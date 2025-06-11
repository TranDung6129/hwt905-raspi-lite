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
    Lớp này không quản lý kết nối serial, nó chỉ sử dụng một instance đã có.
    """

    def __init__(self, debug: bool = False, ser_instance: Optional[serial.Serial] = None):
        """
        Khởi tạo bộ giải mã dữ liệu HWT905.
        Args:
            debug: Kích hoạt logging ở mức DEBUG nếu True.
            ser_instance: Một instance serial.Serial đã được khởi tạo và kết nối.
        """
        self.ser = ser_instance
        self.decoder_factory = PacketDecoderFactory()

        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            if logger.level > logging.INFO:
                 logger.setLevel(logging.INFO)

        self._packet_buffer = b''
        self._last_serial_error_time = 0
        self._serial_error_log_delay = 5  # Chỉ log lỗi serial mỗi 5 giây

    def set_ser_instance(self, ser_instance: Optional[serial.Serial]):
        """
        Thiết lập hoặc cập nhật instance serial được sử dụng bởi decoder.
        Args:
            ser_instance: Instance serial mới, hoặc None để ngắt kết nối.
        """
        self.ser = ser_instance
        self._packet_buffer = b'' # Xóa buffer khi có kết nối mới
        logger.info(f"Data Decoder đã được cập nhật với instance serial mới: {'kết nối' if ser_instance else 'ngắt kết nối'}")

    def read_raw_packet(self) -> Optional[bytes]:
        """
        Đọc cho đến khi tìm thấy một gói dữ liệu 11-byte hoàn chỉnh từ cổng serial.
        Sử dụng buffer để xử lý các byte nhận được không theo gói hoàn chỉnh.
        Returns:
            Một gói dữ liệu 11-byte thô, hoặc None nếu không có dữ liệu mới hoặc có lỗi.
        """
        if not self.ser or not self.ser.is_open:
            # Không log lỗi ở đây để tránh spam, ConnectionManager sẽ xử lý
            return None

        try:
            if self.ser.in_waiting > 0:
                new_bytes = self.ser.read(self.ser.in_waiting)
                self._packet_buffer += new_bytes
        except serial.SerialException as e:
            # Chỉ log lỗi định kỳ để tránh spam
            current_time = time.time()
            if current_time - self._last_serial_error_time > self._serial_error_log_delay:
                logger.error(f"Lỗi serial khi đọc dữ liệu: {e}. Kết nối có thể đã mất.")
                self._last_serial_error_time = current_time
            # Đóng cổng và xóa instance để báo hiệu cho lớp quản lý biết cần kết nối lại
            try:
                self.ser.close()
            except Exception:
                pass # Bỏ qua lỗi khi đóng cổng đã lỗi
            self.ser = None 
            self._packet_buffer = b''
            return None
        except OSError as e:
            # Xử lý lỗi I/O (bao gồm Errno 5) với throttling tương tự như SerialException
            current_time = time.time()
            if current_time - self._last_serial_error_time > self._serial_error_log_delay:
                logger.error(f"Lỗi I/O khi đọc dữ liệu: {e}. Kết nối có thể đã mất.")
                self._last_serial_error_time = current_time
            # Đóng cổng và xóa instance để báo hiệu cho lớp quản lý biết cần kết nối lại
            try:
                self.ser.close()
            except Exception:
                pass # Bỏ qua lỗi khi đóng cổng đã lỗi
            self.ser = None 
            self._packet_buffer = b''
            return None
        except Exception as e:
            # Chỉ log lỗi không xác định với throttling
            current_time = time.time()
            if current_time - self._last_serial_error_time > self._serial_error_log_delay:
                logger.error(f"Lỗi không xác định khi đọc dữ liệu: {e}")
                self._last_serial_error_time = current_time
            return None
        
        # Xử lý buffer để tìm một gói tin hoàn chỉnh
        while True:
            if len(self._packet_buffer) < DATA_PACKET_LENGTH:
                # Không đủ dữ liệu trong buffer để tạo thành một gói tin, thoát ra và chờ thêm
                return None

            header_index = self._packet_buffer.find(bytes([DATA_HEADER_BYTE]))
            if header_index == -1:
                # Không tìm thấy header, buffer này là vô giá trị
                logger.debug(f"Không tìm thấy header trong buffer. Đã xóa {len(self._packet_buffer)} bytes.")
                self._packet_buffer = b''
                return None
            
            if header_index > 0:
                # Dọn dẹp các byte rác trước header
                garbage_bytes = self._packet_buffer[:header_index]
                self._packet_buffer = self._packet_buffer[header_index:]
                logger.warning(f"Tìm thấy {len(garbage_bytes)} byte rác trước header: {garbage_bytes.hex().upper()}. Đã xóa.")
                continue # Bắt đầu lại vòng lặp với buffer đã được dọn dẹp

            # Tại đây, buffer bắt đầu bằng một header và đủ dài
            potential_packet = self._packet_buffer[:DATA_PACKET_LENGTH]
            
            # Kiểm tra checksum ngay tại đây để loại bỏ gói tin không hợp lệ sớm
            if is_valid_data_packet(potential_packet):
                self._packet_buffer = self._packet_buffer[DATA_PACKET_LENGTH:] # Xóa gói tin đã xử lý
                return potential_packet # Trả về gói tin hợp lệ
            else:
                # Gói tin không hợp lệ, xóa header bị lỗi và thử lại
                logger.debug(f"Gói tin không hợp lệ (checksum sai): {potential_packet.hex().upper()}. Bỏ qua.")
                self._packet_buffer = self._packet_buffer[1:]
                continue
        
        return None

    def decode_raw_packet(self, raw_packet: bytes) -> Dict[str, Any]:
        """
        Giải mã một gói dữ liệu thô đã được đọc. Giả định gói tin đã được xác thực checksum.
        Args:
            raw_packet (bytes): Gói dữ liệu 11 byte thô đã được xác thực.
        Returns:
            Dict[str, Any]: Dictionary chứa dữ liệu đã giải mã hoặc thông tin lỗi.
        """
        # is_valid_data_packet đã được gọi trong read_raw_packet, nhưng có thể gọi lại để an toàn
        if len(raw_packet) != DATA_PACKET_LENGTH or raw_packet[0] != DATA_HEADER_BYTE:
             return {
                "error": "invalid_packet", 
                "message": "Packet length or header is incorrect for decoding.",
                "raw_packet": raw_packet
            }
        return self._decode_packet(raw_packet)

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

    def read_one_packet(self) -> Optional[Dict[str, Any]]:
        """
        Đọc và giải mã một gói dữ liệu từ cổng serial.
        
        Returns:
            Dict chứa thông tin packet đã được decode, hoặc None nếu không có packet nào.
        """
        raw_packet = self.read_raw_packet()
        if raw_packet:
            return self.decode_raw_packet(raw_packet)
        return None
