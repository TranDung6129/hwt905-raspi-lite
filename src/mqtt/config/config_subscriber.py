"""
MQTT Configuration Subscriber for Remote Sensor Configuration.
Listens to MQTT config commands and executes them via the command handler.
"""

import json
import logging
import paho.mqtt.client as mqtt
from typing import Dict, Any, Optional, Callable
from .config_command_handler import MQTTConfigCommandHandler

logger = logging.getLogger(__name__)

class MQTTConfigSubscriber:
    """
    MQTT subscriber for remote sensor configuration commands.
    """
    
    def __init__(self, mqtt_config: Dict[str, Any], command_handler: MQTTConfigCommandHandler,
                 response_publisher: Optional[Callable] = None):
        """
        Initialize MQTT config subscriber.
        
        Args:
            mqtt_config: MQTT configuration dictionary
            command_handler: MQTTConfigCommandHandler instance
            response_publisher: Optional callback to publish responses
        """
        self.mqtt_config = mqtt_config
        self.command_handler = command_handler
        self.response_publisher = response_publisher
        
        # MQTT client
        self.client = None
        self.is_connected = False
        
        # Topics
        self.command_topic = mqtt_config.get("subscribe_commands_topic", "sensor/hwt905/commands")
        self.response_topic = mqtt_config.get("publish_response_topic", "sensor/hwt905/config_response")
        
    def connect(self) -> bool:
        """
        Connect to MQTT broker.
        
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            # Create MQTT client
            client_id = f"{self.mqtt_config.get('client_id', 'hwt905_config')}_subscriber"
            self.client = mqtt.Client(client_id)
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Configure TLS if needed
            if self.mqtt_config.get("use_tls", False):
                self.client.tls_set()
            
            # Set credentials if provided
            username = self.mqtt_config.get("username")
            password = self.mqtt_config.get("password")
            if username and password:
                self.client.username_pw_set(username, password)
            
            # Connect to broker
            broker_address = self.mqtt_config["broker_address"]
            broker_port = self.mqtt_config.get("broker_port", 1883)
            keepalive = self.mqtt_config.get("keepalive", 60)
            
            logger.info(f"Connecting to MQTT broker: {broker_address}:{broker_port}")
            self.client.connect(broker_address, broker_port, keepalive)
            
            # Start the loop in a separate thread
            self.client.loop_start()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("Disconnected from MQTT broker")
            except Exception as e:
                logger.error(f"Error disconnecting from MQTT: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            self.is_connected = True
            logger.info("Connected to MQTT broker for config commands")
            
            # Subscribe to command topic
            client.subscribe(self.command_topic)
            logger.info(f"Subscribed to command topic: {self.command_topic}")
            
            # Publish help message
            self._publish_help()
            
        else:
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        self.is_connected = False
        if rc != 0:
            logger.warning("Unexpected disconnection from MQTT broker")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received."""
        try:
            logger.info(f"Received config command on topic {msg.topic}")
            logger.debug(f"Command payload: {msg.payload.decode('utf-8')}")
            
            # Handle the command
            response = self.command_handler.handle_command(msg.topic, msg.payload)
            
            # Publish response
            self._publish_response(response)
            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
            error_response = {
                "status": "error",
                "error": f"Message processing error: {e}",
                "timestamp": __import__('time').time()
            }
            self._publish_response(error_response)
    
    def _publish_response(self, response: Dict[str, Any]):
        """
        Publish command response.
        
        Args:
            response: Response dictionary to publish
        """
        try:
            if self.client and self.is_connected:
                payload = json.dumps(response, ensure_ascii=False, indent=2)
                self.client.publish(self.response_topic, payload, qos=1)
                logger.info(f"Published response: {response.get('status', 'unknown')}")
                
            # Also call response publisher if available
            if self.response_publisher:
                self.response_publisher(response)
                
        except Exception as e:
            logger.error(f"Error publishing response: {e}")
    
    def _publish_help(self):
        """Publish help information about available commands."""
        try:
            help_info = self.command_handler.get_command_help()
            help_info["message"] = "HWT905 Remote Configuration - Available Commands"
            help_info["status"] = "info"
            help_info["timestamp"] = __import__('time').time()
            
            self._publish_response(help_info)
            
        except Exception as e:
            logger.error(f"Error publishing help: {e}")
    
    def publish_status(self, status_data: Dict[str, Any]):
        """
        Publish status update.
        
        Args:
            status_data: Status data to publish
        """
        try:
            if self.client and self.is_connected:
                status_topic = self.mqtt_config.get("publish_status_topic", "sensor/hwt905/status")
                payload = json.dumps(status_data, ensure_ascii=False, indent=2)
                self.client.publish(status_topic, payload, qos=1)
                
        except Exception as e:
            logger.error(f"Error publishing status: {e}")
    
    def is_ready(self) -> bool:
        """Check if the subscriber is ready to receive commands."""
        return self.is_connected and self.client is not None
