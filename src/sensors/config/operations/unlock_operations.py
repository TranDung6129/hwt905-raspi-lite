"""
Unlock operations for HWT905 sensor configuration.
"""
import time
import logging
from src.sensors.config.base import HWT905ConfigBase
from src.sensors.hwt905_constants import (
    REG_KEY, UNLOCK_KEY_VALUE_DATAL, UNLOCK_KEY_VALUE_DATAH
)

logger = logging.getLogger(__name__)

class UnlockOperations(HWT905ConfigBase):
    """
    Lớp để thực hiện các thao tác mở khóa cảm biến HWT905.
    """
    
    def unlock_sensor_for_config(self) -> bool:
        """
        Gửi lệnh Mở khóa cảm biến bằng cách ghi giá trị 0xB588 vào thanh ghi KEY (địa chỉ 0x69).
        Lệnh đầy đủ được gửi: FF AA 69 88 B5.
        """
        logger.info("Đang gửi lệnh Mở khóa cảm biến (ghi 0xB588 vào thanh ghi KEY 0x69)...")
        if self._send_write_command(REG_KEY, UNLOCK_KEY_VALUE_DATAL, UNLOCK_KEY_VALUE_DATAH):
            logger.info("Lệnh mở khóa đã được gửi.")
            time.sleep(0.1)
            return True
        else:
            logger.error("Gửi lệnh mở khóa thất bại.")
            return False
