# Main Loop Refactor Documentation

## Tổng quan

Việc tách `_main_loop_thread` từ `main.py` ra thành module riêng `src/core/main_loop.py` nhằm cải thiện:

- **Tổ chức code**: Tách logic chính ra khỏi file main để dễ quản lý
- **Khả năng bảo trì**: Dễ debug, test và modify logic xử lý chính
- **Tái sử dụng**: Có thể sử dụng lại MainLoopController cho các mục đích khác
- **Testability**: Dễ dàng test logic xử lý riêng biệt

## Cấu trúc mới

### File: `src/core/main_loop.py`

#### Class `MainLoopController`
- **Mục đích**: Điều khiển vòng lặp chính của ứng dụng IMU
- **Chức năng chính**:
  - Đọc dữ liệu từ cảm biến (thật hoặc mock)
  - Xử lý dữ liệu acceleration
  - Gửi dữ liệu qua MQTT theo các strategy khác nhau
  - Xử lý lỗi và exception

#### Function `create_main_loop_thread()`
- **Mục đích**: Factory function để tạo thread cho vòng lặp chính
- **Tham số**: Tất cả các dependency cần thiết cho vòng lặp
- **Trả về**: Configured threading.Thread object

### Các method quan trọng trong MainLoopController:

1. **`run_main_loop()`**: Entry point chính của vòng lặp
2. **`_determine_effective_buffer_size()`**: Tính toán buffer size dựa trên strategy
3. **`_get_packet_data()`**: Lấy dữ liệu từ cảm biến hoặc mock
4. **`_handle_packet_error()`**: Xử lý lỗi packet
5. **`_process_acceleration_packet()`**: Xử lý packet gia tốc và gửi MQTT

## Thay đổi trong `main.py`

### Trước refactor:
```python
def _main_loop_thread(config_manager, data_decoder, ...):
    # 100+ dòng code logic phức tạp
    pass

# Trong main():
main_loop_thread = threading.Thread(target=_main_loop_thread, args=(...))
```

### Sau refactor:
```python
from src.core.main_loop import create_main_loop_thread

# Trong main():
main_loop_thread = create_main_loop_thread(_running_flag, config_manager, ...)
```

## Lợi ích của refactor

### 1. Separation of Concerns
- `main.py`: Chỉ tập trung vào setup và initialization
- `main_loop.py`: Chỉ tập trung vào logic xử lý dữ liệu

### 2. Improved Readability
- File `main.py` ngắn gọn hơn (từ ~300 dòng xuống ~200 dòng)
- Logic phức tạp được tách ra và có documentation riêng

### 3. Better Error Handling
- Mỗi phần xử lý có method riêng, dễ debug
- Exception handling được tổ chức tốt hơn

### 4. Enhanced Testability
- Có thể test từng method riêng biệt
- Mock dependencies dễ dàng hơn

### 5. Future Extensibility
- Dễ dàng thêm các strategy xử lý mới
- Có thể tạo các variant của MainLoopController

## Cách sử dụng

### Import và khởi tạo:
```python
from src.core.main_loop import create_main_loop_thread
import threading

running_flag = threading.Event()
running_flag.set()

# Tạo thread
main_thread = create_main_loop_thread(
    running_flag=running_flag,
    config_manager=config_manager,
    data_decoder=data_decoder,
    sensor_data_processor=processor,
    mqtt_client=mqtt_client,
    data_compressor=compressor,
    mqtt_message_builder=message_builder,
    app_config=config
)

# Chạy thread
main_thread.start()
```

### Dừng thread:
```python
running_flag.clear()  # Signal để dừng
main_thread.join()    # Đợi thread kết thúc
```

## Testing

Chạy test để đảm bảo refactor thành công:
```bash
python3.11 test_main_loop_refactor.py
```

## Backward Compatibility

Refactor này **hoàn toàn backward compatible**:
- API của ứng dụng không thay đổi
- Cấu hình không thay đổi
- Behavior của ứng dụng giữ nguyên
- Chỉ có cấu trúc code internal thay đổi

## Future Improvements

1. **Add Unit Tests**: Tạo comprehensive test suite cho MainLoopController
2. **Add Configuration Validation**: Validate app_config trước khi chạy
3. **Add Metrics**: Thu thập metrics về performance của main loop
4. **Add Health Checks**: Implement health check mechanism
5. **Add Graceful Shutdown**: Cải thiện quá trình shutdown

---

*Tài liệu này được tạo sau khi hoàn thành việc refactor main_loop_thread vào ngày 5/6/2025*
