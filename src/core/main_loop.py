"""
Main Loop Thread Module

Module này chứa logic chính để đọc, xử lý và gửi dữ liệu cảm biến IMU.
Được tách riêng từ main.py để cải thiện cấu trúc và khả năng bảo trì.
"""

import logging
import time
import threading
from typing import Optional

from src.sensors.hwt905_config_manager import HWT905ConfigManager
from src.sensors.hwt905_data_decoder import HWT905DataDecoder
from src.processing.data_processor import SensorDataProcessor
from src.processing.data_compressor import DataCompressor
from src.mqtt.mqtt_client import MQTTClient
from src.utils.mqtt_message_builder import MQTTMessageBuilder
from src.utils.common import generate_mock_acc_data
from src.sensors.hwt905_constants import PACKET_TYPE_ACC


class MainLoopController:
    """
    Lớp điều khiển vòng lặp chính của ứng dụng IMU.
    """
    
    def __init__(self, running_flag: threading.Event):
        """
        Khởi tạo controller với flag để điều khiển vòng lặp.
        
        Args:
            running_flag: Threading event để điều khiển vòng lặp chính
        """
        self.running_flag = running_flag
        self.logger = logging.getLogger(__name__)
    
    def run_main_loop(self, 
                      config_manager: Optional[HWT905ConfigManager], 
                      data_decoder: Optional[HWT905DataDecoder], 
                      sensor_data_processor: SensorDataProcessor,
                      mqtt_client: MQTTClient,
                      data_compressor: DataCompressor,
                      mqtt_message_builder: MQTTMessageBuilder,
                      app_config: dict):
        """
        Luồng chính để đọc, xử lý và gửi dữ liệu cảm biến.
        
        Args:
            config_manager: Quản lý cấu hình cảm biến (None nếu dùng mock data)
            data_decoder: Bộ giải mã dữ liệu cảm biến (None nếu dùng mock data)
            sensor_data_processor: Bộ xử lý dữ liệu cảm biến
            mqtt_client: Client MQTT để gửi dữ liệu
            data_compressor: Bộ nén dữ liệu
            mqtt_message_builder: Bộ tạo message MQTT
            app_config: Cấu hình ứng dụng
        """
        self.logger.info("Luồng chính đã bắt đầu.")

        processed_data_buffer = [] # Buffer để nhóm dữ liệu trước khi gửi MQTT
        
        # Lấy cách gửi và kích thước buffer từ config
        send_strategy = app_config["mqtt"].get("send_strategy", "batch") # Mặc định là "batch"
        processing_buffer_size = app_config["processing"]["data_buffer_size"]

        effective_buffer_size = self._determine_effective_buffer_size(
            send_strategy, processing_buffer_size
        )
        
        use_mock_data = app_config.get("mock_data", False)
        mock_interval_s = app_config["processing"]["dt_sensor_mock"] # Khoảng thời gian giữa các mẫu mock
        mock_time_elapsed = 0.0 # Để tạo dữ liệu giả lập

        while self.running_flag.is_set():
            try:
                packet_info = self._get_packet_data(
                    use_mock_data, data_decoder, mock_time_elapsed, mock_interval_s
                )
                
                if packet_info and use_mock_data:
                    mock_time_elapsed += mock_interval_s
                    time.sleep(mock_interval_s) # Giả lập độ trễ nhận data

                if packet_info:
                    if self._handle_packet_error(packet_info):
                        continue
                    
                    if self._process_acceleration_packet(
                        packet_info, sensor_data_processor, mqtt_message_builder,
                        processed_data_buffer, effective_buffer_size, send_strategy,
                        data_compressor, mqtt_client, app_config
                    ):
                        processed_data_buffer.clear()
                        
            except KeyboardInterrupt:
                self.logger.info("Nhận tín hiệu dừng từ người dùng. Đang dừng luồng chính.")
                self.running_flag.clear()
            except Exception as e:
                self.logger.critical(f"Lỗi nghiêm trọng trong luồng chính: {e}", exc_info=True)
                self.running_flag.clear()

        self.logger.info("Luồng chính đã dừng.")
    
    def _determine_effective_buffer_size(self, send_strategy: str, processing_buffer_size: int) -> int:
        """
        Xác định kích thước buffer hiệu quả dựa trên strategy gửi.
        
        Args:
            send_strategy: Cách thức gửi dữ liệu
            processing_buffer_size: Kích thước buffer từ config
            
        Returns:
            Kích thước buffer hiệu quả
        """
        effective_buffer_size = 1
        
        if send_strategy == "continuous":
            effective_buffer_size = 1
            self.logger.info(f"Cách gửi dữ liệu: Liên tục (mỗi {effective_buffer_size} mẫu).")
        elif send_strategy == "batch":
            effective_buffer_size = processing_buffer_size
            self.logger.info(f"Cách gửi dữ liệu: Theo lô (mỗi {effective_buffer_size} mẫu).")
        elif send_strategy == "batch_average":
            effective_buffer_size = processing_buffer_size
            self.logger.info(f"Cách gửi dữ liệu: Trung bình theo lô (mỗi {effective_buffer_size} mẫu).")
        else: # Mặc định hoặc không rõ thì dùng batch
            send_strategy = "batch" 
            effective_buffer_size = processing_buffer_size
            self.logger.warning(f"Cách gửi không xác định, sử dụng mặc định: Theo lô (mỗi {effective_buffer_size} mẫu).")

        if effective_buffer_size <= 0:
            self.logger.warning(f"effective_buffer_size ({effective_buffer_size}) không hợp lệ, đặt lại thành 1.")
            effective_buffer_size = 1
            
        return effective_buffer_size
    
    def _get_packet_data(self, use_mock_data: bool, data_decoder: Optional[HWT905DataDecoder], 
                        mock_time_elapsed: float, mock_interval_s: float) -> Optional[dict]:
        """
        Lấy dữ liệu packet từ cảm biến thật hoặc mock data.
        
        Args:
            use_mock_data: Có sử dụng mock data hay không
            data_decoder: Bộ giải mã dữ liệu (None nếu dùng mock)
            mock_time_elapsed: Thời gian đã trôi qua cho mock data
            mock_interval_s: Khoảng thời gian giữa các mẫu mock
            
        Returns:
            Thông tin packet hoặc None
        """
        packet_info = None
        
        if use_mock_data:
            # Tạo dữ liệu giả lập
            packet_info = generate_mock_acc_data(mock_time_elapsed)
        else:
            # Đọc gói tin từ cảm biến thật
            if not data_decoder:
                self.logger.error("Data Decoder chưa được khởi tạo cho cảm biến thật.")
                self.running_flag.clear()
                return None
            packet_info = data_decoder.read_one_packet()
            
        return packet_info
    
    def _handle_packet_error(self, packet_info: dict) -> bool:
        """
        Xử lý lỗi packet nếu có.
        
        Args:
            packet_info: Thông tin packet
            
        Returns:
            True nếu có lỗi và cần skip packet này, False nếu không có lỗi
        """
        if "error" in packet_info:
            self.logger.warning(f"Lỗi gói tin từ cảm biến: {packet_info['message']} (Gói raw: {packet_info.get('raw_packet', b'').hex()})")
            if packet_info["error"] == "possible_baudrate_mismatch":
                self.logger.error("Lỗi Baudrate nghiêm trọng. Đang dừng luồng chính.")
                self.running_flag.clear() # Dừng vòng lặp
            return True
        return False
    
    def _process_acceleration_packet(self, packet_info: dict, sensor_data_processor: SensorDataProcessor,
                                   mqtt_message_builder: MQTTMessageBuilder, processed_data_buffer: list,
                                   effective_buffer_size: int, send_strategy: str,
                                   data_compressor: DataCompressor, mqtt_client: MQTTClient,
                                   app_config: dict) -> bool:
        """
        Xử lý packet gia tốc và gửi dữ liệu qua MQTT nếu cần.
        
        Args:
            packet_info: Thông tin packet
            sensor_data_processor: Bộ xử lý dữ liệu cảm biến
            mqtt_message_builder: Bộ tạo message MQTT
            processed_data_buffer: Buffer dữ liệu đã xử lý
            effective_buffer_size: Kích thước buffer hiệu quả
            send_strategy: Cách thức gửi dữ liệu
            data_compressor: Bộ nén dữ liệu
            mqtt_client: Client MQTT
            app_config: Cấu hình ứng dụng
            
        Returns:
            True nếu đã gửi dữ liệu và cần clear buffer, False nếu không
        """
        if packet_info.get("type") != PACKET_TYPE_ACC:
            return False
            
        accX = packet_info.get("acc_x")
        accY = packet_info.get("acc_y")
        accZ = packet_info.get("acc_z")
        
        if accX is None or accY is None or accZ is None:
            return False
            
        processed_results = sensor_data_processor.process_new_sample(accX, accY, accZ)
        
        if not processed_results or not processed_results.get("rls_warmed_up", False):
            return False
            
        current_timestamp = time.time() # Unix timestamp
        
        # Sử dụng MQTTMessageBuilder để tạo data point
        data_point_for_mqtt = mqtt_message_builder.create_data_point(processed_results, current_timestamp)
        processed_data_buffer.append(data_point_for_mqtt)

        if len(processed_data_buffer) >= effective_buffer_size:
            # Sử dụng MQTTMessageBuilder để tạo message theo strategy
            combined_data = mqtt_message_builder.build_message(send_strategy, processed_data_buffer)
            num_points_in_payload = 1 if send_strategy == "batch_average" else len(processed_data_buffer)
            
            if combined_data:
                try:
                    compressed_payload = data_compressor.compress(combined_data)
                    mqtt_client.publish(app_config["mqtt"]["publish_data_topic"], compressed_payload)
                    self.logger.debug(f"Đã gửi {num_points_in_payload} điểm dữ liệu (strategy: {send_strategy}) qua MQTT.")
                except Exception as e:
                    self.logger.error(f"Lỗi khi nén hoặc publish MQTT: {e}")
            return True
            
        return False


def create_main_loop_thread(running_flag: threading.Event,
                          config_manager: Optional[HWT905ConfigManager], 
                          data_decoder: Optional[HWT905DataDecoder], 
                          sensor_data_processor: SensorDataProcessor,
                          mqtt_client: MQTTClient,
                          data_compressor: DataCompressor,
                          mqtt_message_builder: MQTTMessageBuilder,
                          app_config: dict) -> threading.Thread:
    """
    Tạo và trả về thread cho vòng lặp chính.
    
    Args:
        running_flag: Threading event để điều khiển vòng lặp
        config_manager: Quản lý cấu hình cảm biến
        data_decoder: Bộ giải mã dữ liệu cảm biến
        sensor_data_processor: Bộ xử lý dữ liệu cảm biến
        mqtt_client: Client MQTT
        data_compressor: Bộ nén dữ liệu
        mqtt_message_builder: Bộ tạo message MQTT
        app_config: Cấu hình ứng dụng
        
    Returns:
        Thread đã được cấu hình để chạy vòng lặp chính
    """
    controller = MainLoopController(running_flag)
    
    return threading.Thread(
        target=controller.run_main_loop,
        args=(config_manager, data_decoder, sensor_data_processor,
              mqtt_client, data_compressor, mqtt_message_builder, app_config)
    )
