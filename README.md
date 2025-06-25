# HWT905 Raspberry Pi Lite - Angle Data Logger

Hệ thống thu thập dữ liệu góc từ cảm biến IMU HWT905 được tối ưu hóa cho Raspberry Pi. 
Phiên bản này tập trung vào việc **chỉ lưu dữ liệu góc** với **rate limiting 200Hz** để giảm dung lượng lưu trữ và tăng hiệu suất.

## Tính Năng Chính

- **Lưu chỉ dữ liệu góc**: Roll, Pitch, Yaw + Temperature
- **Rate limiting**: Tối đa 200Hz (configurable)  
- **Auto file rotation**: Tạo file mới mỗi giờ
- **Auto cleanup**: Xóa dữ liệu cũ tự động
- **Auto port discovery**: Tự động quét và kết nối cổng UART khả dụ
- **MQTT publishing**: Gửi dữ liệu định kỳ
- **Systemd integration**: Tự khởi động và restart
- **CSV format**: Dữ liệu dễ đọc và xử lý
- **Environment config**: Cấu hình qua file .env

## Yêu Cầu Hệ Thống

### Hardware
- **Raspberry Pi** (khuyên dùng Pi 4 hoặc mới hơn)
- **MicroSD Card** ≥ 16GB
- **Cảm biến HWT905** với USB-Serial adapter
- **Kết nối internet** (để cài đặt và gửi dữ liệu)

### Software  
- **Raspberry Pi OS** (Lite hoặc Desktop)
- **Python 3.7+** 
- **Git**

## Cài Đặt Nhanh

### Bước 1: Tải project
```bash
cd ~
git clone <your-repository-url>
cd hwt905-raspi-lite
```

### Bước 2: Cấu hình
```bash
# Copy và chỉnh sửa file cấu hình
cp env.example .env
nano .env
```

**Các cấu hình quan trọng:**
```bash
SENSOR_UART_PORT=/dev/ttyUSB0          # Cổng kết nối cảm biến
SENSOR_AUTO_DISCOVER=true             # Tự động quét cổng nếu cổng chính thất bại
DATA_COLLECTION_RATE_HZ=200           # Tần số lưu dữ liệu (Hz)
STORAGE_BASE_DIR=data                 # Thư mục lưu dữ liệu
STORAGE_FILE_ROTATION_HOURS=1         # Xoay file mỗi X giờ
STORAGE_CLEANUP_DAYS=7                # Xóa dữ liệu sau X ngày
```

### Bước 3: Chạy cài đặt tự động
```bash
chmod +x install.sh
sudo ./install.sh
```

### Bước 4: Khởi động lại (quan trọng!)
```bash
sudo reboot
```

## Output Data Format

File CSV được tạo với format:
```csv
timestamp,angle_roll,angle_pitch,angle_yaw,temperature
1750816666.586,16.37,-2.07,391.17,25.0
1750816666.593,16.43,-2.03,393.49,25.0
...
```

**Với tần số 200Hz:**
- ~200 records/giây
- ~12,000 records trong 60 giây
- ~720,000 records trong 1 giờ
- ~17.3MB/giờ (ước tính)

## Quản Lý Hệ Thống

### Kiểm tra trạng thái
```bash
# Xem log real-time
sudo journalctl -u hwt-app.service -f

# Kiểm tra trạng thái dịch vụ
sudo systemctl status hwt-app.service

# Xem dữ liệu được lưu
ls -la data/
head data/data_*.csv
```

### Quản lý dịch vụ
```bash
# Khởi động lại
sudo systemctl restart hwt-app.service

# Dừng dịch vụ
sudo systemctl stop hwt-app.service

# Khởi động dịch vụ
sudo systemctl start hwt-app.service
```

### Thay đổi cấu hình
```bash
# Chỉnh sửa .env
nano .env

# Khởi động lại để áp dụng
sudo systemctl restart hwt-app.service
```

## Cấu Hình Chi Tiết

### Rate Limiting
```bash
# Trong file .env
DATA_COLLECTION_RATE_HZ=200    # Giới hạn 200Hz
DATA_COLLECTION_RATE_HZ=0      # Disable rate limiting
DATA_COLLECTION_RATE_HZ=400    # Tăng lên 400Hz
```

### Storage Management
```bash
STORAGE_BASE_DIR=data                 # Thư mục lưu dữ liệu  
STORAGE_FILE_ROTATION_HOURS=1         # File mới mỗi giờ
STORAGE_CLEANUP_DAYS=7                # Giữ dữ liệu 7 ngày
```

### Sensor Connection
```bash
SENSOR_UART_PORT=/dev/ttyUSB0         # Cổng kết nối ưu tiên
SENSOR_BAUD_RATE=115200               # Tốc độ baud
SENSOR_AUTO_DISCOVER=true             # Tự động quét cổng khả dụ
```

**Tính năng Auto-Discovery:**
- Khi `SENSOR_AUTO_DISCOVER=true`, hệ thống sẽ tự động quét các cổng UART khả dụ nếu cổng chính thất bại
- Ưu tiên các cổng: `/dev/ttyUSB*`, `/dev/ttyACM*`, `COM*`
- Giúp tránh lỗi khi cổng cũ chưa được giải phóng hoàn toàn sau khi mất kết nối

### MQTT Configuration
```bash
MQTT_BROKER_ADDRESS=your-broker.com
MQTT_BROKER_PORT=1883
MQTT_DATA_TOPIC=sensor/hwt905/angle_data
SENDER_PERIOD_MINUTES=30              # Gửi dữ liệu mỗi 30 phút
```

## Monitoring & Debugging

### Kiểm tra tần số thực tế
```bash
# Xem log rate trong 10 giây qua
sudo journalctl -u hwt-app.service --since "10 seconds ago" | grep "Lưu góc"

# Mong đợi thấy: "Lưu góc: ~200.0Hz"
```

### Test không giới hạn tần số
```bash
# Chạy tạm thời với rate unlimited
DATA_COLLECTION_RATE_HZ=0 python3 main.py
```

### Kiểm tra cảm biến
```bash
# Test raw data từ cảm biến
sudo cat /dev/ttyUSB0

# Kiểm tra cổng kết nối
ls /dev/ttyUSB* /dev/ttyACM*

# Test tính năng auto-discovery
python3 scripts/test_port_scanner.py

# Xem log quét cổng trong hệ thống
sudo journalctl -u hwt-app.service | grep -E "(quét|phát hiện|kết nối)"
```

## Cấu Trúc Dịch Vụ

Hệ thống sử dụng 3 systemd services:

- **hwt-app.service**: Ứng dụng chính (đọc và lưu dữ liệu góc)
- **hwt-sender.timer**: Gửi dữ liệu định kỳ qua MQTT  
- **hwt-cleanup.timer**: Dọn dẹp dữ liệu cũ hàng ngày

```bash
# Xem tất cả timers
systemctl list-timers | grep hwt
```

## Troubleshooting

### Không có dữ liệu
1. Kiểm tra cảm biến: `sudo cat /dev/ttyUSB0`
2. Kiểm tra log: `sudo journalctl -u hwt-app.service`
3. Kiểm tra cấu hình: `grep SENSOR_UART_PORT .env`
4. Test auto-discovery: `python3 scripts/test_port_scanner.py`

### Cổng kết nối không ổn định
1. Bật auto-discovery: `SENSOR_AUTO_DISCOVER=true` trong file .env
2. Kiểm tra các cổng khả dụ: `ls /dev/ttyUSB* /dev/ttyACM*`
3. Xem log quét cổng: `sudo journalctl -u hwt-app.service | grep "quét"`
4. Test thủ công: `python3 scripts/test_port_scanner.py`

### Tần số thấp
1. Test unlimited: `DATA_COLLECTION_RATE_HZ=0 python3 main.py`
2. Kiểm tra CPU: `top`
3. Kiểm tra cảm biến configuration

### Service không start
1. Kiểm tra log: `sudo journalctl -u hwt-app.service --no-pager`
2. Kiểm tra permissions: `ls -la /dev/ttyUSB0`
3. Reboot system

## Performance

**Với cấu hình mặc định (200Hz):**
- CPU usage: ~5-10% (Pi 4)
- Memory usage: ~50MB
- Disk I/O: ~17MB/giờ
- Network: Chỉ khi gửi MQTT

**Khuyến nghị:**
- Pi 4 2GB+ cho ổn định tốt nhất
- SD Card Class 10+ cho I/O performance
- Cấp nguồn ổn định (5V 3A+)