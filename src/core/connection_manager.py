import logging
import time
import serial
from typing import Optional

logger = logging.getLogger(__name__)

class SensorConnectionManager:
    """
    Quản lý kết nối và tái kết nối với cảm biến HWT905 một cách đơn giản.
    """

    def __init__(self, port: str, baudrate: int, reconnect_delay_s: int = 5, debug: bool = False):
        """
        Khởi tạo ConnectionManager.

        Args:
            port (str): Cổng UART, ví dụ: "/dev/ttyUSB0".
            baudrate (int): Baudrate để kết nối.
            reconnect_delay_s (int): Thời gian chờ giữa các lần thử kết nối lại.
            debug (bool): Bật chế độ debug.
        """
        self.port = port
        self.baudrate = baudrate
        self.reconnect_delay_s = reconnect_delay_s
        self.debug = debug
        self.ser: Optional[serial.Serial] = None

    def establish_connection(self) -> Optional[serial.Serial]:
        """
        Cố gắng thiết lập kết nối với cảm biến.
        Hàm này sẽ không lặp lại, chỉ thử một lần.

        Returns:
            Một instance serial.Serial nếu kết nối thành công, hoặc None nếu thất bại.
        """
        try:
            logger.info(f"Đang thử kết nối tới cảm biến trên {self.port} @ {self.baudrate} bps...")
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            
            if self.ser.is_open:
                # Gửi một byte rác để "đánh thức" cổng, đôi khi cần thiết
                self.ser.write(b'\x00') 
                logger.info(f"Đã mở cổng {self.port} thành công.")
                return self.ser
            else:
                logger.warning(f"Không thể mở cổng {self.port} dù không có lỗi.")
                return None

        except serial.SerialException as e:
            logger.error(f"Lỗi kết nối Serial trên cổng {self.port}: {e}")
            return None
        except Exception as e:
            logger.error(f"Lỗi không xác định khi kết nối: {e}")
            return None

    def close_connection(self):
        """Đóng kết nối serial nếu đang mở."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info(f"Đã đóng kết nối trên cổng {self.port}.")
        self.ser = None