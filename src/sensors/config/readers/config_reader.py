"""
Configuration reader for HWT905 sensor.
"""
import time
import logging
from typing import Optional
from src.sensors.config.base import HWT905ConfigBase
from src.sensors.hwt905_constants import (
    COMMAND_HEADER_BYTE1, COMMAND_HEADER_BYTE2,
    REG_READADDR, PACKET_TYPE_READ_REGISTER
)
from src.sensors.hwt905_data_decoder import HWT905DataDecoder
import serial

logger = logging.getLogger(__name__)

class ConfigReader(HWT905ConfigBase):
    """
    Lớp để đọc cấu hình hiện tại của cảm biến HWT905.
    """
    
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
                               REG_READADDR,  # Địa chỉ thanh ghi lệnh đọc
                               register_address & 0xFF,  # Địa chỉ thanh ghi muốn đọc
                               0x00])  # DATAH luôn là 0x00 cho lệnh đọc

        try:
            self.ser.reset_input_buffer()
            self.ser.write(command_bytes)
            logger.debug(f"Đã gửi lệnh ĐỌC: {' '.join([f'{b:02X}' for b in command_bytes])} từ thanh ghi {hex(register_address)}")
            time.sleep(0.1)  # Chờ một chút để cảm biến xử lý và gửi phản hồi

            # Truyền self.ser hiện có cho DataDecoder để tránh mở lại cổng
            decoder = HWT905DataDecoder(debug=(logger.level <= logging.DEBUG), ser_instance=self.ser)
            
            start_time = time.time()
            found_response = False
            ret_value = None
            baudrate_mismatch_detected = False

            # Đọc gói tin cho đến khi tìm thấy phản hồi đọc thanh ghi hoặc hết timeout
            while (time.time() - start_time) < timeout_s:
                packet_info = decoder.read_one_packet() 
                
                if packet_info:
                    if packet_info.get("type") == PACKET_TYPE_READ_REGISTER:
                        payload = packet_info["payload"]
                        # Phản hồi đọc thanh ghi có format: REG1L REG1H REG2L REG2H ...
                        # Thanh ghi yêu cầu là REG1, nên cần đọc 2 bytes đầu tiên của payload
                        if len(payload) >= 2: 
                            value = (payload[1] << 8) | payload[0]  # Ghép byte cao và byte thấp
                            logger.info(f"Đã đọc thành công giá trị {hex(value)} từ thanh ghi {hex(register_address)}")
                            ret_value = value
                            found_response = True
                            break
                        else:
                            logger.warning(f"Gói phản hồi đọc thanh ghi không đủ dữ liệu cho {hex(register_address)}: Payload={payload.hex()}.")
                            found_response = False
                            break
                    elif "error" in packet_info and packet_info["error"] == "checksum_mismatch":
                        logger.debug(f"Đã nhận gói lỗi checksum khi đọc thanh ghi: {packet_info.get('raw_packet', b'').hex()}")
                    elif "error" in packet_info and packet_info["error"] == "possible_baudrate_mismatch":
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
            logger.error(f"{e}")
            raise
        except Exception as e:
            logger.error(f"Lỗi không xác định khi gửi lệnh ĐỌC tới thanh ghi {hex(register_address)}: {e}")
            return None
