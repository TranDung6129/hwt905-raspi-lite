import logging
import time
import serial
import glob
import os
from typing import Optional, List

logger = logging.getLogger(__name__)

class SensorConnectionManager:
    """
    Quản lý kết nối với cảm biến HWT905 đơn giản.
    """

    def __init__(self, port: str, baudrate: int):
        """
        Khởi tạo ConnectionManager.

        Args:
            port (str): Cổng UART ưu tiên, ví dụ: "/dev/ttyUSB0".
            baudrate (int): Baudrate để kết nối.
        """
        self.preferred_port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.current_port: Optional[str] = None

    def find_available_ports(self) -> List[str]:
        """
        Tìm tất cả cổng USB serial có sẵn.
        
        Returns:
            Danh sách các cổng USB serial
        """
        ports = []
        
        # Tìm tất cả ttyUSB devices
        usb_ports = glob.glob('/dev/ttyUSB*')
        for port in sorted(usb_ports):
            if os.path.exists(port) and os.access(port, os.R_OK | os.W_OK):
                ports.append(port)
        
        # Ưu tiên preferred port lên đầu nếu có
        if self.preferred_port in ports:
            ports.remove(self.preferred_port)
            ports.insert(0, self.preferred_port)
        
        return ports

    def establish_connection(self) -> Optional[serial.Serial]:
        """
        Thiết lập kết nối với cảm biến.

        Returns:
            Instance serial.Serial nếu thành công, None nếu thất bại.
        """
        try:
            # Đóng kết nối cũ nếu có
            self.close_connection()
            
            # Tìm cổng có sẵn
            available_ports = self.find_available_ports()
            if not available_ports:
                logger.error("Không tìm thấy cổng USB serial nào có sẵn")
                return None
            
            # Thử kết nối từng cổng
            for port in available_ports:
                try:
                    logger.info(f"Đang kết nối tới {port} @ {self.baudrate} bps...")
                    
                    self.ser = serial.Serial(
                        port=port,
                        baudrate=self.baudrate,
                        timeout=0.5,
                        write_timeout=1.0,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE
                    )
                    
                    if self.ser.is_open:
                        self.current_port = port
                        self.ser.reset_input_buffer()
                        self.ser.reset_output_buffer()
                        
                        logger.info(f"Kết nối {port} thành công")
                        return self.ser
                
                except serial.SerialException as e:
                    logger.warning(f"Không thể kết nối {port}: {e}")
                    continue
            
            logger.error("Không thể kết nối bất kỳ cổng nào")
            return None

        except Exception as e:
            logger.error(f"Lỗi không xác định: {e}")
            return None

    def wait_for_connection(self, check_interval: int = 5) -> Optional[serial.Serial]:
        """
        Đợi cho đến khi có kết nối thành công.
        
        Args:
            check_interval: Thời gian chờ giữa các lần kiểm tra (giây)
            
        Returns:
            Instance serial.Serial khi có kết nối thành công
        """
        logger.warning("Đang đợi kết nối...")
        
        while True:
            try:
                connection = self.establish_connection()
                if connection and connection.is_open:
                    logger.info(f"Đã có kết nối! (Port: {self.current_port})")
                    return connection
                else:
                    logger.info(f"Chưa có kết nối. Thử lại sau {check_interval} giây...")
                    time.sleep(check_interval)
                    
            except KeyboardInterrupt:
                logger.info("Dừng đợi kết nối do người dùng hủy")
                return None
            except Exception as e:
                logger.error(f"Lỗi khi đợi kết nối: {e}")
                time.sleep(check_interval)

    def handle_serial_error(self, error: Exception, consecutive_failures: int, max_failures: int = 3) -> bool:
        """
        Xử lý lỗi serial và quyết định có cần dừng không.
        
        Args:
            error: Lỗi serial xảy ra
            consecutive_failures: Số lần thất bại liên tiếp
            max_failures: Số lần thất bại tối đa
            
        Returns:
            True nếu cần dừng và đợi kết nối lại
        """
        if consecutive_failures >= max_failures:
            logger.warning("Kết nối bị mất. Đang dừng và đợi kết nối lại...")
            self.close_connection()
            return True
        
        return False

    def close_connection(self):
        """Đóng kết nối serial nếu đang mở."""
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                logger.info(f"Đã đóng kết nối trên {self.current_port}")
            except Exception as e:
                logger.warning(f"Lỗi khi đóng kết nối: {e}")
        self.ser = None
        self.current_port = None