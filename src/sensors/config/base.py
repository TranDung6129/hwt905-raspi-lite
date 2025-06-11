"""
Base class for HWT905 configuration components.
Provides shared serial connection and command sending functionality.
"""
import serial
import time
import logging
from typing import Optional
from src.sensors.hwt905_constants import (
    COMMAND_HEADER_BYTE1, COMMAND_HEADER_BYTE2,
    DEFAULT_BAUDRATE, DEFAULT_SERIAL_TIMEOUT
)

logger = logging.getLogger(__name__)

class HWT905ConfigBase:
    """
    Base class cho các component cấu hình HWT905.
    Cung cấp kết nối serial chung và chức năng gửi lệnh.
    """
    
    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE,
                 timeout: float = DEFAULT_SERIAL_TIMEOUT, debug: bool = False):
        """
        Khởi tạo base component.
        Args:
            port: Cổng serial để kết nối
            baudrate: Tốc độ baud cho giao tiếp serial
            timeout: Thời gian chờ đọc serial (giây)
            debug: Kích hoạt logging DEBUG nếu True
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            if logger.level > logging.INFO:
                logger.setLevel(logging.INFO)
    
    def _send_write_command(self, register_address: int, data_low: int, data_high: int, retries: int = 3) -> bool:
        """
        Gửi một lệnh GHI (Write) đến cảm biến theo định dạng FF AA ADDR DATAL DATAH.
        Args:
            register_address: Địa chỉ của thanh ghi.
            data_low: Byte thấp của dữ liệu cần ghi (0-255).
            data_high: Byte cao của dữ liệu cần ghi (0-255).
            retries: Số lần thử lại nếu lệnh không thành công
        Returns:
            True nếu gửi thành công, False nếu có lỗi.
        """
        if not self.ser or not self.ser.is_open:
            logger.error("Lỗi gửi lệnh ghi: Kết nối serial chưa được thiết lập hoặc đã đóng.")
            return False

        command_bytes = bytes([COMMAND_HEADER_BYTE1, COMMAND_HEADER_BYTE2, 
                               register_address & 0xFF,
                               data_low & 0xFF,
                               data_high & 0xFF])
        
        attempt = 0
        while attempt < retries:
            try:
                self.ser.reset_input_buffer()
                bytes_written = self.ser.write(command_bytes)
                
                if bytes_written == 5:
                    logger.debug(f"Đã gửi lệnh GHI: {' '.join([f'{b:02X}' for b in command_bytes])} tới thanh ghi {hex(register_address)}")
                    return True
                else:
                    logger.warning(f"Gửi lệnh GHI không đầy đủ ({bytes_written}/5 bytes) tới thanh ghi {hex(register_address)}. Thử lại {attempt+1}/{retries}...")
                    attempt += 1
                    time.sleep(0.1)
                    
            except serial.SerialException as e:
                logger.error(f"Lỗi serial khi gửi lệnh GHI tới thanh ghi {hex(register_address)}: {e}. Thử lại {attempt+1}/{retries}...")
                attempt += 1
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Lỗi không xác định khi gửi lệnh GHI tới thanh ghi {hex(register_address)}: {e}. Thử lại {attempt+1}/{retries}...")
                attempt += 1
                time.sleep(0.1)
        
        logger.error(f"Đã thử {retries} lần nhưng không thể gửi lệnh thành công tới thanh ghi {hex(register_address)}")
        return False

    def set_ser_instance(self, ser_instance: serial.Serial) -> None:
        """
        Thiết lập instance serial từ bên ngoài.
        Hữu ích khi muốn chia sẻ kết nối serial giữa các component.
        """
        self.ser = ser_instance
        if ser_instance:
            self.port = ser_instance.port
            self.baudrate = ser_instance.baudrate
            self.timeout = ser_instance.timeout
