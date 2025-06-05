"""
Update rate configuration setter for HWT905 sensor.
"""
import logging
from src.sensors.config.base import HWT905ConfigBase
from src.sensors.hwt905_constants import REG_RRATE

logger = logging.getLogger(__name__)

class UpdateRateSetter(HWT905ConfigBase):
    """
    Lớp để thiết lập tốc độ cập nhật dữ liệu của cảm biến HWT905.
    """
    
    def set_update_rate(self, rate_value: int) -> bool:
        """
        Thiết lập tốc độ cập nhật dữ liệu của cảm biến (thanh ghi RRATE, địa chỉ 0x03).
        Args:
            rate_value: Giá trị 16-bit cho tốc độ, ví dụ RATE_OUTPUT_10HZ (0x0006).
        """
        data_low = rate_value & 0xFF
        data_high = (rate_value >> 8) & 0xFF
        logger.info(f"Đang thiết lập Tốc độ cập nhật (thanh ghi {hex(REG_RRATE)}) với giá trị {hex(rate_value)} (DL={hex(data_low)}, DH={hex(data_high)})")
        if self._send_write_command(REG_RRATE, data_low, data_high):
            logger.info(f"Lệnh thiết lập Tốc độ cập nhật đã được gửi.")
            return True
        logger.error(f"Gửi lệnh thiết lập Tốc độ cập nhật thất bại.")
        return False
