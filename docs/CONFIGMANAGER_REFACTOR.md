# HWT905 Configuration Module

Mô-đun cấu hình đã được tái cấu trúc thành các components độc lập để dễ bảo trì và mở rộng.

## Cấu trúc thư mục

```
src/sensors/config/
├── __init__.py                 # Xuất tất cả components
├── base.py                     # Base class chung cho tất cả components
├── unified_config_manager.py   # Manager tích hợp tất cả components
├── setters/                    # Các phương thức thiết lập cấu hình
│   ├── __init__.py
│   ├── baudrate_setter.py      # Thiết lập baudrate
│   ├── update_rate_setter.py   # Thiết lập tốc độ cập nhật
│   └── output_content_setter.py # Thiết lập nội dung đầu ra
├── operations/                 # Các thao tác cơ bản
│   ├── __init__.py
│   ├── unlock_operations.py    # Mở khóa cảm biến
│   └── save_operations.py      # Lưu cấu hình và khởi động lại
├── reset/                      # Các thao tác reset
│   ├── __init__.py
│   └── factory_reset_operations.py # Factory reset
└── readers/                    # Đọc và kiểm tra cấu hình
    ├── __init__.py
    ├── config_reader.py        # Đọc thanh ghi
    └── config_verifier.py      # Kiểm tra cấu hình
```

## Cách sử dụng

### 1. Sử dụng Unified Config Manager (Khuyến nghị)

```python
from src.sensors.config import HWT905UnifiedConfigManager

# Khởi tạo
config_manager = HWT905UnifiedConfigManager('/dev/ttyUSB0', 9600)

# Kết nối
if config_manager.connect():
    # Thiết lập baudrate
    config_manager.set_baudrate(BAUD_RATE_115200)
    
    # Thiết lập tốc độ cập nhật
    config_manager.set_update_rate(RATE_OUTPUT_50HZ)
    
    # Factory reset
    config_manager.factory_reset()
    
    # Đọc cấu hình
    baud_value = config_manager.read_current_config(REG_BAUD)
    
    # Kiểm tra trạng thái
    is_default = config_manager.verify_factory_reset_state()
```

### 2. Sử dụng các components riêng lẻ

```python
from src.sensors.config.setters import BaudrateSetter
from src.sensors.config.operations import UnlockOperations

# Khởi tạo các components
baudrate_setter = BaudrateSetter('/dev/ttyUSB0', 9600)
unlock_ops = UnlockOperations('/dev/ttyUSB0', 9600)

# Kết nối và thiết lập
if baudrate_setter.connect():
    unlock_ops.set_ser_instance(baudrate_setter.ser)  # Chia sẻ kết nối
    
    unlock_ops.unlock_sensor_for_config()
    baudrate_setter.set_baudrate(BAUD_RATE_115200)
```

### 3. Backward Compatibility

File `hwt905_config_manager.py` gốc vẫn hoạt động bình thường, nhưng sử dụng `HWT905UnifiedConfigManager` bên trong:

```python
from src.sensors.hwt905_config_manager import HWT905ConfigManager

# Vẫn hoạt động như cũ, nhưng sẽ hiển thị warning về deprecated
config_manager = HWT905ConfigManager('/dev/ttyUSB0', 9600)
```

## Lợi ích của cấu trúc mới

1. **Separation of Concerns**: Mỗi component chỉ phụ trách một nhóm chức năng cụ thể
2. **Modularity**: Có thể sử dụng từng component riêng lẻ khi cần
3. **Maintainability**: Dễ bảo trì và sửa lỗi cho từng chức năng
4. **Extensibility**: Dễ thêm chức năng mới mà không ảnh hưởng đến code hiện có
5. **Testing**: Có thể test từng component độc lập
6. **Code Reuse**: Có thể tái sử dụng các component trong các project khác

## Components

### Base (HWT905ConfigBase)
- Quản lý kết nối serial chung
- Cung cấp phương thức `_send_write_command()` cho tất cả components

### Setters
- **BaudrateSetter**: Thiết lập tốc độ baud
- **UpdateRateSetter**: Thiết lập tốc độ cập nhật dữ liệu
- **OutputContentSetter**: Thiết lập nội dung đầu ra và dừng output

### Operations
- **UnlockOperations**: Mở khóa cảm biến để cấu hình
- **SaveOperations**: Lưu cấu hình và khởi động lại cảm biến

### Reset
- **FactoryResetOperations**: Thực hiện factory reset hoàn chình

### Readers
- **ConfigReader**: Đọc giá trị từ thanh ghi
- **ConfigVerifier**: Kiểm tra và xác minh cấu hình

## Migration Guide

Để chuyển từ `HWT905ConfigManager` cũ sang cấu trúc mới:

1. **Không thay đổi gì**: Code hiện tại vẫn hoạt động (với warning)
2. **Sử dụng HWT905UnifiedConfigManager**: Thay thế import và class name
3. **Sử dụng components riêng**: Chỉ import và sử dụng component cần thiết

```python
# Cũ
from src.sensors.hwt905_config_manager import HWT905ConfigManager

# Mới - Unified
from src.sensors.config import HWT905UnifiedConfigManager

# Mới - Specific components
from src.sensors.config.setters import BaudrateSetter
from src.sensors.config.reset import FactoryResetOperations
```
