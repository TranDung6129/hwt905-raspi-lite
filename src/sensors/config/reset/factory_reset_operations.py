"""
Factory reset operations for HWT905 sensor.
"""
import time
import logging
from src.sensors.config.base import HWT905ConfigBase
from src.sensors.config.operations.unlock_operations import UnlockOperations
from src.sensors.config.operations.save_operations import SaveOperations
from src.sensors.hwt905_constants import (
    REG_SAVE, FACTORY_RESET_VALUE
)

logger = logging.getLogger(__name__)

class FactoryResetOperations(HWT905ConfigBase):
    """
    Lớp để thực hiện các thao tác factory reset cảm biến HWT905.
    """
    
    def __init__(self, port: str, baudrate: int, timeout: float, debug: bool = False):
        super().__init__(port, baudrate, timeout, debug)
        self.unlock_ops = UnlockOperations(port, baudrate, timeout, debug)
        self.save_ops = SaveOperations(port, baudrate, timeout, debug)
    
    def set_ser_instance(self, ser_instance):
        """Override để đồng bộ serial instance cho tất cả operations."""
        super().set_ser_instance(ser_instance)
        self.unlock_ops.set_ser_instance(ser_instance)
        self.save_ops.set_ser_instance(ser_instance)
    
    def factory_reset(self) -> bool:
        """
        Thực hiện reset cảm biến về cài đặt gốc.
        Quá trình gồm 4 bước:
        1. Mở khóa cảm biến
        2. Factory reset (ghi 0x0001 vào thanh ghi SAVE)
        3. Lưu cài đặt (ghi 0x0000 vào thanh ghi SAVE)
        4. Khởi động lại cảm biến (ghi 0x00FF vào thanh ghi SAVE)
        """
        logger.info("Bắt đầu quá trình Factory Reset cảm biến...")
        
        # Đồng bộ serial instance
        self.unlock_ops.set_ser_instance(self.ser)
        self.save_ops.set_ser_instance(self.ser)
        
        # Bước 1: Mở khóa cảm biến
        if not self.unlock_ops.unlock_sensor_for_config():
            logger.error("Factory Reset thất bại: Không thể mở khóa cảm biến.")
            return False
        time.sleep(0.2)  # Chờ sau unlock
        
        # Bước 2: Gửi lệnh factory reset
        data_low = FACTORY_RESET_VALUE & 0xFF
        data_high = (FACTORY_RESET_VALUE >> 8) & 0xFF
        if not self._send_write_command(REG_SAVE, data_low, data_high, retries=5):
            logger.error("Factory Reset thất bại: Gửi lệnh Reset về cài đặt gốc thất bại.")
            return False
        logger.info("Lệnh Reset về cài đặt gốc đã được gửi.")
        time.sleep(1.0)  # Chờ cảm biến xử lý lệnh
        
        # Bước 3: Lưu cài đặt để đảm bảo factory reset được áp dụng
        if not self.save_ops.save_configuration():
            logger.error("Factory Reset thất bại: Không thể lưu cài đặt sau factory reset.")
            return False
        logger.info("Đã lưu cài đặt sau factory reset.")
        time.sleep(0.5)
        
        # Bước 4: Khởi động lại cảm biến để áp dụng cài đặt factory reset
        if not self.save_ops.restart_sensor():
            logger.error("Factory Reset thất bại: Không thể khởi động lại cảm biến.")
            return False
            
        logger.info("Đã hoàn tất quá trình factory reset và khởi động lại cảm biến.")
        logger.warning("Cảm biến sẽ thực hiện Reset. Cần kết nối lại với baudrate mặc định (thường là 9600) sau một khoảng thời gian.")
        return True
