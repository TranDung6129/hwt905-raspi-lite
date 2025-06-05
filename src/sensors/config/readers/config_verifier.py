"""
Configuration verifier for HWT905 sensor.
"""
import logging
from src.sensors.config.base import HWT905ConfigBase
from src.sensors.config.readers.config_reader import ConfigReader
from src.sensors.hwt905_constants import (
    REG_BAUD, REG_RSW, REG_RRATE,
    DEFAULT_RSW_VALUE, RATE_OUTPUT_10HZ, BAUD_RATE_9600
)

logger = logging.getLogger(__name__)

class ConfigVerifier(HWT905ConfigBase):
    """
    Lớp để kiểm tra và xác minh cấu hình của cảm biến HWT905.
    """
    
    def __init__(self, port: str, baudrate: int, timeout: float, debug: bool = False):
        super().__init__(port, baudrate, timeout, debug)
        self.config_reader = ConfigReader(port, baudrate, timeout, debug)
    
    def set_ser_instance(self, ser_instance):
        """Override để đồng bộ serial instance cho config reader."""
        super().set_ser_instance(ser_instance)
        self.config_reader.set_ser_instance(ser_instance)
    
    def verify_baudrate(self) -> bool:
        """
        Kiểm tra xem baudrate hiện tại có phù hợp với cảm biến hay không bằng cách
        cố gắng đọc một thanh ghi với timeout ngắn.
        
        Returns:
            True nếu baudrate phù hợp (có thể đọc dữ liệu), False nếu không.
        """
        if not self.ser or not self.ser.is_open:
            logger.error("Không thể kiểm tra baudrate: Kết nối serial chưa được thiết lập.")
            return False

        original_timeout = self.ser.timeout
        self.ser.timeout = 0.1  # Short timeout for quicker checking
        
        try:
            # Đồng bộ serial instance
            self.config_reader.set_ser_instance(self.ser)
            
            # Cố gắng đọc một thanh ghi phổ biến với timeout ngắn
            result = self.config_reader.read_current_config(REG_BAUD, timeout_s=0.2)
            if result is not None:
                logger.info(f"Baudrate verification succeeded: Read value {hex(result)} from register {hex(REG_BAUD)}")
                return True
            else:
                logger.warning("Baudrate verification failed: Could not read from register.")
                return False
        except ValueError as e:
            logger.warning(f"Baudrate verification failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Baudrate verification failed with unexpected error: {e}")
            return False
        finally:
            # Khôi phục timeout ban đầu
            self.ser.timeout = original_timeout

    def verify_factory_reset_state(self) -> bool:
        """
        Kiểm tra xem cảm biến đã ở trạng thái mặc định sau khi factory reset chưa.
        Kiểm tra các cài đặt mặc định như:
        - RSW (Output Content): 0x001E (Acc, Gyro, Angle, Mag)
        - RRATE (Output Rate): 0x0006 (10Hz)
        - BAUD: 0x0002 (9600 bps)
        
        Returns:
            True nếu cảm biến đã về trạng thái mặc định, False nếu không.
        """
        logger.info("Đang kiểm tra trạng thái của cảm biến sau khi Factory Reset...")
        
        # Đồng bộ serial instance
        self.config_reader.set_ser_instance(self.ser)
        
        # Giá trị mặc định mong đợi
        expected_rsw = DEFAULT_RSW_VALUE
        expected_rate = RATE_OUTPUT_10HZ
        expected_baud = BAUD_RATE_9600

        # Kiểm tra RSW (Output Content)
        rsw_val = self.config_reader.read_current_config(REG_RSW, timeout_s=0.5)
        if rsw_val is None:
            logger.error("Không thể đọc giá trị RSW sau khi factory reset.")
            return False
        
        # Kiểm tra RRATE (Output Rate)
        rate_val = self.config_reader.read_current_config(REG_RRATE, timeout_s=0.5)
        if rate_val is None:
            logger.error("Không thể đọc giá trị RRATE sau khi factory reset.")
            return False
            
        # Kiểm tra BAUD
        baud_val = self.config_reader.read_current_config(REG_BAUD, timeout_s=0.5)
        if baud_val is None:
            logger.error("Không thể đọc giá trị BAUD sau khi factory reset.")
            return False
            
        # So sánh với giá trị mặc định
        if rsw_val != expected_rsw:
            logger.error(f"RSW không đúng giá trị mặc định: {hex(rsw_val)} (mong đợi {hex(expected_rsw)})")
            return False
            
        if rate_val != expected_rate:
            logger.error(f"RRATE không đúng giá trị mặc định: {hex(rate_val)} (mong đợi {hex(expected_rate)})")
            return False
            
        if baud_val != expected_baud:
            logger.error(f"BAUD không đúng giá trị mặc định: {hex(baud_val)} (mong đợi {hex(expected_baud)})")
            return False
            
        logger.info("Cảm biến đã trở về trạng thái mặc định sau khi factory reset!")
        return True
