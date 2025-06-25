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
        self.debug = debug  # Lưu debug flag
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
        Đọc một gói dữ liệu thô từ cổng serial.
        Trả về None nếu không có dữ liệu hoặc gặp lỗi.
        Raise SerialException nếu mất kết nối.
        """
        try:
            if not self.ser or not self.ser.is_open:
                logger.error("Cổng serial không mở hoặc đã bị đóng")
                raise serial.SerialException("Cổng serial không khả dụng")
                
            # Tìm header 0x55
            header_byte = self.ser.read(1)
            if not header_byte:
                return None
                
            if header_byte[0] != 0x55:
                if self.debug:
                    logger.debug(f"Byte không phải header: 0x{header_byte[0]:02X}")
                return None
            
            # Đọc 10 byte còn lại (tổng cộng 11 byte)
            remaining_data = self.ser.read(10)
            if len(remaining_data) != 10:
                logger.warning(f"Chỉ đọc được {len(remaining_data)}/10 byte sau header")
                return None
            
            full_packet = header_byte + remaining_data
            
            if self.debug:
                packet_hex = ' '.join(f'{b:02X}' for b in full_packet)
                logger.debug(f"Gói tin thô: {packet_hex}")
            
            return full_packet
            
        except serial.SerialTimeoutException:
            # Timeout bình thường, không phải lỗi
            return None
            
        except serial.SerialException as e:
            # Lỗi serial nghiêm trọng - mất kết nối
            # Không log ở đây nữa, để connection_manager xử lý
            raise e
                
        except OSError as e:
            # Lỗi hệ điều hành - thường là mất kết nối
            # Không log ở đây nữa, để connection_manager xử lý
            raise serial.SerialException(f"Mất kết nối: {e}")
            
        except Exception as e:
            logger.error(f"Lỗi không mong muốn khi đọc: {e}", exc_info=True)
            raise serial.SerialException(f"Lỗi đọc dữ liệu: {e}")

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
