import logging
import time
import json
import threading
from queue import Queue

# Import các module và lớp cần thiết
from src.utils.common import load_config
from src.utils.logger_setup import setup_logging
from src.sensors.hwt905_config_manager import HWT905ConfigManager
from src.sensors.hwt905_data_decoder import HWT905DataDecoder
from src.processing.data_processor import SensorDataProcessor
from src.storage.storage_manager import StorageManager
from src.core.async_data_manager import SerialReaderThread, DecoderThread, ProcessorThread, MqttPublisherThread
from src.sensors.hwt905_constants import (
    BAUD_RATE_9600, RATE_OUTPUT_200HZ, RATE_OUTPUT_100HZ, RATE_OUTPUT_50HZ, RATE_OUTPUT_10HZ,
    RSW_ACC_BIT, RSW_GYRO_BIT, RSW_ANGLE_BIT, RSW_MAG_BIT,
    RSW_TIME_BIT, RSW_PRESSURE_HEIGHT_BIT, RSW_GPS_LON_LAT_BIT,
    RSW_GPS_SPEED_BIT, RSW_QUATERNION_BIT, RSW_GPS_ACCURACY_BIT, RSW_PORT_STATUS_BIT
)
from typing import Optional

# Cờ để điều khiển vòng lặp chính
_running_flag = threading.Event()


def main():
    # 1. Tải cấu hình ứng dụng
    try:
        app_config = load_config("config/app_config.json")
    except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
        print(f"FATAL ERROR: Không thể tải file cấu hình app_config.json: {e}")
        exit(1)

    # 2. Thiết lập hệ thống ghi log
    log_config = app_config.get("logging", {})
    log_file_path = log_config.get("log_file_path", "logs/application.log")
    log_level = log_config.get("log_level", "INFO")
    max_bytes = log_config.get("max_bytes", 10485760)
    backup_count = log_config.get("backup_count", 5)

    setup_logging(log_file_path, log_level, max_bytes, backup_count)
    logger = logging.getLogger(__name__)

    logger.info("Ứng dụng Backend IMU đã khởi động.")
    logger.debug(f"Đã tải cấu hình: {app_config}")

    _running_flag.set()

    # 3. Đọc cấu hình điều khiển quy trình
    process_control_config = app_config.get("process_control", {})
    decoding_enabled = process_control_config.get("decoding", True)
    # Các cờ khác hiện không dùng trong pipeline bất đồng bộ mới, nhưng giữ lại để tương thích
    processing_enabled = process_control_config.get("processing", True)
    mqtt_sending_enabled = process_control_config.get("mqtt_sending", True)
    
    logger.info(f"Cấu hình quy trình: Decoding={decoding_enabled}, Processing={processing_enabled}, MQTT Sending={mqtt_sending_enabled}")

    # 4. Khởi tạo và thiết lập cảm biến
    config_manager: Optional[HWT905ConfigManager] = None
    data_decoder: Optional[HWT905DataDecoder] = None

    sensor_config = app_config["sensor"]
    sensor_port = sensor_config["uart_port"]
    sensor_baudrate = sensor_config["baud_rate"]
    target_output_rate = sensor_config["default_output_rate_hz"]
    target_output_content_config = sensor_config["default_output_content"]
    
    rsw_value = 0
    rsw_bit_map = {
        "time": RSW_TIME_BIT, "acceleration": RSW_ACC_BIT, "angular_velocity": RSW_GYRO_BIT,
        "angle": RSW_ANGLE_BIT, "magnetic_field": RSW_MAG_BIT, "port_status": RSW_PORT_STATUS_BIT,
        "atmospheric_pressure_height": RSW_PRESSURE_HEIGHT_BIT, "gnss_data": RSW_GPS_LON_LAT_BIT,
        "gnss_speed": RSW_GPS_SPEED_BIT, "quaternion": RSW_QUATERNION_BIT, "gnss_accuracy": RSW_GPS_ACCURACY_BIT
    }
    for key, bit_const in rsw_bit_map.items():
        if target_output_content_config.get(key, False):
            rsw_value |= bit_const

    logger.info("Ứng dụng đang chạy với CẢM BIẾN THẬT.")
    config_manager = HWT905ConfigManager(port=sensor_port, baudrate=sensor_baudrate, debug=(logger.level <= logging.DEBUG))
    data_decoder = HWT905DataDecoder(port=sensor_port, baudrate=sensor_baudrate, debug=(logger.level <= logging.DEBUG))

    if not config_manager.connect():
        logger.critical("Không thể kết nối với cảm biến. Thoát ứng dụng.")
        return
    data_decoder.ser = config_manager.ser

    try:
        if not config_manager.verify_baudrate():
            logger.warning(f"Baudrate hiện tại ({sensor_baudrate}) không khớp hoặc không đọc được. Đang thử factory reset và đặt lại baudrate mặc định.")
            if config_manager.factory_reset():
                logger.info("Factory Reset thành công. Đang kết nối lại với baudrate mặc định (9600).")
                config_manager.close()
                config_manager.baudrate = BAUD_RATE_9600
                data_decoder.baudrate = BAUD_RATE_9600
                if not config_manager.connect():
                     logger.critical("Không thể kết nối lại sau Factory Reset. Thoát ứng dụng.")
                     return
                data_decoder.ser = config_manager.ser
                if not config_manager.verify_factory_reset_state():
                    logger.error("Cảm biến không ở trạng thái mặc định sau Factory Reset. Vẫn tiếp tục nhưng có thể có vấn đề.")
            else:
                logger.critical("Factory Reset thất bại. Không thể cấu hình cảm biến. Thoát ứng dụng.")
            return
        else:
            logger.info(f"Baudrate hiện tại của cảm biến khớp với cài đặt ({sensor_baudrate} bps).")
    except ValueError as e:
        logger.critical(f"Lỗi nghiêm trọng khi kiểm tra baudrate: {e}. Thoát ứng dụng.")
        config_manager.close()
        return

    logger.info(f"Đang đặt tốc độ output của cảm biến thành {target_output_rate} Hz và nội dung {hex(rsw_value)}...")
    if config_manager.unlock_sensor_for_config():
        rate_map = {10: RATE_OUTPUT_10HZ, 50: RATE_OUTPUT_50HZ, 100: RATE_OUTPUT_100HZ, 200: RATE_OUTPUT_200HZ}
        rate_const = rate_map.get(target_output_rate, RATE_OUTPUT_100HZ)
        if not config_manager.set_update_rate(rate_const): logger.error("Không thể đặt tốc độ output.")
        if not config_manager.set_output_content(rsw_value): logger.error("Không thể đặt nội dung output.")
        if not config_manager.save_configuration(): logger.error("Không thể lưu cấu hình cảm biến.")
    else:
        logger.error("Không thể mở khóa cảm biến để cấu hình.")
    
    app_config["processing"]["dt_sensor_actual"] = 1.0 / target_output_rate

    # 5. Khởi tạo các thành phần dựa trên cấu hình
    storage_config = app_config.get("data_storage", {"enabled": False})
    
    decoded_storage_manager: Optional[StorageManager] = None
    if decoding_enabled and storage_config.get("enabled", False):
        logger.info("Khởi tạo StorageManager cho dữ liệu DECODED.")
        decoded_storage_manager = StorageManager(
            storage_config,
            data_type="decoded",
            fields_to_write=['acc_x', 'acc_y', 'acc_z']
        )

    sensor_data_processor: Optional[SensorDataProcessor] = None
    processed_storage_manager: Optional[StorageManager] = None
    if processing_enabled:
        logger.info("Khởi tạo SensorDataProcessor.")
        processing_config = app_config["processing"]
        sensor_data_processor = SensorDataProcessor(
            dt_sensor=processing_config["dt_sensor_actual"],
            gravity_g=processing_config["gravity_g"],
            acc_filter_type=processing_config.get("acc_filter_type"),
            acc_filter_param=processing_config.get("acc_filter_param"),
            rls_sample_frame_size=processing_config["rls_sample_frame_size"],
            rls_calc_frame_multiplier=processing_config["rls_calc_frame_multiplier"],
            rls_filter_q=processing_config["rls_filter_q"],
            fft_n_points=processing_config["fft_n_points"],
            fft_min_freq_hz=processing_config["fft_min_freq_hz"],
            fft_max_freq_hz=processing_config["fft_max_freq_hz"]
        )
        if storage_config.get("enabled", False):
            logger.info("Khởi tạo StorageManager cho dữ liệu PROCESSED.")
            
            # Chỉ định các cột cần ghi cho file processed_data.csv
            processed_fields_to_write = [
                'vel_x', 'vel_y', 'vel_z',
                'disp_x', 'disp_y', 'disp_z',
                'dominant_freq_x', 'dominant_freq_y', 'dominant_freq_z'
            ]
            
            processed_storage_manager = StorageManager(
                storage_config,
                data_type="processed",
                fields_to_write=processed_fields_to_write
            )

    # 6. Thiết lập pipeline bất đồng bộ 3 (hoặc 4) luồng
    raw_data_queue = Queue(maxsize=8192)
    decoded_data_queue = Queue(maxsize=8192) if processing_enabled else None
    mqtt_queue = Queue(maxsize=8192) if mqtt_sending_enabled else None

    # Luồng 1: Đọc từ Serial
    reader_thread = SerialReaderThread(data_decoder, raw_data_queue, _running_flag)
    
    # Luồng 2: Giải mã và lưu dữ liệu giải mã
    decoder_thread = DecoderThread(
        data_decoder=data_decoder,
        raw_data_queue=raw_data_queue,
        decoded_data_queue=decoded_data_queue,
        running_flag=_running_flag,
        decoded_storage_manager=decoded_storage_manager
    )

    # Luồng 3: Xử lý và lưu dữ liệu xử lý (chỉ khởi tạo nếu processing được bật)
    processor_thread = None
    if processing_enabled and sensor_data_processor:
        processor_thread = ProcessorThread(
            decoded_data_queue=decoded_data_queue,
            running_flag=_running_flag,
            sensor_data_processor=sensor_data_processor,
            processed_storage_manager=processed_storage_manager,
            mqtt_queue=mqtt_queue
        )

    # Luồng 4: Gửi dữ liệu qua MQTT (chỉ khởi tạo nếu được bật)
    mqtt_publisher_thread = None
    if mqtt_sending_enabled and mqtt_queue:
        mqtt_publisher_thread = MqttPublisherThread(
            mqtt_queue=mqtt_queue,
            running_flag=_running_flag
        )

    # 7. Chạy các luồng
    logger.info("Bắt đầu các luồng đọc, giải mã và xử lý bất đồng bộ...")
    reader_thread.start()
    decoder_thread.start()
    if processor_thread:
        processor_thread.start()
    if mqtt_publisher_thread:
        mqtt_publisher_thread.start()

    try:
        # Vòng lặp chính của chương trình chỉ cần giữ cho nó sống và chờ tín hiệu dừng
        while _running_flag.is_set():
            time.sleep(1) 
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu dừng (Ctrl+C). Đang dừng ứng dụng.")
    finally:
        _running_flag.clear()

    # 8. Đợi các luồng kết thúc
    logger.info("Đang đợi các luồng kết thúc...")
    reader_thread.join()
    decoder_thread.join()
    if processor_thread:
        processor_thread.join()
    if mqtt_publisher_thread:
        mqtt_publisher_thread.join()
    
    # Đợi cho queue được xử lý hết
    raw_data_queue.join()
    if decoded_data_queue:
        decoded_data_queue.join()
    if mqtt_queue:
        mqtt_queue.join()
    logger.info("Hàng đợi đã được xử lý xong.")

    # 9. Dọn dẹp
    logger.info("Đang dọn dẹp tài nguyên...")
    if config_manager:
        config_manager.close() # Thao tác này cũng sẽ đóng cổng serial trong data_decoder
    if decoded_storage_manager:
        decoded_storage_manager.close()
    if processed_storage_manager:
        processed_storage_manager.close()
    logger.info("Ứng dụng Backend IMU đã dừng.")


if __name__ == '__main__':
    main()