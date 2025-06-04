# src/sensor/hwt905_config_manager.py
import serial
import time
import logging
from typing import Optional
from src.sensors.hwt905_constants import (
    DEFAULT_BAUDRATE, DEFAULT_SERIAL_TIMEOUT,
    COMMAND_HEADER_BYTE1, COMMAND_HEADER_BYTE2,
    REG_KEY, UNLOCK_KEY_VALUE_DATAL, UNLOCK_KEY_VALUE_DATAH,
    REG_SAVE, SAVE_CONFIG_VALUE, FACTORY_RESET_VALUE, RESTART_SENSOR_VALUE,
    REG_BAUD, BAUD_RATE_9600, BAUD_RATE_115200, # Các baudrate ví dụ
    REG_RRATE, RATE_OUTPUT_10HZ, RATE_OUTPUT_50HZ, RATE_OUTPUT_100HZ, RATE_OUTPUT_200HZ,
    REG_RSW, DEFAULT_RSW_VALUE, RSW_NONE,
    REG_READADDR,
    PACKET_TYPE_READ_REGISTER
)
from src.sensors.hwt905_data_decoder import HWT905DataDecoder # Sẽ tạo sau

# Thiết lập logging cơ bản nếu chưa có handlers
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HWT905ConfigManager:
    """
    Lớp để cấu hình cảm biến Witmotion HWT905 qua kết nối serial,
    dựa trên giao thức ghi thanh ghi FF AA ADDR DATAL DATAH.
    """

    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE,
                 timeout: float = DEFAULT_SERIAL_TIMEOUT, debug: bool = False):
        """
        Khởi tạo giao diện cấu hình HWT905.
        Args:
            port: Cổng serial để kết nối (ví dụ: '/dev/ttyUSB0', 'COM3')
            baudrate: Tốc độ baud cho giao tiếp serial
            timeout: Thời gian chờ đọc serial (giây)
            debug: Kích hoạt logging ở mức DEBUG nếu True
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            # Chỉ hạ cấp độ nếu nó cao hơn INFO và debug không được bật
            if logger.level > logging.INFO:
                logger.setLevel(logging.INFO)

    def connect(self) -> bool:
        """
        Thiết lập kết nối serial đến cảm biến.
        Returns:
            True nếu kết nối thành công, False nếu thất bại.
        """
        if self.ser and self.ser.is_open:
            logger.info(f"Kết nối serial trên {self.port} đã được thiết lập.")
            # Kiểm tra xem baudrate của kết nối hiện tại có khớp với self.baudrate không
            if self.ser.baudrate != self.baudrate:
                logger.warning(f"Baudrate của kết nối hiện tại ({self.ser.baudrate}) không khớp với baudrate yêu cầu ({self.baudrate}). Đang cố gắng đóng và mở lại.")
                self.ser.close()
                self.ser = None # Reset self.ser để buộc tạo lại kết nối

        if self.ser is None or not self.ser.is_open:
            try:
                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.timeout
                )
                logger.info(f"Đã kết nối tới HWT905 trên {self.port} với baudrate {self.baudrate}")
                return True
            except serial.SerialException as e:
                logger.error(f"Không thể kết nối tới {self.port} @ {self.baudrate}bps: {str(e)}")
                self.ser = None
                return False
            except Exception as e:
                logger.error(f"Lỗi không xác định khi kết nối tới {self.port}: {str(e)}")
                self.ser = None
                return False
        return False # Should not reach here if connection was already open or just established


    def close(self) -> None:
        """Đóng kết nối serial."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info(f"Đã đóng kết nối serial trên {self.port}.")
        self.ser = None

    def _send_write_command(self, register_address: int, data_low: int, data_high: int, retries: int = 3) -> bool:
        """
        Gửi một lệnh GHI (Write) đến cảm biến theo định dạng FF AA ADDR DATAL DATAH.
        Args:
            register_address: Địa chỉ của thanh ghi.
            data_low: Byte thấp của dữ liệu cần ghi (0-255).
            data_high: Byte cao của dữ liệu cần ghi (0-255).
            retries: Số lần thử lại nếu lệnh không thành công
        Returns:
            True nếu gửi thành công, False nếu có lỗi.
        """
        if not self.ser or not self.ser.is_open:
            logger.error("Lỗi gửi lệnh ghi: Kết nối serial chưa được thiết lập hoặc đã đóng.")
            return False

        command_bytes = bytes([COMMAND_HEADER_BYTE1, COMMAND_HEADER_BYTE2, 
                               register_address & 0xFF, # Đảm bảo chỉ lấy 1 byte
                               data_low & 0xFF,         # Đảm bảo chỉ lấy 1 byte
                               data_high & 0xFF])        # Đảm bảo chỉ lấy 1 byte
        
        attempt = 0
        while attempt < retries:
            try:
                self.ser.reset_input_buffer() # Xóa buffer nhận trước khi gửi lệnh
                bytes_written = self.ser.write(command_bytes)
                
                # Kiểm tra xem đã gửi đủ 5 bytes chưa (COMMAND_PACKET_LENGTH)
                if bytes_written == 5: # Sử dụng hằng số COMMAND_PACKET_LENGTH
                    logger.debug(f"Đã gửi lệnh GHI: {' '.join([f'{b:02X}' for b in command_bytes])} tới thanh ghi {hex(register_address)}")
                    # Chờ lâu hơn nếu đây là lệnh quan trọng như factory reset hoặc save
                    if register_address == REG_SAVE:
                        time.sleep(0.2)  # Chờ lâu hơn cho các lệnh save
                    else:
                        time.sleep(0.05) # Thời gian chờ ngắn hơn cho các lệnh thông thường
                    return True
                else:
                    logger.warning(f"Gửi lệnh GHI không đầy đủ ({bytes_written}/5 bytes) tới thanh ghi {hex(register_address)}. Thử lại {attempt+1}/{retries}...")
                    attempt += 1
                    time.sleep(0.1)
                    
            except serial.SerialException as e:
                logger.error(f"Lỗi serial khi gửi lệnh GHI tới thanh ghi {hex(register_address)}: {e}. Thử lại {attempt+1}/{retries}...")
                attempt += 1
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Lỗi không xác định khi gửi lệnh GHI tới thanh ghi {hex(register_address)}: {e}. Thử lại {attempt+1}/{retries}...")
                attempt += 1
                time.sleep(0.1)
        
        logger.error(f"Đã thử {retries} lần nhưng không thể gửi lệnh thành công tới thanh ghi {hex(register_address)}")
        return False

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

    def set_baudrate(self, baudrate_value_const: int) -> bool:
        """
        Thiết lập tốc độ baud của cảm biến (thanh ghi BAUD, địa chỉ 0x04).
        Args:
            baudrate_value_const: Hằng số giá trị 16-bit cho tốc độ baud, ví dụ BAUD_RATE_115200 (0x0006).
            
        Lưu ý: Sau khi thay đổi baudrate, cảm biến cần được khởi động lại để áp dụng
        và bạn phải thay đổi baudrate của kết nối serial trên RasPi cho phù hợp.
        """
        data_low = baudrate_value_const & 0xFF
        data_high = (baudrate_value_const >> 8) & 0xFF
        logger.info(f"Đang thiết lập Baudrate (thanh ghi {hex(REG_BAUD)}) với giá trị {hex(baudrate_value_const)} (DL={hex(data_low)}, DH={hex(data_high)})")
        if self._send_write_command(REG_BAUD, data_low, data_high):
            logger.info(f"Lệnh thiết lập Baudrate đã được gửi.")
            # Cần khởi động lại cảm biến và thay đổi baudrate của self.ser sau đó.
            return True
        logger.error(f"Gửi lệnh thiết lập Baudrate thất bại.")
        return False

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
            time.sleep(0.1) # Chờ một chút để cảm biến ngừng gửi dữ liệu
            return True
        logger.error("Gửi lệnh dừng tất cả output thất bại.")
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
            time.sleep(2.0) # Chờ cảm biến khởi động lại hoàn toàn
            return True
        logger.error("Gửi lệnh khởi động lại cảm biến thất bại.")
        return False

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
        
        # Bước 1: Mở khóa cảm biến
        if not self.unlock_sensor_for_config():
            logger.error("Factory Reset thất bại: Không thể mở khóa cảm biến.")
            return False
        time.sleep(0.2) # Chờ sau unlock
        
        # Bước 2: Gửi lệnh factory reset
        data_low = FACTORY_RESET_VALUE & 0xFF
        data_high = (FACTORY_RESET_VALUE >> 8) & 0xFF
        if not self._send_write_command(REG_SAVE, data_low, data_high, retries=5):
            logger.error("Factory Reset thất bại: Gửi lệnh Reset về cài đặt gốc thất bại.")
            return False
        logger.info("Lệnh Reset về cài đặt gốc đã được gửi.")
        time.sleep(1.0) # Chờ cảm biến xử lý lệnh
        
        # Bước 3: Lưu cài đặt để đảm bảo factory reset được áp dụng
        if not self.save_configuration(): # Hàm save_configuration đã bao gồm logic gửi lệnh và chờ
            logger.error("Factory Reset thất bại: Không thể lưu cài đặt sau factory reset.")
            return False
        logger.info("Đã lưu cài đặt sau factory reset.")
        time.sleep(0.5)
        
        # Bước 4: Khởi động lại cảm biến để áp dụng cài đặt factory reset
        if not self.restart_sensor(): # Hàm restart_sensor đã bao gồm logic gửi lệnh và chờ
            logger.error("Factory Reset thất bại: Không thể khởi động lại cảm biến.")
            return False
            
        logger.info("Đã hoàn tất quá trình factory reset và khởi động lại cảm biến.")
        logger.warning("Cảm biến sẽ thực hiện Reset. Cần kết nối lại với baudrate mặc định (thường là 9600) sau một khoảng thời gian.")
        return True

    def read_current_config(self, register_address: int, timeout_s: float = 0.5) -> Optional[int]:
        """
        Gửi lệnh ĐỌC một thanh ghi và chờ phản hồi.
        Lưu ý: Firmware thường trả về giá trị của 4 thanh ghi liên tiếp
        bắt đầu từ địa chỉ được yêu cầu. Phương thức này chỉ trả về giá trị
        của thanh ghi ĐẦU TIÊN (thanh ghi được yêu cầu).

        Args:
            register_address: Địa chỉ thanh ghi cần đọc (ví dụ: REG_BAUD).
            timeout_s: Thời gian chờ tối đa cho phản hồi.

        Returns:
            Giá trị 16-bit của thanh ghi đó nếu đọc thành công, ngược lại None.
            
        Raises:
            ValueError: Nếu phát hiện khả năng không khớp baudrate
        """
        if not self.ser or not self.ser.is_open:
            logger.error("Lỗi đọc thanh ghi: Kết nối serial chưa được thiết lập hoặc đã đóng.")
            return None

        command_bytes = bytes([COMMAND_HEADER_BYTE1, COMMAND_HEADER_BYTE2,
                               REG_READADDR, # Địa chỉ thanh ghi lệnh đọc
                               register_address & 0xFF, # Địa chỉ thanh ghi muốn đọc
                               0x00]) # DATAH luôn là 0x00 cho lệnh đọc

        try:
            self.ser.reset_input_buffer()
            self.ser.write(command_bytes)
            logger.debug(f"Đã gửi lệnh ĐỌC: {' '.join([f'{b:02X}' for b in command_bytes])} từ thanh ghi {hex(register_address)}")
            time.sleep(0.1) # Chờ một chút để cảm biến xử lý và gửi phản hồi

            # Truyền self.ser hiện có cho DataDecoder để tránh mở lại cổng
            # DataDecoder cần phải có khả năng đọc từ một instance serial đã mở
            decoder = HWT905DataDecoder(self.port, self.baudrate, timeout=self.timeout, 
                                        debug=(logger.level <= logging.DEBUG), ser_instance=self.ser)
            
            start_time = time.time()
            found_response = False
            ret_value = None
            baudrate_mismatch_detected = False

            # Đọc gói tin cho đến khi tìm thấy phản hồi đọc thanh ghi hoặc hết timeout
            while (time.time() - start_time) < timeout_s:
                # Đọc gói tin và kiểm tra lỗi
                packet_info = decoder.read_one_packet() 
                
                if packet_info:
                    if packet_info.get("type") == PACKET_TYPE_READ_REGISTER:
                        payload = packet_info["payload"]
                        # Phản hồi đọc thanh ghi có format: REG1L REG1H REG2L REG2H ...
                        # Thanh ghi yêu cầu là REG1, nên cần đọc 2 bytes đầu tiên của payload
                        if len(payload) >= 2: 
                            value = (payload[1] << 8) | payload[0] # Ghép byte cao và byte thấp
                            logger.info(f"Đã đọc thành công giá trị {hex(value)} từ thanh ghi {hex(register_address)}")
                            ret_value = value
                            found_response = True
                            break
                        else:
                            logger.warning(f"Gói phản hồi đọc thanh ghi không đủ dữ liệu cho {hex(register_address)}: Payload={payload.hex()}.")
                            found_response = False
                            break # Thoát vòng lặp nếu gói phản hồi không hợp lệ
                    elif "error" in packet_info and packet_info["error"] == "checksum_mismatch":
                        # Nếu lỗi checksum liên tục, có thể là do baudrate mismatch
                        logger.debug(f"Đã nhận gói lỗi checksum khi đọc thanh ghi: {packet_info.get('raw_packet', b'').hex()}")
                        # Có thể cần một cơ chế thông minh hơn để phát hiện baudrate mismatch thực sự
                        # Ví dụ: nếu có N lỗi checksum liên tiếp trong một khoảng thời gian ngắn
                        # Với mục đích kiểm thử hiện tại, nếu có lỗi checksum thì báo lỗi chung
                    elif "error" in packet_info and packet_info["error"] == "possible_baudrate_mismatch":
                        # Lỗi này đã được HWT905DataDecoder phát hiện
                        baudrate_mismatch_detected = True
                        break
                    else:
                        logger.debug(f"Bỏ qua gói tin không phải phản hồi đọc thanh ghi ({packet_info.get('type_name')}). Raw: {packet_info.get('raw_packet', b'').hex()}")
            
            if baudrate_mismatch_detected:
                raise ValueError("Không khớp baudrate: Không thể đọc dữ liệu từ cảm biến với baudrate hiện tại")
                
            if found_response:
                return ret_value
            else:
                logger.warning(f"Không nhận được phản hồi đọc thanh ghi {hex(register_address)} trong {timeout_s} giây.")
                return None

        except serial.SerialException as e:
            logger.error(f"Lỗi serial khi gửi lệnh ĐỌC tới thanh ghi {hex(register_address)}: {e}")
            return None
        except ValueError as e:
            # Truyền tiếp ValueError để báo lỗi baudrate mismatch
            logger.error(f"{e}")
            raise
        except Exception as e:
            logger.error(f"Lỗi không xác định khi gửi lệnh ĐỌC tới thanh ghi {hex(register_address)}: {e}")
            return None

    def verify_baudrate(self) -> bool:
        """
        Kiểm tra xem baudrate hiện tại có phù hợp với cảm biến hay không bằng cách
        cố gắng đọc một thanh ghi với timeout ngắn.
        
        Returns:
            True nếu baudrate phù hợp (có thể đọc dữ liệu), False nếu không.
        """
        if not self.ser or not self.ser.is_open:
            logger.error("Không thể kiểm tra baudrate: Kết nối serial chưa được thiết lập.")
            return False

        original_timeout = self.ser.timeout
        self.ser.timeout = 0.1  # Short timeout for quicker checking
        
        try:
            # Cố gắng đọc một thanh ghi phổ biến (ví dụ: RSW/MODE) với timeout ngắn
            # Hàm read_current_config sẽ tự động bắt ValueError nếu baudrate mismatch
            result = self.read_current_config(REG_RSW, timeout_s=0.2)
            if result is not None:
                logger.info(f"Baudrate verification succeeded: Read value {hex(result)} from register {hex(REG_RSW)}")
                return True
            else:
                logger.warning("Baudrate verification failed: Could not read from register.")
                return False
        except ValueError as e: # Bắt lỗi từ read_current_config
            logger.warning(f"Baudrate verification failed: {e}")
            return False
        except Exception as e:
            logger.warning(f"Baudrate verification failed with unexpected error: {e}")
            return False
        finally:
            # Khôi phục timeout ban đầu
            self.ser.timeout = original_timeout

    def verify_factory_reset_state(self) -> bool:
        """
        Kiểm tra xem cảm biến đã ở trạng thái mặc định sau khi factory reset chưa.
        Kiểm tra các cài đặt mặc định như:
        - RSW (Output Content): 0x001E (Acc, Gyro, Angle, Mag)
        - RRATE (Output Rate): 0x0006 (10Hz)
        - BAUD: 0x0002 (9600 bps) -- Lưu ý: Hằng số BAUD_RATE_9600 là 0x0002
        
        Returns:
            True nếu cảm biến đã về trạng thái mặc định, False nếu không.
        """
        logger.info("Đang kiểm tra trạng thái của cảm biến sau khi Factory Reset...")
        
        # Giá trị mặc định mong đợi (từ hwt905_constants)
        expected_rsw = DEFAULT_RSW_VALUE
        expected_rate = RATE_OUTPUT_10HZ
        expected_baud = BAUD_RATE_9600 # Đây là mã, không phải giá trị baudrate số

        # Kiểm tra RSW (Output Content)
        rsw_val = self.read_current_config(REG_RSW, timeout_s=0.5)
        if rsw_val is None:
            logger.error("Không thể đọc giá trị RSW sau khi factory reset.")
            return False
        
        # Kiểm tra RRATE (Output Rate)
        rate_val = self.read_current_config(REG_RRATE, timeout_s=0.5)
        if rate_val is None:
            logger.error("Không thể đọc giá trị RRATE sau khi factory reset.")
            return False
            
        # Kiểm tra BAUD
        baud_val = self.read_current_config(REG_BAUD, timeout_s=0.5)
        if baud_val is None:
            logger.error("Không thể đọc giá trị BAUD sau khi factory reset.")
            return False
            
        # So sánh với giá trị mặc định
        if rsw_val != expected_rsw:
            logger.error(f"RSW không đúng giá trị mặc định: {hex(rsw_val)} (mong đợi {hex(expected_rsw)})")
            return False
            
        if rate_val != expected_rate:
            logger.error(f"RRATE không đúng giá trị mặc định: {hex(rate_val)} (mong đợi {hex(expected_rate)})")
            return False
            
        if baud_val != expected_baud:
            logger.error(f"BAUD không đúng giá trị mặc định: {hex(baud_val)} (mong đợi {hex(expected_baud)})")
            return False
            
        logger.info("Cảm biến đã trở về trạng thái mặc định sau khi factory reset!")
        return True