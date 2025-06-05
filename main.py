import logging
import time
import json
import threading

# Import các module và lớp cần thiết
from src.utils.common import load_config
from src.utils.logger_setup import setup_logging
from src.utils.mqtt_message_builder import MQTTMessageBuilder
from src.sensors.hwt905_config_manager import HWT905ConfigManager
from src.sensors.hwt905_data_decoder import HWT905DataDecoder
from src.processing.data_processor import SensorDataProcessor
from src.processing.data_compressor import DataCompressor
from src.mqtt.mqtt_client import MQTTClient
from src.core.main_loop import create_main_loop_thread
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
        app_config = load_config("config/app_config.json") #
    except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
        print(f"FATAL ERROR: Không thể tải file cấu hình app_config.json: {e}")
        exit(1)

    # 2. Thiết lập hệ thống ghi log
    log_config = app_config.get("logging", {}) #
    log_file_path = log_config.get("log_file_path", "logs/application.log") #
    log_level = log_config.get("log_level", "INFO") #
    max_bytes = log_config.get("max_bytes", 10485760) #
    backup_count = log_config.get("backup_count", 5) #

    setup_logging(log_file_path, log_level, max_bytes, backup_count) #
    logger = logging.getLogger(__name__)

    logger.info("Ứng dụng Backend IMU đã khởi động.")
    logger.debug(f"Đã tải cấu hình: {app_config}")

    _running_flag.set() # Đặt cờ running

    # 3. Khởi tạo và thiết lập cảm biến (hoặc mock data)
    use_mock_data = app_config.get("mock_data", False) #
    
    config_manager: Optional[HWT905ConfigManager] = None #
    data_decoder: Optional[HWT905DataDecoder] = None #

    sensor_config = app_config["sensor"] #
    sensor_port = sensor_config["uart_port"] #
    sensor_baudrate = sensor_config["baud_rate"] #
    target_output_rate = sensor_config["default_output_rate_hz"] #
    target_output_content_config = sensor_config["default_output_content"] #
    
    rsw_value = 0 #
    rsw_bit_map = { #
        "time": RSW_TIME_BIT, "acceleration": RSW_ACC_BIT, "angular_velocity": RSW_GYRO_BIT, #
        "angle": RSW_ANGLE_BIT, "magnetic_field": RSW_MAG_BIT, "port_status": RSW_PORT_STATUS_BIT, #
        "atmospheric_pressure_height": RSW_PRESSURE_HEIGHT_BIT, "gnss_data": RSW_GPS_LON_LAT_BIT, #
        "gnss_speed": RSW_GPS_SPEED_BIT, "quaternion": RSW_QUATERNION_BIT, "gnss_accuracy": RSW_GPS_ACCURACY_BIT #
    }
    for key, bit_const in rsw_bit_map.items(): #
        if target_output_content_config.get(key, False): #
            rsw_value |= bit_const #

    if use_mock_data: #
        logger.info("Ứng dụng đang chạy với DỮ LIỆU GIẢ LẬP.")
        app_config["processing"]["dt_sensor_actual"] = app_config["processing"]["dt_sensor_mock"] #
    else:
        logger.info("Ứng dụng đang chạy với CẢM BIẾN THẬT.")
        config_manager = HWT905ConfigManager(port=sensor_port, baudrate=sensor_baudrate, debug=(logger.level <= logging.DEBUG)) #
        data_decoder = HWT905DataDecoder(port=sensor_port, baudrate=sensor_baudrate, debug=(logger.level <= logging.DEBUG)) #

        if not config_manager.connect(): #
            logger.critical("Không thể kết nối với cảm biến. Thoát ứng dụng.")
            _running_flag.clear()
            return
        data_decoder.ser = config_manager.ser #

        try:
            if not config_manager.verify_baudrate(): #
                logger.warning(f"Baudrate hiện tại ({sensor_baudrate}) không khớp hoặc không đọc được. Đang thử factory reset và đặt lại baudrate mặc định.")
                if config_manager.factory_reset(): #
                    logger.info("Factory Reset thành công. Đang kết nối lại với baudrate mặc định (9600).")
                    config_manager.close() #
                    config_manager.baudrate = BAUD_RATE_9600 #
                    data_decoder.baudrate = BAUD_RATE_9600 #
                    if not config_manager.connect(): #
                         logger.critical("Không thể kết nối lại sau Factory Reset. Thoát ứng dụng.")
                         _running_flag.clear()
                         return
                    data_decoder.ser = config_manager.ser #
                    if not config_manager.verify_factory_reset_state(): #
                        logger.error("Cảm biến không ở trạng thái mặc định sau Factory Reset. Vẫn tiếp tục nhưng có thể có vấn đề.")
                else:
                    logger.critical("Factory Reset thất bại. Không thể cấu hình cảm biến. Thoát ứng dụng.")
                    _running_flag.clear()
                    return
            else:
                logger.info(f"Baudrate hiện tại của cảm biến khớp với cài đặt ({sensor_baudrate} bps).")
        except ValueError as e:
            logger.critical(f"Lỗi nghiêm trọng khi kiểm tra baudrate: {e}. Thoát ứng dụng.")
            _running_flag.clear()
            config_manager.close()
            return

        rate_map = { #
            10: RATE_OUTPUT_10HZ, 50: RATE_OUTPUT_50HZ, 100: RATE_OUTPUT_100HZ, 200: RATE_OUTPUT_200HZ #
        }
        rate_const = rate_map.get(target_output_rate, RATE_OUTPUT_100HZ) #
        
        logger.info(f"Đang đặt tốc độ output của cảm biến thành {target_output_rate} Hz và nội dung {hex(rsw_value)}...")
        if config_manager.unlock_sensor_for_config(): #
            if not config_manager.set_update_rate(rate_const): #
                logger.error("Không thể đặt tốc độ output.")
            if not config_manager.set_output_content(rsw_value): #
                logger.error("Không thể đặt nội dung output.")
            if not config_manager.save_configuration(): #
                logger.error("Không thể lưu cấu hình cảm biến.")
        else:
            logger.error("Không thể mở khóa cảm biến để cấu hình. Cấu hình output có thể không được áp dụng.")
        
        app_config["processing"]["dt_sensor_actual"] = 1.0 / target_output_rate #


    # 4. Khởi tạo bộ xử lý dữ liệu nâng cao (SensorDataProcessor)
    processing_config = app_config["processing"] #
    storage_config = app_config.get("data_storage", {"enabled": False}) #
    
    sensor_data_processor = SensorDataProcessor( #
        dt_sensor=processing_config["dt_sensor_actual"], #
        gravity_g=processing_config["gravity_g"], #
        acc_filter_type=processing_config.get("acc_filter_type"), #
        acc_filter_param=processing_config.get("acc_filter_param"), #
        rls_sample_frame_size=processing_config["rls_sample_frame_size"], #
        rls_calc_frame_multiplier=processing_config["rls_calc_frame_multiplier"], #
        rls_filter_q=processing_config["rls_filter_q"], #
        fft_n_points=processing_config["fft_n_points"], #
        fft_min_freq_hz=processing_config["fft_min_freq_hz"], #
        fft_max_freq_hz=processing_config["fft_max_freq_hz"], #
        storage_config=storage_config #
    )

    # 5. Khởi tạo DataCompressor
    compressor_config = app_config["data_compression"] #
    data_compressor = DataCompressor( #
        format=compressor_config["format"], #
        use_zlib=compressor_config["use_zlib"] #
    )

    # 6. Khởi tạo MQTT Message Builder
    mqtt_message_builder = MQTTMessageBuilder()
    
    # 7. Khởi tạo MQTT Client
    mqtt_config = app_config["mqtt"] #
    mqtt_client = MQTTClient( #
        broker_address=mqtt_config["broker_address"], #
        broker_port=mqtt_config["broker_port"], #
        client_id=mqtt_config["client_id"], #
        username=mqtt_config.get("username"), #
        password=mqtt_config.get("password"), #
        keepalive=mqtt_config.get("keepalive", 60), #
        use_tls=mqtt_config.get("use_tls", False) #
    )
    if not mqtt_client.connect(): #
        logger.critical("Không thể kết nối MQTT. Thoát ứng dụng.")
        _running_flag.clear()
        if config_manager: config_manager.close()
        return
    
    # 8. Chạy luồng chính
    logger.info("Bắt đầu luồng đọc-xử lý-gửi dữ liệu...")
    main_loop_thread = create_main_loop_thread(_running_flag, config_manager, data_decoder, sensor_data_processor,
                                             mqtt_client, data_compressor, mqtt_message_builder, app_config)
    main_loop_thread.start() #

    try:
        while _running_flag.is_set(): #
            time.sleep(1) 
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu dừng (Ctrl+C). Đang dừng ứng dụng.")
        _running_flag.clear() #

    main_loop_thread.join() #

    # 9. Dọn dẹp
    logger.info("Đang dọn dẹp tài nguyên...")
    if config_manager: #
        config_manager.close() #
    sensor_data_processor.close() #
    mqtt_client.disconnect() #
    logger.info("Ứng dụng Backend IMU đã dừng.")


if __name__ == '__main__':
    main()