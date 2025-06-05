# MQTT Message Structure Configuration

## Mô tả
Dự án đã được tái cấu trúc để tách riêng phần xây dựng cấu trúc MQTT message ra khỏi file `main.py`. Điều này giúp code dễ bảo trì hơn và có thể cấu hình linh hoạt.

## Các file đã thêm/sửa đổi

### 1. `config/mqtt_message_config.json`
File cấu hình định nghĩa cấu trúc message MQTT:
- **message_structure**: Mô tả các field và kiểu dữ liệu
- **message_templates**: Template cho từng chiến lược gửi dữ liệu
  - `batch`: Gửi nhiều data points cùng lúc
  - `continuous`: Gửi từng data point
  - `batch_average`: Gửi dữ liệu trung bình của một batch

### 2. `src/utils/mqtt_message_builder.py`
Module chứa class `MQTTMessageBuilder` với các chức năng:
- `create_data_point()`: Tạo data point từ kết quả sensor processor
- `build_batch_message()`: Xây dựng message cho strategy "batch"
- `build_continuous_message()`: Xây dựng message cho strategy "continuous"
- `build_batch_average_message()`: Xây dựng message cho strategy "batch_average"
- `build_message()`: Method tổng hợp theo strategy

### 3. `main.py`
Đã được cập nhật để:
- Import `MQTTMessageBuilder`
- Khởi tạo instance của builder
- Sử dụng builder thay vì hardcode cấu trúc message
- Truyền builder vào main loop thread

## Lợi ích

1. **Tách biệt logic**: Cấu trúc message được tách khỏi logic chính
2. **Dễ cấu hình**: Có thể thay đổi cấu trúc message qua file JSON
3. **Tái sử dụng**: Module có thể được sử dụng ở các phần khác của ứng dụng
4. **Dễ test**: Logic xây dựng message có thể được test riêng biệt
5. **Mở rộng**: Dễ dàng thêm các strategy mới

## Cách sử dụng

```python
from src.utils.mqtt_message_builder import MQTTMessageBuilder

# Khởi tạo
builder = MQTTMessageBuilder()

# Tạo data point
data_point = builder.create_data_point(processed_results, timestamp)

# Xây dựng message theo strategy
message = builder.build_message("batch", [data_point1, data_point2])
```

## Cấu trúc message output

### Batch/Continuous:
```json
{
  "metadata": {
    "source": "HWT905_RasPi",
    "strategy": "batch",
    "sample_count": 3,
    "start_time": 1649097918.762,
    "end_time": 1649097918.965
  },
  "data_points": [...]
}
```

### Batch Average:
```json
{  
  "metadata": {
    "source": "HWT905_RasPi",
    "strategy": "batch_average", 
    "original_sample_count": 20,
    "start_time": 1649097918.762,
    "end_time": 1649097918.965
  },
  "data_averaged": {...}
}
```

## Thay đổi cấu hình

Để thay đổi cấu trúc message, chỉnh sửa file `config/mqtt_message_config.json` và restart ứng dụng.
