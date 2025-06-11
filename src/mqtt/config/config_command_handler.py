"""
MQTT Configuration Command Handler for HWT905 Sensor Remote Configuration.
Handles incoming MQTT commands to configure sensor remotely via hex commands.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, Callable
from src.sensors.config import HWT905UnifiedConfigManager
from src.sensors.hwt905_constants import (
    RATE_OUTPUT_10HZ, RATE_OUTPUT_50HZ, RATE_OUTPUT_100HZ, RATE_OUTPUT_200HZ,
    BAUD_RATE_9600, BAUD_RATE_115200, BAUD_RATE_230400,
    RSW_ACC_BIT, RSW_GYRO_BIT, RSW_ANGLE_BIT, RSW_MAG_BIT,
    RSW_TIME_BIT, RSW_PRESSURE_HEIGHT_BIT, RSW_GPS_LON_LAT_BIT,
    RSW_GPS_SPEED_BIT, RSW_QUATERNION_BIT, RSW_GPS_ACCURACY_BIT, RSW_PORT_STATUS_BIT,
    REG_RSW, REG_RRATE, REG_BAUD, REG_SAVE
)

logger = logging.getLogger(__name__)

class MQTTConfigCommandHandler:
    """
    Handles MQTT commands for remote sensor configuration.
    Supports both high-level commands and raw hex commands.
    """
    
    def __init__(self, config_manager: HWT905UnifiedConfigManager, 
                 status_publisher: Optional[Callable] = None):
        """
        Initialize the command handler.
        
        Args:
            config_manager: HWT905UnifiedConfigManager instance
            status_publisher: Optional callback to publish status updates
        """
        self.config_manager = config_manager
        self.status_publisher = status_publisher
        
        # Command mapping
        self.command_handlers = {
            "set_rate": self._handle_set_rate,
            "set_output": self._handle_set_output,
            "set_baudrate": self._handle_set_baudrate,
            "factory_reset": self._handle_factory_reset,
            "read_config": self._handle_read_config,
            "raw_hex": self._handle_raw_hex,
            "unlock": self._handle_unlock,
            "save": self._handle_save,
            "restart": self._handle_restart
        }
        
        # Rate mapping
        self.rate_map = {
            10: RATE_OUTPUT_10HZ,
            50: RATE_OUTPUT_50HZ, 
            100: RATE_OUTPUT_100HZ,
            200: RATE_OUTPUT_200HZ
        }
        
        # Baudrate mapping
        self.baudrate_map = {
            9600: BAUD_RATE_9600,
            115200: BAUD_RATE_115200,
            230400: BAUD_RATE_230400
        }
        
        # Content mapping for output configuration
        self.content_map = {
            "time": RSW_TIME_BIT,
            "acc": RSW_ACC_BIT,
            "acceleration": RSW_ACC_BIT,
            "gyro": RSW_GYRO_BIT,
            "angular_velocity": RSW_GYRO_BIT,
            "angle": RSW_ANGLE_BIT,
            "mag": RSW_MAG_BIT,
            "magnetic": RSW_MAG_BIT,
            "port": RSW_PORT_STATUS_BIT,
            "pressure": RSW_PRESSURE_HEIGHT_BIT,
            "gps_pos": RSW_GPS_LON_LAT_BIT,
            "gps_speed": RSW_GPS_SPEED_BIT,
            "quaternion": RSW_QUATERNION_BIT,
            "gps_acc": RSW_GPS_ACCURACY_BIT
        }

    def handle_command(self, topic: str, payload: bytes) -> Dict[str, Any]:
        """
        Handle incoming MQTT command.
        
        Args:
            topic: MQTT topic
            payload: Command payload
            
        Returns:
            Response dictionary with status and result
        """
        try:
            # Parse JSON payload
            command_data = json.loads(payload.decode('utf-8'))
            logger.info(f"Received config command: {command_data}")
            
            # Extract command type
            command_type = command_data.get("command")
            if not command_type:
                return self._create_error_response("Missing 'command' field")
            
            # Get command handler
            handler = self.command_handlers.get(command_type)
            if not handler:
                return self._create_error_response(f"Unknown command: {command_type}")
            
            # Execute command
            response = handler(command_data)
            
            # Publish status if publisher available
            if self.status_publisher:
                self.status_publisher(response)
                
            return response
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON payload: {e}"
            logger.error(error_msg)
            return self._create_error_response(error_msg)
            
        except Exception as e:
            error_msg = f"Command handling error: {e}"
            logger.error(error_msg)
            return self._create_error_response(error_msg)

    def _handle_set_rate(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set rate command."""
        try:
            rate = command_data.get("rate")
            if rate not in self.rate_map:
                return self._create_error_response(f"Invalid rate: {rate}. Valid: {list(self.rate_map.keys())}")
            
            if not self.config_manager.unlock_sensor_for_config():
                return self._create_error_response("Failed to unlock sensor")
            
            if self.config_manager.set_update_rate(self.rate_map[rate]):
                self.config_manager.save_configuration()
                return self._create_success_response(f"Rate set to {rate} Hz")
            else:
                return self._create_error_response("Failed to set rate")
                
        except Exception as e:
            return self._create_error_response(f"Set rate error: {e}")

    def _handle_set_output(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set output content command."""
        try:
            output_list = command_data.get("output", [])
            if isinstance(output_list, str):
                output_list = [item.strip() for item in output_list.split(',')]
            
            rsw_value = 0
            for content in output_list:
                content_lower = content.lower()
                if content_lower in self.content_map:
                    rsw_value |= self.content_map[content_lower]
                else:
                    logger.warning(f"Unknown output content: {content}")
            
            if not self.config_manager.unlock_sensor_for_config():
                return self._create_error_response("Failed to unlock sensor")
            
            if self.config_manager.set_output_content(rsw_value):
                self.config_manager.save_configuration()
                return self._create_success_response(f"Output content set: {output_list} (RSW=0x{rsw_value:04X})")
            else:
                return self._create_error_response("Failed to set output content")
                
        except Exception as e:
            return self._create_error_response(f"Set output error: {e}")

    def _handle_set_baudrate(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle set baudrate command."""
        try:
            baudrate = command_data.get("baudrate")
            if baudrate not in self.baudrate_map:
                return self._create_error_response(f"Invalid baudrate: {baudrate}. Valid: {list(self.baudrate_map.keys())}")
            
            if not self.config_manager.unlock_sensor_for_config():
                return self._create_error_response("Failed to unlock sensor")
            
            if self.config_manager.set_baudrate(self.baudrate_map[baudrate]):
                self.config_manager.save_configuration()
                return self._create_success_response(f"Baudrate set to {baudrate}. Sensor will restart.")
            else:
                return self._create_error_response("Failed to set baudrate")
                
        except Exception as e:
            return self._create_error_response(f"Set baudrate error: {e}")

    def _handle_factory_reset(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle factory reset command."""
        try:
            if not self.config_manager.unlock_sensor_for_config():
                return self._create_error_response("Failed to unlock sensor")
            
            if self.config_manager.factory_reset():
                return self._create_success_response("Factory reset completed")
            else:
                return self._create_error_response("Factory reset failed")
                
        except Exception as e:
            return self._create_error_response(f"Factory reset error: {e}")

    def _handle_read_config(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle read configuration command."""
        try:
            config_info = {}
            
            # Read current values
            rsw_val = self.config_manager.read_current_config(REG_RSW)
            rate_val = self.config_manager.read_current_config(REG_RRATE)
            baud_val = self.config_manager.read_current_config(REG_BAUD)
            
            if rsw_val is not None:
                config_info["rsw"] = f"0x{rsw_val:04X}"
            if rate_val is not None:
                config_info["rate"] = f"0x{rate_val:04X}"
            if baud_val is not None:
                config_info["baudrate"] = f"0x{baud_val:04X}"
            
            return self._create_success_response("Configuration read", config_info)
            
        except Exception as e:
            return self._create_error_response(f"Read config error: {e}")

    def _handle_raw_hex(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle raw hex command."""
        try:
            hex_command = command_data.get("hex_command", "").strip()
            if not hex_command:
                return self._create_error_response("Missing 'hex_command' field")
            
            # Parse hex command (format: "FF AA REG DATAL DATAH")
            hex_bytes = hex_command.replace(" ", "").replace("0x", "")
            if len(hex_bytes) != 10:  # 5 bytes = 10 hex chars
                return self._create_error_response("Invalid hex command format. Expected: FF AA REG DATAL DATAH")
            
            try:
                # Convert hex string to bytes
                command_bytes = bytes.fromhex(hex_bytes)
                register_addr = command_bytes[2]
                data_low = command_bytes[3]
                data_high = command_bytes[4]
                
                # Send raw command
                if self.config_manager._send_write_command(register_addr, data_low, data_high):
                    return self._create_success_response(f"Raw hex command sent: {hex_command}")
                else:
                    return self._create_error_response("Failed to send raw hex command")
                    
            except ValueError as e:
                return self._create_error_response(f"Invalid hex format: {e}")
                
        except Exception as e:
            return self._create_error_response(f"Raw hex error: {e}")

    def _handle_unlock(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle unlock sensor command."""
        try:
            if self.config_manager.unlock_sensor_for_config():
                return self._create_success_response("Sensor unlocked")
            else:
                return self._create_error_response("Failed to unlock sensor")
                
        except Exception as e:
            return self._create_error_response(f"Unlock error: {e}")

    def _handle_save(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle save configuration command."""
        try:
            if self.config_manager.save_configuration():
                return self._create_success_response("Configuration saved")
            else:
                return self._create_error_response("Failed to save configuration")
                
        except Exception as e:
            return self._create_error_response(f"Save error: {e}")

    def _handle_restart(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle restart sensor command."""
        try:
            if self.config_manager.restart_sensor():
                return self._create_success_response("Sensor restart initiated")
            else:
                return self._create_error_response("Failed to restart sensor")
                
        except Exception as e:
            return self._create_error_response(f"Restart error: {e}")

    def _create_success_response(self, message: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Create success response."""
        response = {
            "status": "success",
            "message": message,
            "timestamp": time.time()
        }
        if data:
            response["data"] = data
        return response

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create error response."""
        return {
            "status": "error",
            "error": error_message,
            "timestamp": time.time()
        }

    def get_command_help(self) -> Dict[str, Any]:
        """Get help information for available commands."""
        return {
            "available_commands": {
                "set_rate": {
                    "description": "Set sensor output rate",
                    "parameters": {"rate": "int (10, 50, 100, 200)"},
                    "example": {"command": "set_rate", "rate": 200}
                },
                "set_output": {
                    "description": "Set sensor output content",
                    "parameters": {"output": "list or comma-separated string"},
                    "example": {"command": "set_output", "output": ["acc", "time"]}
                },
                "set_baudrate": {
                    "description": "Set sensor baudrate",
                    "parameters": {"baudrate": "int (9600, 115200, 230400)"},
                    "example": {"command": "set_baudrate", "baudrate": 115200}
                },
                "factory_reset": {
                    "description": "Perform factory reset",
                    "parameters": {},
                    "example": {"command": "factory_reset"}
                },
                "read_config": {
                    "description": "Read current configuration",
                    "parameters": {},
                    "example": {"command": "read_config"}
                },
                "raw_hex": {
                    "description": "Send raw hex command",
                    "parameters": {"hex_command": "string (FF AA REG DATAL DATAH)"},
                    "example": {"command": "raw_hex", "hex_command": "FF AA 03 00 64"}
                },
                "unlock": {
                    "description": "Unlock sensor for configuration",
                    "parameters": {},
                    "example": {"command": "unlock"}
                },
                "save": {
                    "description": "Save current configuration",
                    "parameters": {},
                    "example": {"command": "save"}
                },
                "restart": {
                    "description": "Restart sensor",
                    "parameters": {},
                    "example": {"command": "restart"}
                }
            }
        }
