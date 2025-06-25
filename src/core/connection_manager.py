import logging
import time
import serial
import subprocess
import glob
import os
from typing import Optional, List

logger = logging.getLogger(__name__)

class SensorConnectionManager:
    """
    Quản lý kết nối với cảm biến HWT905 sử dụng logic cổng động.
    """

    def __init__(self, port: str, baudrate: int, reconnect_delay_s: int = 5, debug: bool = False):
        """
        Khởi tạo ConnectionManager.

        Args:
            port (str): Cổng UART ưu tiên, ví dụ: "/dev/ttyUSB0".
            baudrate (int): Baudrate để kết nối.
            reconnect_delay_s (int): Thời gian chờ giữa các lần thử kết nối lại.
            debug (bool): Bật chế độ debug.
        """
        self.preferred_port = port
        self.baudrate = baudrate
        self.reconnect_delay_s = reconnect_delay_s
        self.debug = debug
        self.ser: Optional[serial.Serial] = None
        self.current_port: Optional[str] = None
        self.reconnection_attempts = 0

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

    def test_port_with_data(self, port: str, timeout: float = 2.0) -> bool:
        """
        Test cổng bằng cách kiểm tra có dữ liệu từ cảm biến không.
        
        Args:
            port: Cổng serial để test
            timeout: Thời gian chờ tối đa
            
        Returns:
            True nếu cổng có dữ liệu từ cảm biến
        """
        try:
            test_ser = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=0.1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            if test_ser.is_open:
                # Clear buffers
                test_ser.reset_input_buffer()
                test_ser.reset_output_buffer()
                
                # Chờ dữ liệu
                start_time = time.time()
                data_count = 0
                
                while time.time() - start_time < timeout:
                    if test_ser.in_waiting > 0:
                        data = test_ser.read(test_ser.in_waiting)
                        data_count += len(data)
                        if data_count > 100:  # Đủ dữ liệu để confirm
                            test_ser.close()
                            logger.info(f"Cổng {port} có {data_count} bytes dữ liệu - Active!")
                            return True
                    time.sleep(0.1)
                
                test_ser.close()
                
                if data_count > 0:
                    logger.info(f"Cổng {port} có {data_count} bytes dữ liệu nhưng ít")
                    return True
                else:
                    logger.debug(f"Cổng {port} không có dữ liệu")
                    return False
            
        except Exception as e:
            logger.debug(f"Không thể test cổng {port}: {e}")
            return False
        
        return False

    def find_active_port(self) -> Optional[str]:
        """
        Tìm cổng USB serial đang có dữ liệu từ cảm biến.
        
        Returns:
            Cổng đang hoạt động hoặc None
        """
        logger.info("Tìm kiếm cổng USB serial đang hoạt động...")
        
        available_ports = self.find_available_ports()
        if not available_ports:
            logger.warning("Không tìm thấy cổng USB serial nào")
            return None
        
        logger.info(f"Tìm thấy {len(available_ports)} cổng: {available_ports}")
        
        # Test từng cổng để tìm cổng có dữ liệu
        for port in available_ports:
            logger.info(f"Đang test cổng {port}...")
            if self.test_port_with_data(port):
                logger.info(f"Tìm thấy cổng hoạt động: {port}")
                return port
        
        # Nếu không có cổng nào có dữ liệu, trả về cổng đầu tiên
        if available_ports:
            logger.warning(f"Không có cổng nào có dữ liệu. Sử dụng cổng đầu tiên: {available_ports[0]}")
            return available_ports[0]
        
        return None

    def establish_connection(self) -> Optional[serial.Serial]:
        """
        Thiết lập kết nối với cảm biến bằng logic cổng động.

        Returns:
            Instance serial.Serial nếu thành công, None nếu thất bại.
        """
        try:
            # Đóng kết nối cũ nếu có
            self.close_connection()
            
            # Tìm cổng đang hoạt động
            active_port = self.find_active_port()
            if not active_port:
                logger.error("Không tìm thấy cổng USB serial nào có sẵn")
                return None
            
            logger.info(f"Đang kết nối tới {active_port} @ {self.baudrate} bps...")
            
            # Tạo kết nối
            self.ser = serial.Serial(
                port=active_port,
                baudrate=self.baudrate,
                timeout=0.5,
                write_timeout=1.0,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            if self.ser.is_open:
                self.current_port = active_port
                
                # Clear buffers
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                
                # Test nhanh xem có dữ liệu không
                time.sleep(0.5)
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    logger.info(f"Kết nối {active_port} thành công - nhận được {len(data)} bytes")
                else:
                    logger.info(f"Kết nối {active_port} thành công")
                
                return self.ser
            else:
                logger.error(f"Không thể mở cổng {active_port}")
                return None

        except serial.SerialException as e:
            logger.error(f"Lỗi kết nối Serial: {e}")
            return None
        except Exception as e:
            logger.error(f"Lỗi không xác định: {e}")
            return None

    def reconnect(self) -> Optional[serial.Serial]:
        """
        Kết nối lại bằng cách tìm cổng hoạt động mới.
        
        Returns:
            Instance serial.Serial mới nếu thành công, None nếu thất bại.
        """
        logger.info("Thực hiện kết nối lại...")
        self.close_connection()
        time.sleep(1)  # Chờ hệ thống cleanup
        return self.establish_connection()

    def auto_reconnect(self, running_flag) -> Optional[serial.Serial]:
        """
        Thử kết nối lại liên tục cho đến khi thành công hoặc bị dừng.
        
        Args:
            running_flag: Threading event để kiểm tra có nên tiếp tục hay không
            
        Returns:
            Instance serial.Serial mới nếu thành công, None nếu bị dừng
        """
        logger.warning("Bắt đầu kết nối lại...")
        
        reconnect_delay = 3  # Thời gian chờ ban đầu
        attempt_count = 0
        
        while running_flag.is_set():
            attempt_count += 1
            self.reconnection_attempts += 1
            
            try:
                new_serial = self.reconnect()
                if new_serial and new_serial.is_open:
                    logger.info(f"Kết nối lại thành công sau {attempt_count} lần thử! (Port: {self.current_port})")
                    self.reconnection_attempts = 0
                    return new_serial
                else:
                    logger.warning(f"Kết nối lại thất bại (lần {attempt_count})")
                    
            except Exception as e:
                logger.error(f"Lỗi khi thử kết nối lại (lần {attempt_count}): {e}")
            
            logger.info(f"Thử lại sau {reconnect_delay} giây...")
            time.sleep(reconnect_delay)
            
            # Tăng delay nhưng không quá 10 giây
            reconnect_delay = min(reconnect_delay + 1, 10)
        
        logger.warning("Dừng thử kết nối lại do ứng dụng đang thoát.")
        return None

    def handle_serial_error(self, error: Exception, consecutive_failures: int, max_failures: int = 3) -> bool:
        """
        Xử lý lỗi serial đơn giản.
        
        Args:
            error: Lỗi serial xảy ra
            consecutive_failures: Số lần thất bại liên tiếp
            max_failures: Số lần thất bại tối đa
            
        Returns:
            True nếu cần chuyển sang chế độ kết nối lại
        """
        logger.error(f"Lỗi Serial (lần {consecutive_failures}): {error}")
        
        if consecutive_failures >= max_failures:
            logger.warning(f"Quá nhiều lỗi liên tiếp ({consecutive_failures}). Cần kết nối lại...")
            return True
        else:
            logger.info(f"Thử lại... ({consecutive_failures}/{max_failures})")
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