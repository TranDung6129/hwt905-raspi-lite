"""
Save operations for HWT905 sensor configuration.
"""
import time
import logging
from src.sensors.config.base import HWT905ConfigBase
from src.sensors.hwt905_constants import (
    REG_SAVE, SAVE_CONFIG_VALUE, RESTART_SENSOR_VALUE
)

logger = logging.getLogger(__name__)

class SaveOperations(HWT905ConfigBase):
    """
    Lớp để thực hiện các thao tác lưu cấu hình và khởi động lại cảm biến HWT905.
    """
    
    def save_configuration(self) -> bool:
        """
        Gửi lệnh Lưu cấu hình bằng cách ghi giá trị 0x0000 vào thanh ghi SAVE (địa chỉ 0x00).
        Lệnh đầy đủ được gửi: FF AA 00 00 00.
        """
        logger.info("Đang gửi lệnh Lưu cấu hình (ghi 0x0000 vào thanh ghi SAVE 0x00)...")
        data_low = SAVE_CONFIG_VALUE & 0xFF
        data_high = (SAVE_CONFIG_VALUE >> 8) & 0xFF
        if self._send_write_command(REG_SAVE, data_low, data_high):
            logger.info("Lệnh lưu cấu hình đã được gửi.")
            time.sleep(0.2)
            return True
        else:
            logger.error("Gửi lệnh lưu cấu hình thất bại.")
            return False

    def restart_sensor(self) -> bool:
        """
        Gửi lệnh khởi động lại cảm biến (ghi 0x00FF vào thanh ghi SAVE 0x00).
        Lệnh này thường được sử dụng sau khi thay đổi baudrate hoặc factory reset.
        """
        logger.info("Đang gửi lệnh Khởi động lại cảm biến (ghi 0x00FF vào thanh ghi SAVE 0x00)...")
        data_low = RESTART_SENSOR_VALUE & 0xFF
        data_high = (RESTART_SENSOR_VALUE >> 8) & 0xFF
        if self._send_write_command(REG_SAVE, data_low, data_high, retries=5):
            logger.info("Lệnh khởi động lại cảm biến đã được gửi.")
            time.sleep(2.0)  # Chờ cảm biến khởi động lại hoàn toàn
            return True
        logger.error("Gửi lệnh khởi động lại cảm biến thất bại.")
        return False
