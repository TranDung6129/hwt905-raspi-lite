import logging
from typing import Dict, Any
from .base_publisher import BasePublisher
from src.utils.common import load_config
import copy
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

class RealtimePublisher(BasePublisher):
    """
    Publisher gửi mỗi điểm dữ liệu ngay lập tức (real-time).
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.compressor = self.get_compressor()
        message_config = load_config('config/mqtt_message_config.json')
        self.message_template = message_config['message_templates']['continuous']['structure']

    def publish(self, data_point: Dict[str, Any]):
        """
        Xây dựng, nén và gửi một điểm dữ liệu.

        Args:
            data_point (Dict[str, Any]): Dữ liệu đã xử lý.
        """
        ts = data_point.get('ts', 0)
        
        # Tạo message từ template, deepcopy để đảm bảo an toàn
        message = copy.deepcopy(self.message_template)
        message['metadata']['start_time'] = ts
        message['metadata']['end_time'] = ts
        message['data_points'] = [data_point]

        try:
            if self.compressor:
                payload = self.compressor.compress(message)
            else:
                # Fallback to plain JSON if no compressor
                import json
                payload = json.dumps(message).encode('utf-8')

            # Gửi tin nhắn
            msg_info = self.client.publish(self.publish_topic, payload, qos=0)
            
            if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Gửi thành công 1 điểm dữ liệu, kích thước payload: {len(payload)} bytes.")
            if msg_info.is_published() == False:
                logger.warning(f"Tin nhắn có thể chưa được gửi (is_published=False). Mid: {msg_info.mid}")
                
        except Exception as e:
            logger.error(f"Lỗi khi gửi dữ liệu real-time: {e}") 