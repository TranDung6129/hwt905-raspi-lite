# src/sensor/hwt905_config_manager.py
"""
Legacy HWT905 Config Manager - Deprecated
Sử dụng HWT905UnifiedConfigManager từ src.sensors.config thay thế.
File này được giữ lại để tương thích backward compatibility.
"""
import logging
from src.sensors.config.unified_config_manager import HWT905UnifiedConfigManager
from src.sensors.hwt905_constants import DEFAULT_BAUDRATE, DEFAULT_SERIAL_TIMEOUT

# Thiết lập logging cơ bản nếu chưa có handlers
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HWT905ConfigManager(HWT905UnifiedConfigManager):
    """
    Legacy class cho HWT905ConfigManager.
    Deprecated - Sử dụng HWT905UnifiedConfigManager thay thế.
    
    Lớp này được giữ lại để đảm bảo tương thích backward compatibility
    với code hiện tại đang sử dụng HWT905ConfigManager.
    """
    
    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE,
                 timeout: float = DEFAULT_SERIAL_TIMEOUT, debug: bool = False):
        """
        Khởi tạo legacy config manager.
        Args:
            port: Cổng serial để kết nối (ví dụ: '/dev/ttyUSB0', 'COM3')
            baudrate: Tốc độ baud cho giao tiếp serial
            timeout: Thời gian chờ đọc serial (giây)
            debug: Kích hoạt logging ở mức DEBUG nếu True
        """
        logger.warning("HWT905ConfigManager is deprecated. Use HWT905UnifiedConfigManager from src.sensors.config instead.")
        super().__init__(port, baudrate, timeout, debug)