#!/usr/bin/env python3
# scripts/sender.py

import logging
import os
import sys
import csv
import json
import time
from typing import List, Dict
from datetime import datetime

import paho.mqtt.client as mqtt

# Add project root to the Python path to allow importing from 'src'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src import config
    from src.utils.logger_setup import setup_logging
except ImportError as e:
    print(f"FATAL: Could not import necessary modules. Make sure the script is run from the project root "
          f"or the PYTHONPATH is set correctly. Error: {e}")
    sys.exit(1)

logger = logging.getLogger(__name__)

def process_and_send_file(filepath: str, client: mqtt.Client, topic: str):
    """
    Reads a CSV file, packages its content into a JSON message, sends it via MQTT,
    and renames the file upon successful transmission.
    """
    logger.info(f"Đang xử lý file: {os.path.basename(filepath)}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            data_points = [row for row in reader]

        if not data_points:
            logger.warning(f"File '{filepath}' trống. Bỏ qua và đánh dấu là 'empty'.")
            os.rename(filepath, f"{filepath}.empty")
            return

        # Prepare the payload
        payload = {
            "metadata": {
                "source_device": config.MQTT_CLIENT_ID,
                "filename": os.path.basename(filepath),
                "sent_timestamp_utc": datetime.utcnow().isoformat() + "Z",
                "data_points_count": len(data_points)
            },
            "angle_data": data_points
        }
        
        payload_str = json.dumps(payload)

        # Publish to MQTT
        result = client.publish(topic, payload_str, qos=1)
        result.wait_for_publish(timeout=10)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"Đã gửi thành công dữ liệu từ '{os.path.basename(filepath)}' tới topic '{topic}'.")
            os.rename(filepath, f"{filepath}.sent")
        else:
            logger.error(f"Gửi MQTT thất bại với mã lỗi: {result.rc}. File sẽ được thử lại sau.")

    except FileNotFoundError:
        logger.error(f"File không tồn tại: {filepath}. Bỏ qua.")
    except json.JSONDecodeError as e:
        logger.error(f"Lỗi khi tạo JSON từ file '{filepath}': {e}")
    except (IOError, os.error) as e:
        logger.error(f"Lỗi I/O hoặc hệ thống khi xử lý file '{filepath}': {e}")
    except Exception as e:
        logger.error(f"Lỗi không mong muốn khi xử lý file '{filepath}': {e}", exc_info=True)


def main():
    """Main function to run the sender script."""
    setup_logging(log_level=config.LOG_LEVEL)
    logger.info("Bắt đầu kịch bản gửi dữ liệu...")

    data_dir = config.STORAGE_BASE_DIR
    if not os.path.isdir(data_dir):
        logger.warning(f"Thư mục dữ liệu '{data_dir}' không tồn tại. Không có gì để gửi. Thoát.")
        return

    files_to_send = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    if not files_to_send:
        logger.info("Không tìm thấy file .csv nào để gửi. Thoát.")
        return

    logger.info(f"Tìm thấy {len(files_to_send)} file để xử lý.")

    sender_client_id = f"{config.MQTT_CLIENT_ID}-sender-{int(time.time())}"
    client = mqtt.Client(client_id=sender_client_id)
    
    if config.MQTT_USERNAME and config.MQTT_PASSWORD:
        client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)

    try:
        logger.info(f"Đang kết nối tới MQTT Broker tại {config.MQTT_BROKER_ADDRESS}:{config.MQTT_BROKER_PORT}...")
        client.connect(config.MQTT_BROKER_ADDRESS, config.MQTT_BROKER_PORT, 60)
        client.loop_start()

        for filename in sorted(files_to_send):
            filepath = os.path.join(data_dir, filename)
            process_and_send_file(filepath, client, config.MQTT_DATA_TOPIC)

    except ConnectionRefusedError:
        logger.error("Kết nối MQTT bị từ chối. Vui lòng kiểm tra địa chỉ broker, port và credentials.")
    except OSError as e:
        logger.error(f"Lỗi mạng hoặc hệ điều hành khi kết nối MQTT: {e}")
    except Exception as e:
        logger.error(f"Lỗi không mong muốn trong quá trình gửi: {e}", exc_info=True)
    finally:
        logger.info("Đang ngắt kết nối MQTT và dừng kịch bản.")
        client.loop_stop()
        client.disconnect()
        logger.info("Kịch bản gửi dữ liệu đã kết thúc.")


if __name__ == "__main__":
    main() 