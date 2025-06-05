# src/sensor/hwt905_data_decoder.py

"""
Chứa các hàm để đọc (decode) các gói dữ liệu nhận được từ cảm biến
và chuyển đổi raw data thành giá trị có ý nghĩa.
Đã được refactor để sử dụng PacketDecoderFactory.
"""
import serial
import time
import logging
from typing import Dict, Any, Optional

from src.sensors.hwt905_constants import (
    DATA_HEADER_BYTE,
    DATA_PACKET_LENGTH,
    DEFAULT_SERIAL_TIMEOUT, DEFAULT_BAUDRATE
)
from src.sensors.hwt905_protocol import calculate_checksum, is_valid_data_packet
from src.sensors.decoders import PacketDecoderFactory

logger = logging.getLogger(__name__)

class HWT905DataDecoder:
    """
    Lớp để đọc và giải mã các gói dữ liệu từ cảm biến Witmotion HWT905.
    Sử dụng PacketDecoderFactory để decode các packet types khác nhau.
    """

    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE,
                 timeout: float = DEFAULT_SERIAL_TIMEOUT, debug: bool = False,
                 ser_instance: Optional[serial.Serial] = None):
        """
        Khởi tạo bộ giải mã dữ liệu HWT905.
        Args:
            port: Cổng serial để kết nối.
            baudrate: Tốc độ baud cho giao tiếp serial.
            timeout: Thời gian chờ đọc serial (giây).
            debug: Kích hoạt logging ở mức DEBUG nếu True.
            ser_instance: Một instance serial.Serial đã được khởi tạo. Nếu cung cấp,
                          lớp sẽ sử dụng instance này thay vì tự mở/đóng cổng.
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = ser_instance # Sử dụng instance serial được cung cấp nếu có
        
        # Khởi tạo decoder factory
        self.decoder_factory = PacketDecoderFactory()

        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            if logger.level > logging.INFO:
                 logger.setLevel(logging.INFO)

        self._packet_buffer = b'' # Buffer để lưu trữ các byte nhận được

    def connect(self) -> bool:
        """
        Thiết lập kết nối serial đến cảm biến nếu chưa có ser_instance.
        Returns:
            True nếu kết nối thành công, False nếu thất bại.
        """
        if self.ser and self.ser.is_open:
            logger.info(f"Kết nối serial trên {self.port} đã được thiết lập.")
            if self.ser.baudrate != self.baudrate:
                logger.warning(f"Baudrate của kết nối hiện tại ({self.ser.baudrate}) không khớp với baudrate yêu cầu ({self.baudrate}). Đang cố gắng đóng và mở lại.")
                self.ser.close()
                self.ser = None

        if self.ser is None or not self.ser.is_open:
            try:
                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.timeout
                )
                logger.info(f"Đã kết nối tới HWT905 trên {self.port} với baudrate {self.baudrate}")
                return True
            except serial.SerialException as e:
                logger.error(f"Không thể kết nối tới {self.port} @ {self.baudrate}bps: {str(e)}")
                self.ser = None
                return False
            except Exception as e:
                logger.error(f"Lỗi không xác định khi kết nối tới {self.port}: {str(e)}")
                self.ser = None
                return False
        return True # Return True if connection was already open or just established successfully


    def close(self) -> None:
        """Đóng kết nối serial nếu nó được mở bởi instance này."""
        if self.ser and self.ser.is_open:
            # Chỉ đóng cổng nếu instance này tự mở nó (không phải là ser_instance được truyền vào)
            # Hoặc nếu không có cách nào để biết, hãy cảnh báo và đóng.
            logger.info(f"Đang đóng kết nối serial trên {self.port}.")
            self.ser.close()
        self.ser = None

    def read_one_packet(self) -> Optional[Dict[str, Any]]:
        """
        Đọc một gói dữ liệu từ cổng serial và giải mã nó.
        Sử dụng buffer để xử lý các byte nhận được không theo gói hoàn chỉnh.
        Returns:
            Dict[str, Any] chứa dữ liệu đã giải mã hoặc thông tin lỗi, hoặc None nếu không có gói hợp lệ.
        """
        if not self.ser or not self.ser.is_open:
            logger.error("Lỗi đọc gói tin: Kết nối serial chưa được thiết lập hoặc đã đóng.")
            return None

        # Đọc dữ liệu mới vào buffer
        try:
            new_bytes = self.ser.read(self.ser.in_waiting or 1) # Đọc tất cả byte có sẵn hoặc ít nhất 1 byte
            if not new_bytes:
                return None # Không có dữ liệu mới
            self._packet_buffer += new_bytes
        except serial.SerialException as e:
            logger.error(f"Lỗi serial khi đọc dữ liệu: {e}")
            self._packet_buffer = b'' # Xóa buffer để tránh dữ liệu hỏng
            return {"error": "serial_error", "message": str(e)}
        except Exception as e:
            logger.error(f"Lỗi không xác định khi đọc dữ liệu: {e}")
            return {"error": "unknown_error", "message": str(e)}

        # Tìm kiếm và xử lý gói tin trong buffer
        while len(self._packet_buffer) >= DATA_PACKET_LENGTH:
            # Tìm byte header
            header_index = self._packet_buffer.find(bytes([DATA_HEADER_BYTE]))
            
            if header_index == -1:
                # Không tìm thấy header, xóa toàn bộ buffer
                logger.debug("Không tìm thấy header byte trong buffer, xóa buffer.")
                self._packet_buffer = b''
                return None # Quay lại chờ thêm dữ liệu
            
            if header_index > 0:
                # Tìm thấy header nhưng có các byte rác ở phía trước
                garbage_bytes = self._packet_buffer[:header_index]
                self._packet_buffer = self._packet_buffer[header_index:]
                logger.warning(f"Tìm thấy {len(garbage_bytes)} byte rác trước header: {garbage_bytes.hex().upper()}. Đã xóa.")
                # Nếu có nhiều byte rác, có thể là baudrate mismatch
                if len(garbage_bytes) > 50: # Một ngưỡng tùy ý
                    logger.error("Phát hiện số lượng lớn byte rác. Khả năng cao không khớp baudrate!")
                    self._packet_buffer = b'' # Xóa buffer
                    return {"error": "possible_baudrate_mismatch", "raw_bytes": garbage_bytes.hex()}

            # Nếu buffer đủ dài để chứa một gói tin tiềm năng
            if len(self._packet_buffer) >= DATA_PACKET_LENGTH:
                potential_packet = self._packet_buffer[:DATA_PACKET_LENGTH]
                
                if is_valid_data_packet(potential_packet):
                    self._packet_buffer = self._packet_buffer[DATA_PACKET_LENGTH:] # Xóa gói tin đã xử lý khỏi buffer
                    return self._decode_packet(potential_packet)
                else:
                    # Gói tin không hợp lệ (checksum sai hoặc cấu trúc sai)
                    # Xóa byte header đầu tiên và thử lại
                    logger.debug(f"Gói tin không hợp lệ: {potential_packet.hex().upper()}. Xóa byte đầu tiên.")
                    self._packet_buffer = self._packet_buffer[1:] # Xóa byte đầu tiên (đầu header đã tìm thấy)
                    # Không return ở đây, mà tiếp tục vòng lặp while để tìm gói tin hợp lệ tiếp theo
            else:
                # Buffer chưa đủ dài để chứa gói tin hoàn chỉnh sau khi xử lý byte rác/header
                return None # Quay lại chờ thêm dữ liệu

        return None # Không có gói tin hoàn chỉnh nào trong buffer

    def _decode_packet(self, packet_bytes: bytes) -> Dict[str, Any]:
        """
        Giải mã một gói dữ liệu hoàn chỉnh và hợp lệ.
        Args:
            packet_bytes (bytes): Gói dữ liệu 11 byte hợp lệ.
        Returns:
            Dict[str, Any]: Dictionary chứa dữ liệu đã giải mã.
        """
        packet_type = packet_bytes[1]
        payload = packet_bytes[2:DATA_PACKET_LENGTH-1] # 8 bytes payload
        
        decoded_data: Dict[str, Any] = {
            "raw_packet": packet_bytes,
            "header": packet_bytes[0],
            "type": packet_type,
            "type_name": self.decoder_factory.get_packet_type_name(packet_type),
            "payload": payload,
            "checksum": packet_bytes[-1]
        }

        # Sử dụng decoder factory để decode payload
        try:
            payload_data = self.decoder_factory.decode_packet(packet_type, payload)
            decoded_data.update(payload_data)
        except Exception as e:
            logger.error(f"Lỗi khi decode packet type 0x{packet_type:02X}: {e}")
            decoded_data["error"] = "decoding_error"
            decoded_data["message"] = str(e)
            
        return decoded_data

    def get_supported_packet_types(self) -> Dict[int, str]:
        """
        Trả về danh sách các packet types được hỗ trợ
        
        Returns:
            Dict mapping packet_type -> packet_name
        """
        return self.decoder_factory.list_supported_types()
