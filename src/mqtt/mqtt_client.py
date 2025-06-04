import paho.mqtt.client as paho
import logging
import time
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)

class MQTTClient:
    """
    Lớp để quản lý kết nối và giao tiếp MQTT.
    """
    def __init__(self, broker_address: str, broker_port: int, client_id: str,
                 username: Optional[str] = None, password: Optional[str] = None,
                 keepalive: int = 60, use_tls: bool = False,
                 on_connect_callback: Optional[Callable[[paho.Client, Any, Any, int], None]] = None,
                 on_message_callback: Optional[Callable[[paho.Client, Any, paho.MQTTMessage], None]] = None):
        
        self.broker_address = broker_address
        self.broker_port = broker_port
        self.client_id = client_id
        self.username = username
        self.password = password
        self.keepalive = keepalive
        self.use_tls = use_tls

        self.client = paho.Client(client_id=self.client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish
        self.client.on_subscribe = self._on_subscribe
        
        if on_connect_callback:
            self.on_connect_callback = on_connect_callback
        else:
            self.on_connect_callback = lambda client, userdata, flags, rc: logger.info(f"Kết nối MQTT: {paho.connack_string(rc)}")

        if on_message_callback:
            self.on_message_callback = on_message_callback
        else:
            self.on_message_callback = lambda client, userdata, msg: logger.info(f"Nhận: {msg.topic} {msg.payload.decode()}")

        self.client.on_message = self.on_message_callback

        if self.username:
            self.client.username_pw_set(self.username, self.password)
        
        if self.use_tls:
            # Cần cấu hình TLS nếu dùng: client.tls_set(ca_certs="ca.crt", certfile="client.crt", keyfile="client.key")
            logger.warning("Cấu hình TLS chưa được triển khai đầy đủ.")

    def _on_connect(self, client: paho.Client, userdata: Any, flags: dict, rc: int):
        if hasattr(self, 'on_connect_callback'):
            self.on_connect_callback(client, userdata, flags, rc)
        if rc == 0:
            logger.info(f"Đã kết nối thành công tới MQTT broker {self.broker_address}:{self.broker_port}")
        else:
            logger.error(f"Kết nối MQTT thất bại: {paho.connack_string(rc)}")

    def _on_disconnect(self, client: paho.Client, userdata: Any, rc: int):
        logger.warning(f"Đã ngắt kết nối khỏi MQTT broker (rc: {rc}).")
        # Cố gắng kết nối lại tự động
        logger.info("Đang cố gắng kết nối lại MQTT sau 5 giây...")
        time.sleep(5)
        try:
            self.client.reconnect()
        except Exception as e:
            logger.error(f"Lỗi khi cố gắng kết nối lại MQTT: {e}")


    def _on_publish(self, client: paho.Client, userdata: Any, mid: int):
        logger.debug(f"Đã publish message với mid {mid}")

    def _on_subscribe(self, client: paho.Client, userdata: Any, mid: int, granted_qos: list):
        logger.info(f"Đã subscribe thành công với mid {mid}, QOS: {granted_qos}")

    def connect(self) -> bool:
        """Kết nối tới MQTT broker."""
        try:
            # client.connect() blocking cho đến khi kết nối hoặc timeout
            self.client.connect(self.broker_address, self.broker_port, self.keepalive)
            self.client.loop_start() # Bắt đầu luồng xử lý mạng trong nền
            logger.info(f"Đang chờ kết nối tới MQTT broker {self.broker_address}:{self.broker_port}...")
            # Chờ một chút để callback on_connect được gọi
            time.sleep(1) 
            return self.client.is_connected()
        except Exception as e:
            logger.error(f"Lỗi khi cố gắng kết nối tới MQTT broker: {e}")
            return False

    def disconnect(self) -> None:
        """Ngắt kết nối khỏi MQTT broker."""
        if self.client.is_connected():
            self.client.loop_stop() # Dừng luồng xử lý mạng
            self.client.disconnect()
            logger.info("Đã ngắt kết nối khỏi MQTT broker.")

    def publish(self, topic: str, payload: str, qos: int = 1, retain: bool = False) -> None:
        """
        Publish một message tới topic đã cho.
        Payload phải là chuỗi (string) hoặc bytes.
        """
        if not self.client.is_connected():
            logger.warning(f"Không thể publish: Client chưa kết nối. Topic: {topic}")
            return
        result = self.client.publish(topic, payload, qos, retain)
        # result.rc có thể là paho.MQTT_ERR_SUCCESS (0)
        # result.mid là message ID
        if result.rc != paho.MQTT_ERR_SUCCESS:
            logger.error(f"Lỗi khi publish message tới topic {topic}: {result.rc}")

    def subscribe(self, topic: str, qos: int = 1) -> None:
        """Subscribe tới một topic."""
        if not self.client.is_connected():
            logger.warning(f"Không thể subscribe: Client chưa kết nối. Topic: {topic}")
            return
        self.client.subscribe(topic, qos)
        logger.info(f"Đã subscribe tới topic: {topic}")