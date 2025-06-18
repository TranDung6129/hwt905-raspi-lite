#!/usr/bin/env python3
"""
Standalone MQTT Configuration Service for HWT905 Sensor.
Chạy độc lập để xử lý các lệnh cấu hình từ xa qua MQTT.

Usage:
    python3 scripts/mqtt_config_service.py [options]
    
Chạy service này song song với main application để cho phép
cấu hình cảm biến từ xa thông qua MQTT commands.
"""

import sys
import time
import signal
import logging
import argparse
import threading
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.utils.common import load_config
from src.utils.logger_setup import setup_logger
from src.core.connection_manager import SensorConnectionManager
from src.mqtt.config import MQTTConfigCommandHandler, MQTTConfigSubscriber

class MQTTConfigService:
    """
    Standalone MQTT Configuration Service.
    Chạy độc lập để xử lý remote config commands.
    """
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or str(project_root / "config" / "app_config.json")
        self.running = False
        self.mqtt_subscriber = None
        self.connection_manager = None
        self.config_manager = None
        
        # Load configuration
        self.app_config = load_config(self.config_path)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
    def start(self) -> bool:
        """
        Start the MQTT configuration service.
        
        Returns:
            True if started successfully, False otherwise
        """
        try:
            self.logger.info("🚀 Starting HWT905 MQTT Configuration Service...")
            
            # Initialize sensor connection
            if not self._init_sensor_connection():
                return False
            
            # Initialize MQTT config subscriber
            if not self._init_mqtt_subscriber():
                return False
            
            self.running = True
            self.logger.info("✅ MQTT Configuration Service started successfully")
            self.logger.info(f"📡 Listening for commands on: {self.app_config['mqtt']['subscribe_commands_topic']}")
            self.logger.info(f"📤 Publishing responses to: {self.app_config['mqtt']['publish_response_topic']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start service: {e}")
            return False
    
    def stop(self):
        """Stop the service gracefully."""
        self.logger.info("🛑 Stopping MQTT Configuration Service...")
        self.running = False
        
        if self.mqtt_subscriber:
            self.mqtt_subscriber.disconnect()
            
        if self.connection_manager:
            self.connection_manager.close_connection()
            
        self.logger.info("✅ Service stopped")
    
    def _init_sensor_connection(self) -> bool:
        """Initialize sensor connection."""
        try:
            sensor_config = self.app_config["sensor"]
            self.connection_manager = SensorConnectionManager(
                sensor_config=sensor_config,
                debug=(self.logger.level <= logging.DEBUG)
            )
            
            # Establish connection with retries
            max_retries = 3
            for attempt in range(max_retries):
                self.logger.info(f"🔌 Attempting sensor connection (attempt {attempt + 1}/{max_retries})...")
                
                ser_instance = self.connection_manager.establish_connection()
                if ser_instance:
                    self.logger.info("✅ Sensor connected successfully")
                    
                    # Get config manager
                    self.config_manager = self.connection_manager.get_config_manager()
                    if self.config_manager:
                        self.logger.info("🔧 Config manager initialized")
                        return True
                    else:
                        self.logger.error("❌ Failed to get config manager")
                        return False
                else:
                    self.logger.warning(f"⚠️ Connection attempt {attempt + 1} failed")
                    if attempt < max_retries - 1:
                        time.sleep(2)
            
            self.logger.error("❌ Failed to connect to sensor after all retries")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Sensor connection error: {e}")
            return False
    
    def _init_mqtt_subscriber(self) -> bool:
        """Initialize MQTT subscriber."""
        try:
            if not self.config_manager:
                self.logger.error("❌ Config manager not available")
                return False
            
            # Create command handler
            command_handler = MQTTConfigCommandHandler(
                config_manager=self.config_manager,
                status_publisher=None  # Will be set by subscriber
            )
            
            # Create MQTT subscriber
            mqtt_config = self.app_config.get("mqtt", {})
            self.mqtt_subscriber = MQTTConfigSubscriber(
                mqtt_config=mqtt_config,
                command_handler=command_handler
            )
            
            # Connect to MQTT broker
            if self.mqtt_subscriber.connect():
                self.logger.info("📡 Connected to MQTT broker")
                return True
            else:
                self.logger.error("❌ Failed to connect to MQTT broker")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ MQTT initialization error: {e}")
            return False
    
    def run(self):
        """Main service loop."""
        if not self.start():
            return False
        
        try:
            # Service loop
            while self.running:
                # Health check - verify connections
                if not self._health_check():
                    self.logger.warning("⚠️ Health check failed, attempting reconnection...")
                    if not self._reconnect():
                        self.logger.error("❌ Reconnection failed, stopping service")
                        break
                
                time.sleep(10)  # Check every 10 seconds
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Received interrupt signal")
        except Exception as e:
            self.logger.error(f"❌ Service error: {e}")
        finally:
            self.stop()
            
        return True
    
    def _health_check(self) -> bool:
        """Check service health."""
        try:
            # Check MQTT connection
            if not self.mqtt_subscriber or not self.mqtt_subscriber.is_ready():
                return False
            
            # Check sensor connection (optional - may not always be available)
            # We'll be more lenient here since sensor might be temporarily disconnected
            
            return True
            
        except Exception as e:
            self.logger.debug(f"Health check error: {e}")
            return False
    
    def _reconnect(self) -> bool:
        """Attempt to reconnect components."""
        try:
            # Try to reconnect MQTT if needed
            if not self.mqtt_subscriber or not self.mqtt_subscriber.is_ready():
                self.logger.info("🔄 Reconnecting MQTT...")
                if self.mqtt_subscriber:
                    self.mqtt_subscriber.disconnect()
                
                time.sleep(2)
                return self._init_mqtt_subscriber()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Reconnection error: {e}")
            return False

def signal_handler(signum, frame):
    """Handle signals for graceful shutdown."""
    print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
    global service
    if service:
        service.stop()
    sys.exit(0)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='HWT905 MQTT Configuration Service')
    parser.add_argument('--config', '-c', help='Path to configuration file')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                        default='INFO', help='Set logging level')
    parser.add_argument('--daemon', '-d', action='store_true', 
                        help='Run as daemon (background process)')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = getattr(logging, args.log_level)
    setup_logger(log_level=log_level)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run service
    global service
    service = MQTTConfigService(config_path=args.config)
    
    if args.daemon:
        # TODO: Implement proper daemon mode
        print("Daemon mode not yet implemented. Running in foreground.")
    
    print("🚀 HWT905 MQTT Configuration Service")
    print("====================================")
    print("📋 Service sẽ xử lý remote config commands qua MQTT")
    print("🔌 Chạy song song với main application")
    print("🛑 Press Ctrl+C to stop")
    print("")
    
    success = service.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
