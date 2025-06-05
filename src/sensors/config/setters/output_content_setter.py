"""
Output content configuration setter for HWT905 sensor.
"""
import logging
from src.sensors.config.base import HWT905ConfigBase
from src.sensors.hwt905_constants import REG_RSW, RSW_NONE

logger = logging.getLogger(__name__)

class OutputContentSetter(HWT905ConfigBase):
    """
    Lớp để thiết lập nội dung đầu ra của cảm biến HWT905.
    """
    
    def set_output_content(self, rsw_value: int) -> bool:
        """
        Thiết lập nội dung đầu ra của cảm biến (thanh ghi RSW, địa chỉ 0x02).
        Args:
            rsw_value: Giá trị 16-bit, mỗi bit tương ứng với một loại dữ liệu output.
                       Ví dụ: DEFAULT_RSW_VALUE (0x001E) để bật ACC, GYRO, ANGLE, MAG.
        """
        data_low = rsw_value & 0xFF
        data_high = (rsw_value >> 8) & 0xFF
        logger.info(f"Đang thiết lập Nội dung đầu ra (RSW {hex(REG_RSW)}) với giá trị {hex(rsw_value)} (DL={hex(data_low)}, DH={hex(data_high)})")
        if self._send_write_command(REG_RSW, data_low, data_high):
            logger.info(f"Lệnh thiết lập Nội dung đầu ra đã được gửi.")
            return True
        logger.error(f"Gửi lệnh thiết lập Nội dung đầu ra thất bại.")
        return False

    def attempt_stop_all_data_output(self) -> bool:
        """
        Cố gắng dừng tất cả output bằng cách ghi 0x0000 (RSW_NONE) vào thanh ghi RSW (0x02).
        """
        logger.info("Đang thử gửi lệnh Dừng tất cả Output (ghi 0x0000 vào RSW 0x02)...")
        data_low = RSW_NONE & 0xFF
        data_high = (RSW_NONE >> 8) & 0xFF
        if self._send_write_command(REG_RSW, data_low, data_high):
            logger.info("Lệnh dừng tất cả output đã được gửi.")
            return True
        logger.error("Gửi lệnh dừng tất cả output thất bại.")
        return False
