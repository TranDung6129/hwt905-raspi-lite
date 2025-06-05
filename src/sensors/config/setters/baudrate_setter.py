"""
Baudrate configuration setter for HWT905 sensor.
"""
import logging
from src.sensors.config.base import HWT905ConfigBase
from src.sensors.hwt905_constants import REG_BAUD

logger = logging.getLogger(__name__)

class BaudrateSetter(HWT905ConfigBase):
    """
    Lớp để thiết lập tốc độ baud của cảm biến HWT905.
    """
    
    def set_baudrate(self, baudrate_value_const: int) -> bool:
        """
        Thiết lập tốc độ baud của cảm biến (thanh ghi BAUD, địa chỉ 0x04).
        Args:
            baudrate_value_const: Hằng số giá trị 16-bit cho tốc độ baud, ví dụ BAUD_RATE_115200 (0x0006).
            
        Lưu ý: Sau khi thay đổi baudrate, cảm biến cần được khởi động lại để áp dụng
        và bạn phải thay đổi baudrate của kết nối serial trên RasPi cho phù hợp.
        """
        data_low = baudrate_value_const & 0xFF
        data_high = (baudrate_value_const >> 8) & 0xFF
        logger.info(f"Đang thiết lập Baudrate (thanh ghi {hex(REG_BAUD)}) với giá trị {hex(baudrate_value_const)} (DL={hex(data_low)}, DH={hex(data_high)})")
        if self._send_write_command(REG_BAUD, data_low, data_high):
            logger.info(f"Lệnh thiết lập Baudrate đã được gửi.")
            return True
        logger.error(f"Gửi lệnh thiết lập Baudrate thất bại.")
        return False
