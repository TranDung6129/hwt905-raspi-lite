# src/core/async_data_manager.py
import threading
import logging
import time
from queue import Queue
from typing import Optional

from ..sensors.hwt905_data_decoder import HWT905DataDecoder
from ..storage.storage_manager import StorageManager
from ..processing.data_processor import SensorDataProcessor
from ..sensors.hwt905_constants import PACKET_TYPE_ACC

logger = logging.getLogger(__name__)

class SerialReaderThread(threading.Thread):
    """
    Luồng chuyên đọc dữ liệu thô từ cổng serial và đưa vào hàng đợi.
    """
    def __init__(self, data_decoder: HWT905DataDecoder, raw_data_queue: Queue, running_flag: threading.Event):
        super().__init__(daemon=True, name="SerialReaderThread")
        self.data_decoder = data_decoder
        self.raw_data_queue = raw_data_queue
        self.running_flag = running_flag
        self.raw_packet_count = 0
        self.last_log_time = time.time()

    def run(self):
        logger.info("Luồng đọc Serial đã bắt đầu.")
        while self.running_flag.is_set():
            try:
                raw_packet = self.data_decoder.read_raw_packet() 
                if raw_packet:
                    self.raw_data_queue.put(raw_packet)
                    self.raw_packet_count += 1
                else:
                    # Ngủ một chút nếu không có dữ liệu để tránh chiếm dụng CPU
                    time.sleep(0.0001)
                
                current_time = time.time()
                if current_time - self.last_log_time >= 5.0:
                    rate = self.raw_packet_count / (current_time - self.last_log_time)
                    logger.info(f"[Reader] Tốc độ đọc: {rate:.2f} packets/s ({self.raw_packet_count} trong 5s). Queue size: {self.raw_data_queue.qsize()}")
                    self.raw_packet_count = 0
                    self.last_log_time = current_time

            except Exception as e:
                logger.error(f"[Reader] Lỗi trong luồng đọc Serial: {e}", exc_info=True)
                self.running_flag.clear()
        logger.info("Luồng đọc Serial đã dừng.")


class ProcessingPipelineThread(threading.Thread):
    """
    Luồng thực hiện toàn bộ pipeline xử lý sau khi đọc:
    Decode -> (Lưu decoded) -> Process -> (Lưu processed) -> (Gửi MQTT)
    """
    def __init__(self, data_decoder: HWT905DataDecoder, raw_data_queue: Queue, 
                 running_flag: threading.Event,
                 sensor_data_processor: Optional[SensorDataProcessor] = None,
                 decoded_storage_manager: Optional[StorageManager] = None,
                 processed_storage_manager: Optional[StorageManager] = None):
        super().__init__(daemon=True, name="ProcessingPipelineThread")
        self.data_decoder = data_decoder
        self.raw_data_queue = raw_data_queue
        self.running_flag = running_flag
        self.sensor_data_processor = sensor_data_processor
        self.decoded_storage_manager = decoded_storage_manager
        self.processed_storage_manager = processed_storage_manager
        
        self.decoded_packet_count = 0
        self.processed_packet_count = 0
        self.last_log_time = time.time()

    def run(self):
        logger.info("Luồng xử lý pipeline đã bắt đầu.")
        while self.running_flag.is_set() or not self.raw_data_queue.empty():
            try:
                raw_packet = self.raw_data_queue.get(timeout=1)
                
                # 1. Decode
                packet_info = self.data_decoder.decode_raw_packet(raw_packet)

                if not packet_info or "error" in packet_info:
                    if packet_info:
                        logger.warning(f"[Pipeline] Lỗi giải mã gói tin: {packet_info.get('message', 'Unknown')}")
                    self.raw_data_queue.task_done()
                    continue

                self.decoded_packet_count += 1
                
                # Chỉ xử lý các gói gia tốc
                if packet_info.get("type") != PACKET_TYPE_ACC:
                    self.raw_data_queue.task_done()
                    continue

                acc_data = {
                    'acc_x': packet_info.get("acc_x"),
                    'acc_y': packet_info.get("acc_y"),
                    'acc_z': packet_info.get("acc_z")
                }
                current_timestamp = time.time()

                # 2. Lưu dữ liệu đã giải mã (nếu được cấu hình)
                if self.decoded_storage_manager:
                    self.decoded_storage_manager.store_and_prepare_for_transmission(acc_data, current_timestamp)

                # 3. Xử lý dữ liệu (nếu được cấu hình)
                if self.sensor_data_processor:
                    processed_results = self.sensor_data_processor.process_new_sample(
                        acc_data['acc_x'], acc_data['acc_y'], acc_data['acc_z']
                    )
                    
                    # 4. Lưu dữ liệu đã xử lý (nếu có kết quả và được cấu hình)
                    if processed_results and self.processed_storage_manager:
                        self.processed_packet_count += 1
                        self.processed_storage_manager.store_and_prepare_for_transmission(processed_results, current_timestamp)
                
                self.raw_data_queue.task_done()

                # Ghi log định kỳ
                current_time = time.time()
                if current_time - self.last_log_time >= 5.0:
                    decode_rate = self.decoded_packet_count / (current_time - self.last_log_time)
                    process_rate = self.processed_packet_count / (current_time - self.last_log_time)
                    logger.info(f"[Pipeline] Tốc độ Decode: {decode_rate:.2f} packets/s. Process: {process_rate:.2f} packets/s.")
                    self.decoded_packet_count = 0
                    self.processed_packet_count = 0
                    self.last_log_time = current_time

            except Queue.Empty:
                if not self.running_flag.is_set():
                    logger.info("Hàng đợi trống và cờ đã tắt, thoát luồng pipeline.")
                    break
                continue
            except Exception as e:
                logger.error(f"[Pipeline] Lỗi trong luồng pipeline: {e}", exc_info=True)
                self.running_flag.clear()
                
        logger.info("Luồng xử lý pipeline đã dừng.") 