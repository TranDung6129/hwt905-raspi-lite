# main.py

import logging
import time
import json
import threading
import random # Để tạo dữ liệu giả lập
import numpy as np # Để tạo dữ liệu giả lập và các mảng

# Import các module và lớp cần thiết
from src.utils.common import load_config
from src.utils.logger_setup import setup_logging
from src.sensors.hwt905_config_manager import HWT905ConfigManager
from src.sensors.hwt905_data_decoder import HWT905DataDecoder
from src.processing.data_processor import SensorDataProcessor
from src.processing.data_compressor import DataCompressor
from src.mqtt.mqtt_client import MQTTClient
from src.sensors.hwt905_constants import (
    BAUD_RATE_9600, RATE_OUTPUT_200HZ, RATE_OUTPUT_100HZ, RATE_OUTPUT_50HZ, RATE_OUTPUT_10HZ,
    PACKET_TYPE_ACC, # Chỉ quan tâm gói gia tốc để xử lý
    RSW_ACC_BIT, RSW_GYRO_BIT, RSW_ANGLE_BIT, RSW_MAG_BIT,
    RSW_TIME_BIT, RSW_PRESSURE_HEIGHT_BIT, RSW_GPS_LON_LAT_BIT,
    RSW_GPS_SPEED_BIT, RSW_QUATERNION_BIT, RSW_GPS_ACCURACY_BIT, RSW_PORT_STATUS_BIT
)
from typing import Optional, Dict, Any

# Cờ để điều khiển vòng lặp chính
_running_flag = threading.Event()

def _generate_mock_acc_data(time_elapsed: float) -> Dict[str, Any]:
    """
    Tạo một gói dữ liệu gia tốc giả lập (tương tự như từ HWT905DataDecoder).
    """
    # Gia tốc (dao động xung quanh 0, trục Z xung quanh 1g)
    acc_x = 0.1 * np.sin(2 * np.pi * 1 * time_elapsed) + random.uniform(-0.01, 0.01)
    acc_y = 0.05 * np.cos(2 * np.pi * 0.5 * time_elapsed) + random.uniform(-0.01, 0.01)
    acc_z = 1.0 + 0.02 * np.sin(2 * np.pi * 2 * time_elapsed) + random.uniform(-0.01, 0.01)
    
    # Mô phỏng cấu trúc trả về của data_decoder
    return {
        "raw_packet": b'', # Giả lập gói raw
        "header": 0x55,
        "type": PACKET_TYPE_ACC,
        "type_name": "ACCELERATION",
        "payload": b'',
        "checksum": 0x00,
        "acc_x": acc_x,
        "acc_y": acc_y,
        "acc_z": acc_z,
        "temperature": 25.0 + random.uniform(-1,1),
    }

def _main_loop_thread(config_manager: Optional[HWT905ConfigManager], 
                      data_decoder: Optional[HWT905DataDecoder], 
                      sensor_data_processor: SensorDataProcessor,
                      mqtt_client: MQTTClient,
                      data_compressor: DataCompressor,
                      app_config: dict):
    """
    Luồng chính để đọc, xử lý và gửi dữ liệu cảm biến.
    """
    logger = logging.getLogger(__name__ + ".MainLoop")
    logger.info("Luồng chính đã bắt đầu.")

    processed_data_buffer = [] # Buffer để nhóm dữ liệu trước khi gửi MQTT
    buffer_size = app_config["processing"]["data_buffer_size"]
    
    use_mock_data = app_config.get("mock_data", False)
    mock_interval_s = app_config["processing"]["dt_sensor_mock"] # Khoảng thời gian giữa các mẫu mock
    mock_time_elapsed = 0.0 # Để tạo dữ liệu giả lập

    while _running_flag.is_set():
        try:
            packet_info = None
            if use_mock_data:
                # Tạo dữ liệu giả lập
                packet_info = _generate_mock_acc_data(mock_time_elapsed)
                mock_time_elapsed += mock_interval_s
                time.sleep(mock_interval_s) # Giả lập độ trễ nhận data
            else:
                # Đọc gói tin từ cảm biến thật
                if not data_decoder:
                    logger.error("Data Decoder chưa được khởi tạo cho cảm biến thật.")
                    _running_flag.clear()
                    break
                packet_info = data_decoder.read_one_packet()
                # time.sleep(0.001) # Có thể bỏ qua nếu tốc độ dữ liệu đủ cao và read() là blocking

            if packet_info:
                if "error" in packet_info:
                    logger.warning(f"Lỗi gói tin từ cảm biến: {packet_info['message']} (Gói raw: {packet_info.get('raw_packet', b'').hex()})")
                    if packet_info["error"] == "possible_baudrate_mismatch":
                        logger.error("Lỗi Baudrate nghiêm trọng. Đang dừng luồng chính.")
                        _running_flag.clear() # Dừng vòng lặp
                elif packet_info.get("type") == PACKET_TYPE_ACC: # Chỉ xử lý gói gia tốc
                    # Lấy gia tốc thô (đơn vị g)
                    accX = packet_info.get("acc_x")
                    accY = packet_info.get("acc_y")
                    accZ = packet_info.get("acc_z")
                    
                    if accX is not None and accY is not None and accZ is not None:
                        # Xử lý dữ liệu bằng SensorDataProcessor
                        processed_results = sensor_data_processor.process_new_sample(accX, accY, accZ)
                        
                        if processed_results and processed_results.get("rls_warmed_up", False):
                            # Thêm thời gian vào kết quả xử lý
                            current_timestamp = time.time() # Unix timestamp
                            processed_results["timestamp"] = current_timestamp
                            
                            # Lấy mẫu cuối cùng của mỗi mảng kết quả từ RLS/Filter để giảm kích thước payload MQTT
                            data_point_for_mqtt = {
                                "ts": processed_results["timestamp"],
                                "acc_x_filtered": processed_results["acc_x_filtered"][-1] if processed_results["acc_x_filtered"].size > 0 else 0,
                                "acc_y_filtered": processed_results["acc_y_filtered"][-1] if processed_results["acc_y_filtered"].size > 0 else 0,
                                "acc_z_filtered": processed_results["acc_z_filtered"][-1] if processed_results["acc_z_filtered"].size > 0 else 0,
                                "vel_x": processed_results["vel_x"][-1] if processed_results["vel_x"].size > 0 else 0,
                                "vel_y": processed_results["vel_y"][-1] if processed_results["vel_y"].size > 0 else 0,
                                "vel_z": processed_results["vel_z"][-1] if processed_results["vel_z"].size > 0 else 0,
                                "disp_x": processed_results["disp_x"][-1] if processed_results["disp_x"].size > 0 else 0,
                                "disp_y": processed_results["disp_y"][-1] if processed_results["disp_y"].size > 0 else 0,
                                "disp_z": processed_results["disp_z"][-1] if processed_results["disp_z"].size > 0 else 0,
                                "dominant_freq_x": processed_results.get("dominant_freq_x", 0),
                                "dominant_freq_y": processed_results.get("dominant_freq_y", 0),
                                "dominant_freq_z": processed_results.get("dominant_freq_z", 0),
                            }
                            
                            processed_data_buffer.append(data_point_for_mqtt)

                            if len(processed_data_buffer) >= buffer_size:
                                # Nhóm và gửi dữ liệu qua MQTT
                                combined_data = {
                                    "metadata": {
                                        "source": "HWT905_RasPi",
                                        "sample_count": len(processed_data_buffer),
                                        "start_time": processed_data_buffer[0]["ts"],
                                        "end_time": processed_data_buffer[-1]["ts"]
                                    },
                                    "data_points": processed_data_buffer # Gửi list các dict
                                }
                                
                                try:
                                    compressed_payload = data_compressor.compress(combined_data)
                                    mqtt_client.publish(app_config["mqtt"]["publish_data_topic"], compressed_payload)
                                    processed_data_buffer.clear() # Xóa buffer sau khi gửi
                                    logger.debug(f"Đã gửi {len(combined_data['data_points'])} điểm dữ liệu qua MQTT.")
                                except Exception as e:
                                    logger.error(f"Lỗi khi nén hoặc publish MQTT: {e}")
                    
        except KeyboardInterrupt:
            logger.info("Nhận tín hiệu dừng từ người dùng. Đang dừng luồng chính.")
            _running_flag.clear()
        except Exception as e:
            logger.critical(f"Lỗi nghiêm trọng trong luồng chính: {e}", exc_info=True)
            _running_flag.clear()

    logger.info("Luồng chính đã dừng.")


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

    _running_flag.set() # Đặt cờ running

    # 3. Khởi tạo và thiết lập cảm biến (hoặc mock data)
    use_mock_data = app_config.get("mock_data", False)
    
    config_manager: Optional[HWT905ConfigManager] = None
    data_decoder: Optional[HWT905DataDecoder] = None

    # Lấy các tham số cấu hình cảm biến từ app_config
    sensor_config = app_config["sensor"]
    sensor_port = sensor_config["uart_port"]
    sensor_baudrate = sensor_config["baud_rate"]
    target_output_rate = sensor_config["default_output_rate_hz"]
    target_output_content_config = sensor_config["default_output_content"]
    
    # Cấu hình RSW value từ dict trong app_config
    rsw_value = 0
    rsw_bit_map = { # Ánh xạ string key sang hằng số RSW_BIT
        "time": RSW_TIME_BIT, "acceleration": RSW_ACC_BIT, "angular_velocity": RSW_GYRO_BIT,
        "angle": RSW_ANGLE_BIT, "magnetic_field": RSW_MAG_BIT, "port_status": RSW_PORT_STATUS_BIT,
        "atmospheric_pressure_height": RSW_PRESSURE_HEIGHT_BIT, "gnss_data": RSW_GPS_LON_LAT_BIT,
        "gnss_speed": RSW_GPS_SPEED_BIT, "quaternion": RSW_QUATERNION_BIT, "gnss_accuracy": RSW_GPS_ACCURACY_BIT
    }
    for key, bit_const in rsw_bit_map.items():
        if target_output_content_config.get(key, False):
            rsw_value |= bit_const

    if use_mock_data:
        logger.info("Ứng dụng đang chạy với DỮ LIỆU GIẢ LẬP.")
        # Không cần khởi tạo config_manager/data_decoder cho mock data
        # dt_sensor cho SensorDataProcessor sẽ là mock_dt
        app_config["processing"]["dt_sensor_actual"] = app_config["processing"]["dt_sensor_mock"] 
    else:
        logger.info("Ứng dụng đang chạy với CẢM BIẾN THẬT.")
        config_manager = HWT905ConfigManager(port=sensor_port, baudrate=sensor_baudrate, debug=(logger.level <= logging.DEBUG))
        data_decoder = HWT905DataDecoder(port=sensor_port, baudrate=sensor_baudrate, debug=(logger.level <= logging.DEBUG))

        if not config_manager.connect():
            logger.critical("Không thể kết nối với cảm biến. Thoát ứng dụng.")
            _running_flag.clear()
            return
        data_decoder.ser = config_manager.ser # Đảm bảo decoder dùng cùng serial instance

        # Kiểm tra và cấu hình baudrate cảm biến
        try:
            if not config_manager.verify_baudrate():
                logger.warning(f"Baudrate hiện tại ({sensor_baudrate}) không khớp hoặc không đọc được. Đang thử factory reset và đặt lại baudrate mặc định.")
                if config_manager.factory_reset():
                    logger.info("Factory Reset thành công. Đang kết nối lại với baudrate mặc định (9600).")
                    config_manager.close()
                    config_manager.baudrate = BAUD_RATE_9600 # Cập nhật baudrate của manager
                    data_decoder.baudrate = BAUD_RATE_9600 # Cập nhật baudrate của decoder
                    if not config_manager.connect():
                         logger.critical("Không thể kết nối lại sau Factory Reset. Thoát ứng dụng.")
                         _running_flag.clear()
                         return
                    data_decoder.ser = config_manager.ser # Cập nhật serial instance cho decoder
                    if not config_manager.verify_factory_reset_state():
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

        # Cấu hình tốc độ output và nội dung output cho cảm biến thật
        rate_map = {
            10: RATE_OUTPUT_10HZ, 50: RATE_OUTPUT_50HZ, 100: RATE_OUTPUT_100HZ, 200: RATE_OUTPUT_200HZ
        }
        rate_const = rate_map.get(target_output_rate, RATE_OUTPUT_100HZ)
        
        logger.info(f"Đang đặt tốc độ output của cảm biến thành {target_output_rate} Hz và nội dung {hex(rsw_value)}...")
        if config_manager.unlock_sensor_for_config():
            if not config_manager.set_update_rate(rate_const):
                logger.error("Không thể đặt tốc độ output.")
            if not config_manager.set_output_content(rsw_value):
                logger.error("Không thể đặt nội dung output.")
            if not config_manager.save_configuration():
                logger.error("Không thể lưu cấu hình cảm biến.")
        else:
            logger.error("Không thể mở khóa cảm biến để cấu hình. Cấu hình output có thể không được áp dụng.")
        
        app_config["processing"]["dt_sensor_actual"] = 1.0 / target_output_rate


    # 4. Khởi tạo bộ xử lý dữ liệu (SensorDataProcessor)
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

    # 5. Khởi tạo DataCompressor
    compressor_config = app_config["data_compression"]
    data_compressor = DataCompressor(
        format=compressor_config["format"],
        use_zlib=compressor_config["use_zlib"]
    )

    # 6. Khởi tạo MQTT Client
    mqtt_config = app_config["mqtt"]
    mqtt_client = MQTTClient(
        broker_address=mqtt_config["broker_address"],
        broker_port=mqtt_config["broker_port"],
        client_id=mqtt_config["client_id"],
        username=mqtt_config.get("username"),
        password=mqtt_config.get("password"),
        keepalive=mqtt_config.get("keepalive", 60),
        use_tls=mqtt_config.get("use_tls", False)
    )
    if not mqtt_client.connect():
        logger.critical("Không thể kết nối MQTT. Thoát ứng dụng.")
        _running_flag.clear()
        if config_manager: config_manager.close()
        return
    
    # 7. Chạy luồng chính
    logger.info("Bắt đầu luồng đọc-xử lý-gửi dữ liệu...")
    main_loop_thread = threading.Thread(target=_main_loop_thread, 
                                        args=(config_manager, data_decoder, sensor_data_processor, 
                                              mqtt_client, data_compressor, app_config))
    main_loop_thread.start()

    # Chờ luồng chính hoàn thành (có thể do lỗi hoặc tín hiệu dừng)
    try:
        while _running_flag.is_set():
            time.sleep(1) # Giữ luồng chính của main() tồn tại
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu dừng (Ctrl+C). Đang dừng ứng dụng.")
        _running_flag.clear() # Báo hiệu cho luồng chính dừng

    main_loop_thread.join() # Chờ luồng chính kết thúc

    # 8. Dọn dẹp
    logger.info("Đang dọn dẹp tài nguyên...")
    if config_manager:
        config_manager.close()
    mqtt_client.disconnect()
    logger.info("Ứng dụng Backend IMU đã dừng.")


if __name__ == '__main__':
    main()