import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MQTT Configuration
MQTT_BROKER_ADDRESS = os.getenv("MQTT_BROKER_ADDRESS", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "hwt905-raspi-sensor-1")
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_DATA_TOPIC = os.getenv("MQTT_DATA_TOPIC", "sensor/hwt905/angle_data")

# Sensor Configuration
SENSOR_UART_PORT = os.getenv("SENSOR_UART_PORT", "/dev/ttyUSB0")
SENSOR_BAUD_RATE = int(os.getenv("SENSOR_BAUD_RATE", 115200))
SENSOR_AUTO_DISCOVER = os.getenv("SENSOR_AUTO_DISCOVER", "true").lower() == "true"

# Storage Configuration
STORAGE_BASE_DIR = os.getenv("STORAGE_BASE_DIR", "data")
STORAGE_FILE_ROTATION_HOURS = int(os.getenv("STORAGE_FILE_ROTATION_HOURS", 1))
STORAGE_CLEANUP_DAYS = int(os.getenv("STORAGE_CLEANUP_DAYS", 7))

# Data Collection Configuration
# Rate limiting for data storage (Hz). Set to 0 to disable rate limiting
DATA_COLLECTION_RATE_HZ = int(os.getenv("DATA_COLLECTION_RATE_HZ", 200))

# Service Configuration
SENDER_PERIOD_MINUTES = int(os.getenv("SENDER_PERIOD_MINUTES", 30))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper() 