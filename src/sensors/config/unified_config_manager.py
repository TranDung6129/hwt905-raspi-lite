"""
Unified HWT905 Configuration Manager.
Tích hợp tất cả các components cấu hình thành một interface duy nhất.
"""
import serial
import logging
from typing import Optional
from src.sensors.config.base import HWT905ConfigBase
from src.sensors.config.setters.baudrate_setter import BaudrateSetter
from src.sensors.config.setters.update_rate_setter import UpdateRateSetter
from src.sensors.config.setters.output_content_setter import OutputContentSetter
from src.sensors.config.operations.unlock_operations import UnlockOperations
from src.sensors.config.operations.save_operations import SaveOperations
from src.sensors.config.reset.factory_reset_operations import FactoryResetOperations
from src.sensors.config.readers.config_reader import ConfigReader
from src.sensors.config.readers.config_verifier import ConfigVerifier
from src.sensors.hwt905_constants import DEFAULT_BAUDRATE, DEFAULT_SERIAL_TIMEOUT

logger = logging.getLogger(__name__)

class HWT905UnifiedConfigManager(HWT905ConfigBase):
    """
    Unified Config Manager cho cảm biến HWT905.
    Tích hợp tất cả các chức năng cấu hình thành một interface duy nhất.
    """
    
    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE,
                 timeout: float = DEFAULT_SERIAL_TIMEOUT, debug: bool = False):
        """
        Khởi tạo unified config manager.
        Args:
            port: Cổng serial để kết nối
            baudrate: Tốc độ baud cho giao tiếp serial
            timeout: Thời gian chờ đọc serial (giây)
            debug: Kích hoạt logging DEBUG nếu True
        """
        super().__init__(port, baudrate, timeout, debug)
        
        # Khởi tạo tất cả các components
        self.baudrate_setter = BaudrateSetter(port, baudrate, timeout, debug)
        self.update_rate_setter = UpdateRateSetter(port, baudrate, timeout, debug)
        self.output_content_setter = OutputContentSetter(port, baudrate, timeout, debug)
        self.unlock_operations = UnlockOperations(port, baudrate, timeout, debug)
        self.save_operations = SaveOperations(port, baudrate, timeout, debug)
        self.factory_reset_operations = FactoryResetOperations(port, baudrate, timeout, debug)
        self.config_reader = ConfigReader(port, baudrate, timeout, debug)
        self.config_verifier = ConfigVerifier(port, baudrate, timeout, debug)
    
    def connect(self) -> bool:
        """
        Thiết lập kết nối serial và đồng bộ cho tất cả components.
        Returns:
            True nếu kết nối thành công, False nếu thất bại.
        """
        if super().connect():
            self._sync_serial_instance()
            return True
        return False
    
    def _sync_serial_instance(self):
        """Đồng bộ serial instance cho tất cả components."""
        components = [
            self.baudrate_setter,
            self.update_rate_setter,
            self.output_content_setter,
            self.unlock_operations,
            self.save_operations,
            self.factory_reset_operations,
            self.config_reader,
            self.config_verifier
        ]
        
        for component in components:
            component.set_ser_instance(self.ser)
    
    # Setter methods
    def set_baudrate(self, baudrate_value_const: int) -> bool:
        """Thiết lập tốc độ baud của cảm biến."""
        return self.baudrate_setter.set_baudrate(baudrate_value_const)
    
    def set_update_rate(self, rate_value: int) -> bool:
        """Thiết lập tốc độ cập nhật dữ liệu của cảm biến."""
        return self.update_rate_setter.set_update_rate(rate_value)
    
    def set_output_content(self, rsw_value: int) -> bool:
        """Thiết lập nội dung đầu ra của cảm biến."""
        return self.output_content_setter.set_output_content(rsw_value)
    
    def attempt_stop_all_data_output(self) -> bool:
        """Cố gắng dừng tất cả output."""
        return self.output_content_setter.attempt_stop_all_data_output()
    
    # Operation methods
    def unlock_sensor_for_config(self) -> bool:
        """Gửi lệnh mở khóa cảm biến."""
        return self.unlock_operations.unlock_sensor_for_config()
    
    def save_configuration(self) -> bool:
        """Gửi lệnh lưu cấu hình."""
        return self.save_operations.save_configuration()
    
    def restart_sensor(self) -> bool:
        """Gửi lệnh khởi động lại cảm biến."""
        return self.save_operations.restart_sensor()
    
    # Reset methods
    def factory_reset(self) -> bool:
        """Thực hiện factory reset cảm biến."""
        return self.factory_reset_operations.factory_reset()
    
    # Reader methods
    def read_current_config(self, register_address: int, timeout_s: float = 0.5) -> Optional[int]:
        """Đọc giá trị hiện tại của một thanh ghi."""
        return self.config_reader.read_current_config(register_address, timeout_s)
    
    # Verifier methods
    def verify_baudrate(self) -> bool:
        """Kiểm tra xem baudrate hiện tại có phù hợp với cảm biến hay không."""
        return self.config_verifier.verify_baudrate()
    
    def verify_factory_reset_state(self) -> bool:
        """Kiểm tra xem cảm biến đã ở trạng thái mặc định sau factory reset chưa."""
        return self.config_verifier.verify_factory_reset_state()
    
    def set_ser_instance(self, ser_instance: serial.Serial) -> None:
        """
        Thiết lập instance serial từ bên ngoài và đồng bộ cho tất cả components.
        """
        super().set_ser_instance(ser_instance)
        self._sync_serial_instance()
