# src/sensor/hwt905_data_decoder.py

"""
Chứa các hàm để đọc (decode) các gói dữ liệu nhận được từ cảm biến
và chuyển đổi raw data thành giá trị có ý nghĩa.
"""
import serial
import time
import logging
from typing import Dict, Any, Optional

from src.sensors.hwt905_constants import (
    DATA_HEADER_BYTE,
    DATA_PACKET_LENGTH,
    PACKET_TYPE_TIME, PACKET_TYPE_ACC, PACKET_TYPE_GYRO, PACKET_TYPE_ANGLE,
    PACKET_TYPE_MAG, PACKET_TYPE_PORT_STATUS, PACKET_TYPE_PRESSURE,
    PACKET_TYPE_GPS_LONLAT, PACKET_TYPE_GPS_SPEED, PACKET_TYPE_QUATERNION,
    PACKET_TYPE_GPS_ACCURACY, PACKET_TYPE_READ_REGISTER,
    SCALE_ACCELERATION, SCALE_ANGULAR_VELOCITY, SCALE_ANGLE, SCALE_TEMPERATURE,
    SCALE_QUATERNION, SCALE_GPS_ALTITUDE, SCALE_GPS_SPEED, SCALE_GPS_ACCURACY,
    DEFAULT_SERIAL_TIMEOUT, DEFAULT_BAUDRATE
)
from src.sensors.hwt905_protocol import calculate_checksum, is_valid_data_packet 

logger = logging.getLogger(__name__)

class HWT905DataDecoder:
    """
    Lớp để đọc và giải mã các gói dữ liệu từ cảm biến Witmotion HWT905.
    """

    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE,
                 timeout: float = DEFAULT_SERIAL_TIMEOUT, debug: bool = False,
                 ser_instance: Optional[serial.Serial] = None):
        """
        Khởi tạo bộ giải mã dữ liệu HWT905.
        Args:
            port: Cổng serial để kết nối.
            baudrate: Tốc độ baud cho giao tiếp serial.
            timeout: Thời gian chờ đọc serial (giây).
            debug: Kích hoạt logging ở mức DEBUG nếu True.
            ser_instance: Một instance serial.Serial đã được khởi tạo. Nếu cung cấp,
                          lớp sẽ sử dụng instance này thay vì tự mở/đóng cổng.
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = ser_instance # Sử dụng instance serial được cung cấp nếu có

        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            if logger.level > logging.INFO:
                 logger.setLevel(logging.INFO)

        self._packet_buffer = b'' # Buffer để lưu trữ các byte nhận được

    def connect(self) -> bool:
        """
        Thiết lập kết nối serial đến cảm biến nếu chưa có ser_instance.
        Returns:
            True nếu kết nối thành công, False nếu thất bại.
        """
        if self.ser and self.ser.is_open:
            logger.info(f"Kết nối serial trên {self.port} đã được thiết lập.")
            if self.ser.baudrate != self.baudrate:
                logger.warning(f"Baudrate của kết nối hiện tại ({self.ser.baudrate}) không khớp với baudrate yêu cầu ({self.baudrate}). Đang cố gắng đóng và mở lại.")
                self.ser.close()
                self.ser = None

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
        return True # Return True if connection was already open or just established successfully


    def close(self) -> None:
        """Đóng kết nối serial nếu nó được mở bởi instance này."""
        if self.ser and self.ser.is_open:
            # Chỉ đóng cổng nếu instance này tự mở nó (không phải là ser_instance được truyền vào)
            # Hoặc nếu không có cách nào để biết, hãy cảnh báo và đóng.
            logger.info(f"Đang đóng kết nối serial trên {self.port}.")
            self.ser.close()
        self.ser = None

    def read_one_packet(self) -> Optional[Dict[str, Any]]:
        """
        Đọc một gói dữ liệu từ cổng serial và giải mã nó.
        Sử dụng buffer để xử lý các byte nhận được không theo gói hoàn chỉnh.
        Returns:
            Dict[str, Any] chứa dữ liệu đã giải mã hoặc thông tin lỗi, hoặc None nếu không có gói hợp lệ.
        """
        if not self.ser or not self.ser.is_open:
            logger.error("Lỗi đọc gói tin: Kết nối serial chưa được thiết lập hoặc đã đóng.")
            return None

        # Đọc dữ liệu mới vào buffer
        try:
            new_bytes = self.ser.read(self.ser.in_waiting or 1) # Đọc tất cả byte có sẵn hoặc ít nhất 1 byte
            if not new_bytes:
                return None # Không có dữ liệu mới
            self._packet_buffer += new_bytes
        except serial.SerialException as e:
            logger.error(f"Lỗi serial khi đọc dữ liệu: {e}")
            self._packet_buffer = b'' # Xóa buffer để tránh dữ liệu hỏng
            return {"error": "serial_error", "message": str(e)}
        except Exception as e:
            logger.error(f"Lỗi không xác định khi đọc dữ liệu: {e}")
            return {"error": "unknown_error", "message": str(e)}

        # Tìm kiếm và xử lý gói tin trong buffer
        while len(self._packet_buffer) >= DATA_PACKET_LENGTH:
            # Tìm byte header
            header_index = self._packet_buffer.find(bytes([DATA_HEADER_BYTE]))
            
            if header_index == -1:
                # Không tìm thấy header, xóa toàn bộ buffer
                logger.debug("Không tìm thấy header byte trong buffer, xóa buffer.")
                self._packet_buffer = b''
                return None # Quay lại chờ thêm dữ liệu
            
            if header_index > 0:
                # Tìm thấy header nhưng có các byte rác ở phía trước
                garbage_bytes = self._packet_buffer[:header_index]
                self._packet_buffer = self._packet_buffer[header_index:]
                logger.warning(f"Tìm thấy {len(garbage_bytes)} byte rác trước header: {garbage_bytes.hex().upper()}. Đã xóa.")
                # Nếu có nhiều byte rác, có thể là baudrate mismatch
                if len(garbage_bytes) > 50: # Một ngưỡng tùy ý
                    logger.error("Phát hiện số lượng lớn byte rác. Khả năng cao không khớp baudrate!")
                    self._packet_buffer = b'' # Xóa buffer
                    return {"error": "possible_baudrate_mismatch", "raw_bytes": garbage_bytes.hex()}

            # Nếu buffer đủ dài để chứa một gói tin tiềm năng
            if len(self._packet_buffer) >= DATA_PACKET_LENGTH:
                potential_packet = self._packet_buffer[:DATA_PACKET_LENGTH]
                
                if is_valid_data_packet(potential_packet):
                    self._packet_buffer = self._packet_buffer[DATA_PACKET_LENGTH:] # Xóa gói tin đã xử lý khỏi buffer
                    return self._decode_packet(potential_packet)
                else:
                    # Gói tin không hợp lệ (checksum sai hoặc cấu trúc sai)
                    # Xóa byte header đầu tiên và thử lại
                    logger.debug(f"Gói tin không hợp lệ: {potential_packet.hex().upper()}. Xóa byte đầu tiên.")
                    self._packet_buffer = self._packet_buffer[1:] # Xóa byte đầu tiên (đầu header đã tìm thấy)
                    # Không return ở đây, mà tiếp tục vòng lặp while để tìm gói tin hợp lệ tiếp theo
            else:
                # Buffer chưa đủ dài để chứa gói tin hoàn chỉnh sau khi xử lý byte rác/header
                return None # Quay lại chờ thêm dữ liệu

        return None # Không có gói tin hoàn chỉnh nào trong buffer

    def _decode_packet(self, packet_bytes: bytes) -> Dict[str, Any]:
        """
        Giải mã một gói dữ liệu hoàn chỉnh và hợp lệ.
        Args:
            packet_bytes (bytes): Gói dữ liệu 11 byte hợp lệ.
        Returns:
            Dict[str, Any]: Dictionary chứa dữ liệu đã giải mã.
        """
        packet_type = packet_bytes[1]
        payload = packet_bytes[2:DATA_PACKET_LENGTH-1] # 8 bytes payload
        
        decoded_data: Dict[str, Any] = {
            "raw_packet": packet_bytes,
            "header": packet_bytes[0],
            "type": packet_type,
            "type_name": self._get_packet_type_name(packet_type),
            "payload": payload,
            "checksum": packet_bytes[-1]
        }

        try:
            if packet_type == PACKET_TYPE_TIME:
                decoded_data.update(self._decode_time_packet(payload))
            elif packet_type == PACKET_TYPE_ACC:
                decoded_data.update(self._decode_acceleration_packet(payload))
            elif packet_type == PACKET_TYPE_GYRO:
                decoded_data.update(self._decode_angular_velocity_packet(payload))
            elif packet_type == PACKET_TYPE_ANGLE:
                decoded_data.update(self._decode_angle_packet(payload))
            elif packet_type == PACKET_TYPE_MAG:
                decoded_data.update(self._decode_magnetic_packet(payload))
            elif packet_type == PACKET_TYPE_PORT_STATUS:
                decoded_data.update(self._decode_port_status_packet(payload))
            elif packet_type == PACKET_TYPE_PRESSURE:
                decoded_data.update(self._decode_pressure_height_packet(payload))
            elif packet_type == PACKET_TYPE_GPS_LONLAT:
                decoded_data.update(self._decode_gps_lonlat_packet(payload))
            elif packet_type == PACKET_TYPE_GPS_SPEED:
                decoded_data.update(self._decode_gps_speed_packet(payload))
            elif packet_type == PACKET_TYPE_QUATERNION:
                decoded_data.update(self._decode_quaternion_packet(payload))
            elif packet_type == PACKET_TYPE_GPS_ACCURACY:
                decoded_data.update(self._decode_gps_accuracy_packet(payload))
            elif packet_type == PACKET_TYPE_READ_REGISTER:
                decoded_data.update(self._decode_read_register_packet(payload))
            else:
                logger.warning(f"Loại gói tin không xác định: {hex(packet_type)}. Payload: {payload.hex()}")
        except IndexError as e:
            logger.error(f"Lỗi IndexError khi giải mã gói tin loại {hex(packet_type)}: {e}. Payload: {payload.hex()}")
            decoded_data["error"] = "payload_index_error"
        except Exception as e:
            logger.error(f"Lỗi không xác định khi giải mã gói tin loại {hex(packet_type)}: {e}. Payload: {payload.hex()}")
            decoded_data["error"] = "decoding_error"
            
        return decoded_data

    def _get_packet_type_name(self, packet_type: int) -> str:
        """Trả về tên thân thiện của loại gói tin."""
        if packet_type == PACKET_TYPE_TIME: return "TIME"
        if packet_type == PACKET_TYPE_ACC: return "ACCELERATION"
        if packet_type == PACKET_TYPE_GYRO: return "ANGULAR_VELOCITY"
        if packet_type == PACKET_TYPE_ANGLE: return "ANGLE"
        if packet_type == PACKET_TYPE_MAG: return "MAGNETIC_FIELD"
        if packet_type == PACKET_TYPE_PORT_STATUS: return "PORT_STATUS"
        if packet_type == PACKET_TYPE_PRESSURE: return "PRESSURE_HEIGHT"
        if packet_type == PACKET_TYPE_GPS_LONLAT: return "GPS_LON_LAT"
        if packet_type == PACKET_TYPE_GPS_SPEED: return "GPS_SPEED"
        if packet_type == PACKET_TYPE_QUATERNION: return "QUATERNION"
        if packet_type == PACKET_TYPE_GPS_ACCURACY: return "GPS_ACCURACY"
        if packet_type == PACKET_TYPE_READ_REGISTER: return "READ_REGISTER_RESPONSE"
        return "UNKNOWN"

    def _bytes_to_short(self, low_byte: int, high_byte: int) -> int:
        """Chuyển đổi 2 byte thành giá trị short (signed 16-bit integer)."""
        val = (high_byte << 8) | low_byte
        if val & 0x8000:  # Kiểm tra bit dấu (most significant bit)
            val = val - 0x10000 # Chuyển đổi sang số âm nếu là số bù 2
        return val

    # ==========================================================================
    # CÁC HÀM GIẢI MÃ CỤ THỂ CHO TỪNG LOẠI GÓI TIN
    # Tham khảo tài liệu "Protocol Format" trang 9 và các phần "Output" trang 11-27
    # ==========================================================================

    def _decode_time_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin thời gian (0x50)."""
        yy = payload[0]  # Year (20YY)
        mm = payload[1]  # Month
        dd = payload[2]  # Day
        hh = payload[3]  # Hour
        mn = payload[4]  # Minute
        ss = payload[5]  # Second
        ms = self._bytes_to_short(payload[6], payload[7]) # Millisecond (msL, msH)
        
        # Checksum được tính bao gồm 0x55, 0x50, và các byte payload. 
        # Không cần tính lại ở đây vì đã kiểm tra gói tin hợp lệ trước đó.
        
        return {
            "year": 2000 + yy,
            "month": mm,
            "day": dd,
            "hour": hh,
            "minute": mn,
            "second": ss,
            "millisecond": ms
        }

    def _decode_acceleration_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin gia tốc (0x51)."""
        ax_raw = self._bytes_to_short(payload[0], payload[1])
        ay_raw = self._bytes_to_short(payload[2], payload[3])
        az_raw = self._bytes_to_short(payload[4], payload[5])
        temp_raw = self._bytes_to_short(payload[6], payload[7])

        ax = ax_raw / SCALE_ACCELERATION # (g)
        ay = ay_raw / SCALE_ACCELERATION # (g)
        az = az_raw / SCALE_ACCELERATION # (g)
        temperature = temp_raw / SCALE_TEMPERATURE # (C)

        return {
            "acc_x": ax,
            "acc_y": ay,
            "acc_z": az,
            "temperature": temperature
        }

    def _decode_angular_velocity_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin vận tốc góc (0x52)."""
        gx_raw = self._bytes_to_short(payload[0], payload[1])
        gy_raw = self._bytes_to_short(payload[2], payload[3])
        gz_raw = self._bytes_to_short(payload[4], payload[5])
        temp_raw = self._bytes_to_short(payload[6], payload[7]) # Nhiệt độ là chung trong gói này

        gx = gx_raw / SCALE_ANGULAR_VELOCITY # (deg/s)
        gy = gy_raw / SCALE_ANGULAR_VELOCITY # (deg/s)
        gz = gz_raw / SCALE_ANGULAR_VELOCITY # (deg/s)
        temperature = temp_raw / SCALE_TEMPERATURE # (C)

        return {
            "gyro_x": gx,
            "gyro_y": gy,
            "gyro_z": gz,
            "temperature": temperature
        }

    def _decode_angle_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin góc (0x53)."""
        roll_raw = self._bytes_to_short(payload[0], payload[1])
        pitch_raw = self._bytes_to_short(payload[2], payload[3])
        yaw_raw = self._bytes_to_short(payload[4], payload[5])
        temp_raw = self._bytes_to_short(payload[6], payload[7]) # Nhiệt độ là chung trong gói này

        roll = roll_raw / SCALE_ANGLE # (deg)
        pitch = pitch_raw / SCALE_ANGLE # (deg)
        yaw = yaw_raw / SCALE_ANGLE # (deg)
        temperature = temp_raw / SCALE_TEMPERATURE # (C)

        return {
            "angle_roll": roll,
            "angle_pitch": pitch,
            "angle_yaw": yaw,
            "temperature": temperature
        }

    def _decode_magnetic_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin từ trường (0x54)."""
        hx_raw = self._bytes_to_short(payload[0], payload[1])
        hy_raw = self._bytes_to_short(payload[2], payload[3])
        hz_raw = self._bytes_to_short(payload[4], payload[5])
        temp_raw = self._bytes_to_short(payload[6], payload[7]) # Nhiệt độ là chung trong gói này

        hx = hx_raw # (LSB)
        hy = hy_raw # (LSB)
        hz = hz_raw # (LSB)
        temperature = temp_raw / SCALE_TEMPERATURE # (C)

        return {
            "mag_x": hx,
            "mag_y": hy,
            "mag_z": hz,
            "temperature": temperature
        }
    
    def _decode_port_status_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin trạng thái cổng (0x55)."""
        d0_status = self._bytes_to_short(payload[0], payload[1])
        d1_status = self._bytes_to_short(payload[2], payload[3])
        d2_status = self._bytes_to_short(payload[4], payload[5])
        d3_status = self._bytes_to_short(payload[6], payload[7])
        
        return {
            "d0_status": d0_status,
            "d1_status": d1_status,
            "d2_status": d2_status,
            "d3_status": d3_status
        }
        
    def _decode_pressure_height_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin áp suất và độ cao (0x56)."""
        # Áp suất là 32-bit (P0 P1 P2 P3)
        pressure = (payload[3] << 24) | (payload[2] << 16) | \
                   (payload[1] << 8) | payload[0] # (Pa)
        
        # Độ cao là 32-bit (H0 H1 H2 H3)
        height_raw = (payload[7] << 24) | (payload[6] << 16) | \
                     (payload[5] << 8) | payload[4]
        height = height_raw / SCALE_GPS_ALTITUDE # (cm / 10 = m)
        
        return {
            "pressure": pressure,
            "height": height
        }

    def _decode_gps_lonlat_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin vĩ độ và kinh độ GPS (0x57)."""
        # Kinh độ là 32-bit (Lon0 Lon1 Lon2 Lon3)
        longitude_raw = (payload[3] << 24) | (payload[2] << 16) | \
                        (payload[1] << 8) | payload[0]
        # Vĩ độ là 32-bit (Lat0 Lat1 Lat2 Lat3)
        latitude_raw = (payload[7] << 24) | (payload[6] << 16) | \
                       (payload[5] << 8) | payload[4]
        
        # Chuyển đổi từ định dạng dd mm.mmmmm thành decimal degrees
        # dd = value / 10000000
        # mm.mmmmm = (value % 10000000) / 100000
        # lon_deg = int(longitude_raw / 10000000) + ((longitude_raw % 10000000) / 100000) / 60
        # lat_deg = int(latitude_raw / 10000000) + ((latitude_raw % 10000000) / 100000) / 60
        
        # Hoặc đơn giản là chia cho 10^7 để có decimal degrees trực tiếp từ tài liệu
        # Tuy nhiên, tài liệu PDF trang 21-22 nói dd=Lon[31:0]/10000000 và mm.mmmmm=(Lon[31:0]%10000000)/100000
        # Điều này ngụ ý định dạng "ddmm.mmmmm" của NMEA. Cần thực hiện phép chia 60.
        
        # WitMotion thường dùng định dạng decimal degrees * 10^7
        longitude = longitude_raw / 10_000_000.0
        latitude = latitude_raw / 10_000_000.0

        return {
            "gps_longitude": longitude,
            "gps_latitude": latitude
        }

    def _decode_gps_speed_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin tốc độ GPS (0x58)."""
        # Tốc độ mặt đất là 32-bit (GPSV0 GPSV1 GPSV2 GPSV3)
        gps_ground_speed_raw = (payload[3] << 24) | (payload[2] << 16) | \
                               (payload[1] << 8) | payload[0]
        gps_ground_speed = gps_ground_speed_raw / SCALE_GPS_SPEED # (km/h)
        
        # GPS Altitude (m)
        gps_altitude_raw = self._bytes_to_short(payload[4], payload[5])
        gps_altitude = gps_altitude_raw / SCALE_GPS_ALTITUDE # (m)
        
        # GPS Heading (deg)
        gps_heading_raw = self._bytes_to_short(payload[6], payload[7])
        gps_heading = gps_heading_raw / SCALE_TEMPERATURE # Tài liệu nói /100, nhưng nên là /100.0 để có float. HWT905 PDF trang 23 nói /100 cho heading
        
        return {
            "gps_ground_speed": gps_ground_speed,
            "gps_altitude": gps_altitude,
            "gps_heading": gps_heading
        }

    def _decode_quaternion_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin Quaternion (0x59)."""
        q0_raw = self._bytes_to_short(payload[0], payload[1])
        q1_raw = self._bytes_to_short(payload[2], payload[3])
        q2_raw = self._bytes_to_short(payload[4], payload[5])
        q3_raw = self._bytes_to_short(payload[6], payload[7])

        q0 = q0_raw / SCALE_QUATERNION
        q1 = q1_raw / SCALE_QUATERNION
        q2 = q2_raw / SCALE_QUATERNION
        q3 = q3_raw / SCALE_QUATERNION

        return {
            "q0": q0,
            "q1": q1,
            "q2": q2,
            "q3": q3
        }

    def _decode_gps_accuracy_packet(self, payload: bytes) -> Dict[str, Any]:
        """Giải mã gói tin độ chính xác GPS (0x5A)."""
        num_satellites = self._bytes_to_short(payload[0], payload[1]) # SVNUM
        pdop_raw = self._bytes_to_short(payload[2], payload[3]) # PDOP
        hdop_raw = self._bytes_to_short(payload[4], payload[5]) # HDOP
        vdop_raw = self._bytes_to_short(payload[6], payload[7]) # VDOP

        pdop = pdop_raw / SCALE_GPS_ACCURACY
        hdop = hdop_raw / SCALE_GPS_ACCURACY
        vdop = vdop_raw / SCALE_GPS_ACCURACY

        return {
            "gps_num_satellites": num_satellites,
            "gps_pdop": pdop,
            "gps_hdop": hdop,
            "gps_vdop": vdop
        }
        
    def _decode_read_register_packet(self, payload: bytes) -> Dict[str, Any]:
        """
        Giải mã gói tin phản hồi từ lệnh đọc thanh ghi (0x5F).
        Gói tin này chứa giá trị của 4 thanh ghi liên tiếp bắt đầu từ thanh ghi yêu cầu.
        Format: REG1L REG1H REG2L REG2H REG3L REG3H REG4L REG4H
        """
        if len(payload) < 8:
            logger.warning(f"Payload của gói phản hồi đọc thanh ghi quá ngắn ({len(payload)} bytes). Mong đợi 8 bytes.")
            return {"error": "read_register_payload_too_short", "payload_hex": payload.hex()}
        
        reg1_value = self._bytes_to_short(payload[0], payload[1])
        reg2_value = self._bytes_to_short(payload[2], payload[3])
        reg3_value = self._bytes_to_short(payload[4], payload[5])
        reg4_value = self._bytes_to_short(payload[6], payload[7])

        return {
            "reg1_value": reg1_value,
            "reg2_value": reg2_value,
            "reg3_value": reg3_value,
            "reg4_value": reg4_value
        }