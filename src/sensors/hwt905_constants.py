"""
Hằng số để cấu hình và giao tiếp với cảm biến WitMotion HWT905.
Bao gồm địa chỉ thanh ghi, mã lệnh, giá trị cài đặt, và mã loại gói tin.
Thông tin được tham khảo từ "WIT Standard Communication Protocol.pdf".
"""
import logging

# ==============================================================================
# 1. HEADER BYTES CHO GIAO THỨC
# ==============================================================================
# Header cho lệnh ghi (Write Command Header: FF AA ADDR DATAL DATAH)
COMMAND_HEADER_BYTE1 = 0xFF
COMMAND_HEADER_BYTE2 = 0xAA

# Header cho gói dữ liệu nhận được (Data Packet Header: 55 TYPE PAYLOAD CHECKSUM)
DATA_HEADER_BYTE = 0x55

# ==============================================================================
# 2. ĐỊA CHỈ THANH GHI (REGISTER ADDRESSES - ADDR)
# Dùng cho các lệnh GHI (FF AA ADDR DATAL DATAH) và ĐỌC (FF AA 27 ADDR 00)
# (Theo "Register Address table", trang 21-22 và "Register" trang 1-8 của PDF Protocol)
# ==============================================================================
REG_SAVE = 0x00               # SAVE (Save/Reboot/Reset)
REG_CALSW = 0x01              # CALSW (Calibration Mode)
REG_RSW = 0x02                # RSW (Return data content - Output Content)
REG_RRATE = 0x03              # RRATE (Return data Speed - Output Rate)
REG_BAUD = 0x04               # BAUD (Baud rate)

REG_AXOFFSET = 0x05           # AXOFFSET (X axis Acceleration bias)
REG_AYOFFSET = 0x06           # AYOFFSET (Y axis Acceleration bias)
REG_AZOFFSET = 0x07           # AZOFFSET (Z axis Acceleration bias)
REG_GXOFFSET = 0x08           # GXOFFSET (X axis Angular velocity bias)
REG_GYOFFSET = 0x09           # GYOFFSET (Y axis Angular velocity bias)
REG_GZOFFSET = 0x0A           # GZOFFSET (Z axis Angular velocity bias)
REG_HXOFFSET = 0x0B           # HXOFFSET (X axis Magnetic bias)
REG_HYOFFSET = 0x0C           # HYOFFSET (Y axis Magnetic bias)
REG_HZOFFSET = 0x0D           # HZOFFSET (Z axis Magnetic bias)

REG_D0MODE = 0x0E             # D0MODE (D0 Pin Mode)
REG_D1MODE = 0x0F             # D1MODE (D1 Pin Mode)
REG_D2MODE = 0x10             # D2MODE (D2 Pin Mode)
REG_D3MODE = 0x11             # D3MODE (D3 Pin Mode)

REG_D0PWMH = 0x12             # D0PWMH (D0PWM High-level width)
REG_D1PWMH = 0x13             # D1PWMH (D1PWM High-level width)
REG_D2PWMH = 0x14             # D2PWMH (D2PWM High-level width)
REG_D3PWMH = 0x15             # D3PWMH (D3PWM High-level width)
REG_D0PWMT = 0x16             # D0PWMT (D0PWM Period)
REG_D1PWMT = 0x17             # D1PWMT (D1PWM Period)
REG_D2PWMT = 0x18             # D2PWMT (D2PWM Period)
REG_D3PWMT = 0x19             # D3PWMT (D3PWM Period)

REG_IICADDR = 0x1A            # IICADDR (Device address for I2C and Modbus)
REG_LEDOFF = 0x1B             # LEDOFF (Turn off LED light)

REG_MAGRANGX = 0x1C           # MAGRANGX (Magnetic field X calibration range)
REG_MAGRANGY = 0x1D           # MAGRANGY (Magnetic field Y calibration range)
REG_MAGRANGZ = 0x1E           # MAGRANGZ (Magnetic field Z calibration range)

REG_BANDWIDTH = 0x1F          # BANDWIDTH (Data filtering bandwidth)
REG_GYRORANGE = 0x20          # GYRORANGE (Gyroscope range)
REG_ACCRANGE = 0x21           # ACCRANGE (Accelerometer range)
REG_SLEEP = 0x22              # SLEEP (Sleep/Wake up)
REG_ORIENT = 0x23             # ORIENT (Installation direction)
REG_AXIS6 = 0x24              # AXIS6 (Algorithm transition: 6-axis/9-axis)
REG_FILTK = 0x25              # FILTK (K-value filtering for acceleration)
REG_GPSBAUD = 0x26            # GPSBAUD (GPS Baud Rate)

REG_READADDR = 0x27           # READADDR (Read registers - địa chỉ thanh ghi để gửi lệnh đọc)
REG_ACCFILT = 0x2A            # ACCFILT (Acceleration filtering)
REG_POWONSEND = 0x2D          # POWONSEND (Power-on output)
REG_VERSION = 0x2E            # VERSION (Version number - Read-only)

REG_YYMM = 0x30               # YYMM (Year/Month)
REG_DDHH = 0x31               # DDHH (Day/Hour)
REG_MMSS = 0x32               # MMSS (Minute/Second)
REG_MS = 0x33                 # MS (Millisecond)

# Địa chỉ các thanh ghi dữ liệu đọc được (Read-only registers)
# (Theo "Register Address table", trang 22 và "Protocol Format" trang 9-27 của PDF Protocol)
REG_DATA_ACC = 0x34           # AX, AY, AZ (Acceleration X, Y, Z) - Read 0x34
REG_DATA_GYRO = 0x37          # GX, GY, GZ (Angular velocity X, Y, Z) - Read 0x37
REG_DATA_MAG = 0x3A           # HX, HY, HZ (Magnetic field X, Y, Z) - Read 0x3A
REG_DATA_ANGLE = 0x3D         # Roll, Pitch, Yaw (Angle X, Y, Z) - Read 0x3D
REG_DATA_TEMP = 0x40          # TEMP (Temperature) - Read 0x40
REG_DATA_DSTATUS = 0x41       # D0Status, D1Status, D2Status, D3Status (Port status) - Read 0x41
REG_DATA_PRESSURE = 0x45      # PressureL, PressureH (Air pressure low/high 16 bits) - Read 0x45
REG_DATA_HEIGHT = 0x47        # HeightL, HeightH (Height low/high 16 bits) - Read 0x47
REG_DATA_LONLAT = 0x49        # LonL, LonH, LatL, LatH (Longitude and latitude) - Read 0x49
REG_DATA_GPSHEIGHT = 0x4D     # GPSHeight (GPS Altitude) - Read 0x4D
REG_DATA_GPSYAW = 0x4E        # GPSYaw (GPS Heading) - Read 0x4E
REG_DATA_GPSVL = 0x4F         # GPSVL (GPS round speed low 16 bits) - Read 0x4F
REG_DATA_GPSVH = 0x50         # GPSVH (GPS ground speed high 16 bits) - Read 0x50
REG_DATA_QUAT = 0x51          # Q0, Q1, Q2, Q3 (Quaternion) - Read 0x51
REG_DATA_SVNUM = 0x55          # SVNUM (Number of satellites) - Read 0x55
REG_DATA_PDOP = 0x56          # PDOP (Position accuracy) - Read 0x56
REG_DATA_HDOP = 0x57          # HDOP (Horizontal accuracy) - Read 0x57
REG_DATA_VDOP = 0x58          # VDOP (Vertical accuracy) - Read 0x58

# Các thanh ghi liên quan đến Alarm
REG_DELAYT = 0x59             # DELAYT (Alarm delay)
REG_XMIN = 0x5A               # XMIN (X-axis angle alarm min.)
REG_XMAX = 0x5B               # XMAX (X-axis angle alarm max.)
REG_BATVAL = 0x5C             # BATVAL (Supply voltage)
REG_ALARMPIN = 0x5D           # ALARMPIN (Alarm Pin Mapping)
REG_YMIN = 0x5E               # YMIN (Y-axis alarm min.)
REG_YMAX = 0x5F               # YMAX (Y-axis alarm max.)

REG_GYROCALITHR = 0x61        # GYROCALITHR (Gyro Still Threshold)
REG_ALARMLEVEL = 0x62         # ALARMLEVEL (Angle alarm level)
REG_GYROCALTIME = 0x63        # GYROCALTIME (Gyro auto calibration time)

REG_TRIGTIME = 0x68           # TRIGTIME (Alarm continuous trigger time)
REG_KEY = 0x69                # KEY (Unlock register) - Đã có UNLOCK_FUNC
REG_WERROR = 0x6A             # WERROR (Gyroscope change value)
REG_TIMEZONE = 0x6B           # TIMEZONE (GPS Timezone)
REG_WZTIME = 0x6E             # WZTIME (Angular velocity continuous rest time)
REG_WZSTATIC = 0x6F           # WZSTATIC (Angular velocity integration threshold)
REG_MODDELAY = 0x74           # MODDELAY (485 Data reply delay - for Modbus)
REG_XREFROLL = 0x79           # XREFROLL (Roll angle zero reference)
REG_YREFPITCH = 0x7A          # YREFPITCH (Pitch angle zero reference)
REG_NUMBERID1 = 0x7F          # NUMBERID1 (Device No1-2)
# ... REG_NUMBERID6 = 0x84

# ==============================================================================
# 3. THAM SỐ CỤ THỂ CHO CÁC LỆNH (Dùng với lệnh ghi)
# ==============================================================================
# --- Cho lệnh Mở khóa (Ghi vào thanh ghi KEY, địa chỉ 0x69) ---
# Để mở khóa, ghi giá trị 0xB588 vào thanh ghi KEY (tương đương DATAH=0xB5, DATAL=0x88)
UNLOCK_KEY_VALUE_DATAL = 0x88
UNLOCK_KEY_VALUE_DATAH = 0xB5
# Lệnh đầy đủ: FF AA 69 88 B5

# --- Cho thanh ghi SAVE (REG_SAVE, địa chỉ 0x00) ---
SAVE_CONFIG_VALUE = 0x0000        # Ghi 0x0000 để Lưu cài đặt hiện tại
FACTORY_RESET_VALUE = 0x0001      # Ghi 0x0001 để Khôi phục cài đặt gốc
RESTART_SENSOR_VALUE = 0x00FF     # Ghi 0x00FF để Khởi động lại cảm biến

# --- Cho thanh ghi CALSW (REG_CALSW, địa chỉ 0x01) ---
CALI_MODE_NORMAL = 0x0000
CALI_MODE_ACC_AUTO = 0x0001
CALI_MODE_HEIGHT_RESET = 0x0003
CALI_MODE_SET_HEADING_ZERO = 0x0004
CALI_MODE_MAG_SPHERICAL_FIT = 0x0007
CALI_MODE_SET_ANGLE_REF = 0x0008
CALI_MODE_MAG_DUAL_PLANE = 0x0009

# --- Cho thanh ghi SLEEP (REG_SLEEP, địa chỉ 0x22) ---
SLEEP_MODE_SLEEP = 0x0001
SLEEP_MODE_WAKEUP = 0x0000 # Gửi bất kỳ serial data nào cũng có thể đánh thức cảm biến

# --- Cho thanh ghi ORIENT (REG_ORIENT, địa chỉ 0x23) ---
ORIENT_HORIZONTAL = 0x0000
ORIENT_VERTICAL = 0x0001

# --- Cho thanh ghi AXIS6 (REG_AXIS6, địa chỉ 0x24) ---
ALGORITHM_9AXIS = 0x0000
ALGORITHM_6AXIS = 0x0001

# --- Cho thanh ghi GYROCALTIME (REG_GYROCALTIME, địa chỉ 0x63) ---
# Giá trị là thời gian (ms)
GYROCALTIME_DEFAULT_MS = 1000 # 0x03E8
GYROCALTIME_500MS = 500 # 0x01F4

# ==============================================================================
# 4. MÃ CÀI ĐẶT TỐC ĐỘ BAUD (Giá trị 16-bit để ghi vào thanh ghi BAUD, REG_BAUD 0x04)
# Giá trị thực tế được ghi là phần [3:0] của dữ liệu 16-bit.
# DATAH thường là 0x00
# (Theo "BAUD (Serial baud rate)", trang 37 của PDF Protocol)
# ==============================================================================
BAUD_RATE_4800   = 0x0001
BAUD_RATE_9600   = 0x0002 # Mặc định của cảm biến sau Factory Reset
BAUD_RATE_19200  = 0x0003
BAUD_RATE_38400  = 0x0004
BAUD_RATE_57600  = 0x0005
BAUD_RATE_115200 = 0x0006 # Baudrate khuyến nghị cho tốc độ cao
BAUD_RATE_230400 = 0x0007
BAUD_RATE_460800 = 0x0008 # Chỉ hỗ trợ trên WT931/JY931/HWT606/HWT906
BAUD_RATE_921600 = 0x0009 # Chỉ hỗ trợ trên WT931/JY931/HWT606/HWT906

# ==============================================================================
# 5. MÃ CÀI ĐẶT TỐC ĐỘ OUTPUT (Giá trị 16-bit để ghi vào thanh ghi RRATE, REG_RRATE 0x03)
# Giá trị thực tế được ghi là phần [3:0] của dữ liệu 16-bit.
# DATAH thường là 0x00
# (Theo "RRATE (Output rate)", trang 35-36 của PDF Protocol)
# ==============================================================================
RATE_OUTPUT_0_1HZ  = 0x0001
RATE_OUTPUT_0_5HZ  = 0x0002
RATE_OUTPUT_1HZ    = 0x0003
RATE_OUTPUT_2HZ    = 0x0004
RATE_OUTPUT_5HZ    = 0x0005
RATE_OUTPUT_10HZ   = 0x0006 # Mặc định của cảm biến
RATE_OUTPUT_20HZ   = 0x0007
RATE_OUTPUT_50HZ   = 0x0008
RATE_OUTPUT_100HZ  = 0x0009
RATE_OUTPUT_125HZ  = 0x000A # Không có trong bảng PDF, nhưng có thể tồn tại
RATE_OUTPUT_200HZ  = 0x000B
RATE_OUTPUT_SINGLE = 0x000C  # Output một lần (Single return)
RATE_OUTPUT_NO_RETURN = 0x000D # Không output (No return)

# ==============================================================================
# 6. ĐỊNH NGHĨA BIT CHO THANH GHI NỘI DUNG OUTPUT (REG_RSW, địa chỉ 0x02)
# Giá trị RSW là một số 16-bit (DATAL là 8 bit thấp, DATAH là 8 bit cao).
# Mỗi bit bật/tắt một loại dữ liệu output.
# (Theo "RSW (Output content)", trang 34 của PDF Protocol)
# ==============================================================================
RSW_TIME_BIT            = (1 << 0)   # Output Time data (0x50)
RSW_ACC_BIT             = (1 << 1)   # Output Acceleration data (0x51)
RSW_GYRO_BIT            = (1 << 2)   # Output Angular Velocity data (0x52)
RSW_ANGLE_BIT           = (1 << 3)   # Output Angle data (0x53)
RSW_MAG_BIT             = (1 << 4)   # Output Magnetic Field data (0x54)
RSW_PORT_STATUS_BIT     = (1 << 5)   # Output Port Status data (0x55)
RSW_PRESSURE_HEIGHT_BIT = (1 << 6)   # Output Pressure/Height data (0x56)
RSW_GPS_LON_LAT_BIT     = (1 << 7)   # Output GPS (Latitude/Longitude) data (0x57)
RSW_GPS_SPEED_BIT       = (1 << 8)   # Output GPS Speed data (0x58)
RSW_QUATERNION_BIT      = (1 << 9)   # Output Quaternion data (0x59)
RSW_GPS_ACCURACY_BIT    = (1 << 10)  # Output GPS Satellite/Accuracy data (0x5A)

# Giá trị RSW mặc định theo PDF (trang 34) là 0x001E
# 0x001E = 0b0000000000011110 = ACC | GYRO | ANGLE | MAG
DEFAULT_RSW_VALUE = RSW_ACC_BIT | RSW_GYRO_BIT | RSW_ANGLE_BIT | RSW_MAG_BIT

# Một số giá trị RSW ví dụ khác để dễ sử dụng:
RSW_ONLY_ANGLE_TIME = RSW_ANGLE_BIT | RSW_TIME_BIT
RSW_ALL_IMU = RSW_ACC_BIT | RSW_GYRO_BIT | RSW_ANGLE_BIT | RSW_MAG_BIT | RSW_QUATERNION_BIT
RSW_FULL_OUTPUT = RSW_ALL_IMU | RSW_PORT_STATUS_BIT | RSW_PRESSURE_HEIGHT_BIT | \
                  RSW_GPS_LON_LAT_BIT | RSW_GPS_SPEED_BIT | RSW_GPS_ACCURACY_BIT | RSW_TIME_BIT

RSW_NONE = 0x0000 # Tắt tất cả output qua RSW (ghi 0x0000 vào thanh ghi 0x02)

# ==============================================================================
# 7. MÃ NHẬN DẠNG LOẠI GÓI TIN DỮ LIỆU (Data Packet Type Identifiers)
# Dùng cho việc giải mã gói dữ liệu nhận được (Byte thứ 2 của gói 0x55 TYPE PAYLOAD CHECKSUM)
# (Theo "Protocol Format" và các phần "Output" của PDF Protocol)
# ==============================================================================
PACKET_TYPE_TIME         = 0x50  # Time Output (0x55 0x50 ...)
PACKET_TYPE_ACC          = 0x51  # Acceleration Output (0x55 0x51 ...)
PACKET_TYPE_GYRO         = 0x52  # Angular Velocity Output (0x55 0x52 ...)
PACKET_TYPE_ANGLE        = 0x53  # Angle Output (0x55 0x53 ...)
PACKET_TYPE_MAG          = 0x54  # Magnetic field Output (0x55 0x54 ...)
PACKET_TYPE_PORT_STATUS  = 0x55  # Port Status Output (0x55 0x55 ...)
PACKET_TYPE_PRESSURE     = 0x56  # Air pressure Altitude Output (0x55 0x56 ...)
PACKET_TYPE_GPS_LONLAT   = 0x57  # Latitude and Longitude Output (0x55 0x57 ...)
PACKET_TYPE_GPS_SPEED    = 0x58  # GPS data Output (ground speed) (0x55 0x58 ...)
PACKET_TYPE_QUATERNION   = 0x59  # Quaternion Output (0x55 0x59 ...)
PACKET_TYPE_GPS_ACCURACY = 0x5A  # GPS Positioning accuracy Output (0x55 0x5A ...)
PACKET_TYPE_READ_REGISTER = 0x5F # Phản hồi từ lệnh đọc thanh ghi (0x55 0x5F ...)

# ==============================================================================
# 8. CÁC HẰNG SỐ CHUYỂN ĐỔI VÀ KHÁC
# ==============================================================================
DEFAULT_SERIAL_TIMEOUT = 1.0 # Thời gian chờ đọc serial mặc định (giây)
DEFAULT_BAUDRATE = 9600   # Tốc độ baudrate mặc định của cảm biến sau Factory Reset
DATA_PACKET_LENGTH = 11   # Chiều dài của một gói dữ liệu (HEADER + TYPE + 8 BYTES PAYLOAD + CHECKSUM)
COMMAND_PACKET_LENGTH = 5 # Chiều dài của một gói lệnh ghi (HEADER + ADDR + DATAL + DATAH)

# Scale factors (hệ số chuyển đổi) từ raw data sang giá trị thực
# Các giá trị này được lấy từ phần "Calculated formular" của các loại output trong PDF
SCALE_ACCELERATION = 32768.0 / 16.0 # 32768 LSB = 16g
SCALE_ANGULAR_VELOCITY = 32768.0 / 2000.0 # 32768 LSB = 2000 deg/s
SCALE_ANGLE = 32768.0 / 180.0 # 32768 LSB = 180 deg
SCALE_TEMPERATURE = 100.0 # Raw value / 100 = Celsius
SCALE_QUATERNION = 32768.0 # Raw value / 32768 = Quaternion component (range -1 to 1)
SCALE_GPS_ALTITUDE = 10.0 # Raw value / 10 = meters
SCALE_GPS_SPEED = 1000.0 # Raw value / 1000 = km/h
SCALE_GPS_ACCURACY = 100.0 # Raw value / 100 = accuracy value (e.g., PDOP)


logger_constants = logging.getLogger(__name__)
logger_constants.debug("Hằng số cho HWT905 đã được nạp.")