#!/usr/bin/env python3
"""
Test script for MQTT Remote Configuration Commands.
Demonstrates how to send various configuration commands via MQTT.
"""

import json
import time
import paho.mqtt.client as mqtt
import argparse
from typing import Dict, Any

class MQTTConfigTester:
    """MQTT Configuration Command Tester"""
    
    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = None
        self.connected = False
        
        # Topics
        self.command_topic = "sensor/hwt905/commands"
        self.response_topic = "sensor/hwt905/config_response"
        
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            self.client = mqtt.Client("hwt905_config_tester")
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            
            print(f"Connecting to MQTT broker: {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            while not self.connected and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
                
            return self.connected
            
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for connection"""
        if rc == 0:
            self.connected = True
            print("Connected to MQTT broker")
            # Subscribe to response topic
            client.subscribe(self.response_topic)
            print(f"Subscribed to response topic: {self.response_topic}")
        else:
            print(f"Connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback for received messages"""
        try:
            response = json.loads(msg.payload.decode('utf-8'))
            print(f"\n📨 Response received:")
            print(json.dumps(response, indent=2, ensure_ascii=False))
            print("-" * 50)
        except Exception as e:
            print(f"Error parsing response: {e}")
    
    def send_command(self, command: Dict[str, Any]):
        """Send configuration command"""
        if not self.connected:
            print("Not connected to MQTT broker")
            return False
            
        try:
            payload = json.dumps(command, ensure_ascii=False)
            print(f"\n📤 Sending command:")
            print(json.dumps(command, indent=2, ensure_ascii=False))
            
            self.client.publish(self.command_topic, payload, qos=1)
            print(f"Command sent to topic: {self.command_topic}")
            return True
            
        except Exception as e:
            print(f"Error sending command: {e}")
            return False
    
    def test_read_config(self):
        """Test reading current configuration"""
        command = {"command": "read_config"}
        return self.send_command(command)
    
    def test_set_rate(self, rate: int):
        """Test setting output rate"""
        command = {"command": "set_rate", "rate": rate}
        return self.send_command(command)
    
    def test_set_output(self, output_list: list):
        """Test setting output content"""
        command = {"command": "set_output", "output": output_list}
        return self.send_command(command)
    
    def test_set_baudrate(self, baudrate: int):
        """Test setting baudrate"""
        command = {"command": "set_baudrate", "baudrate": baudrate}
        return self.send_command(command)
    
    def test_raw_hex(self, hex_command: str):
        """Test sending raw hex command"""
        command = {"command": "raw_hex", "hex_command": hex_command}
        return self.send_command(command)
    
    def test_unlock(self):
        """Test unlocking sensor"""
        command = {"command": "unlock"}
        return self.send_command(command)
    
    def test_save(self):
        """Test saving configuration"""
        command = {"command": "save"}
        return self.send_command(command)
    
    def test_factory_reset(self):
        """Test factory reset (use with caution!)"""
        command = {"command": "factory_reset"}
        return self.send_command(command)

def main():
    parser = argparse.ArgumentParser(description='MQTT Config Command Tester')
    parser.add_argument('--broker', default='localhost', help='MQTT broker host')
    parser.add_argument('--port', type=int, default=1883, help='MQTT broker port')
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')
    
    args = parser.parse_args()
    
    # Create tester
    tester = MQTTConfigTester(args.broker, args.port)
    
    if not tester.connect():
        print("Failed to connect to MQTT broker")
        return
    
    try:
        if args.interactive:
            interactive_mode(tester)
        else:
            demo_mode(tester)
    finally:
        tester.disconnect()

def interactive_mode(tester: MQTTConfigTester):
    """Interactive command mode"""
    print("\n🎮 Interactive MQTT Config Mode")
    print("Available commands:")
    print("1. read - Read current configuration")
    print("2. rate <value> - Set output rate (10, 50, 100, 200)")
    print("3. output <list> - Set output content (e.g., acc,time)")
    print("4. baudrate <value> - Set baudrate (9600, 115200, 230400)")
    print("5. hex <command> - Send raw hex command (e.g., FF AA 03 00 64)")
    print("6. unlock - Unlock sensor")
    print("7. save - Save configuration")
    print("8. reset - Factory reset (DANGEROUS!)")
    print("9. quit - Exit")
    print()
    
    while True:
        try:
            cmd = input("Enter command: ").strip().lower()
            
            if cmd == "quit" or cmd == "q":
                break
            elif cmd == "read":
                tester.test_read_config()
            elif cmd.startswith("rate "):
                try:
                    rate = int(cmd.split()[1])
                    tester.test_set_rate(rate)
                except (IndexError, ValueError):
                    print("Usage: rate <value> (10, 50, 100, 200)")
            elif cmd.startswith("output "):
                try:
                    output_str = cmd.split(maxsplit=1)[1]
                    output_list = [item.strip() for item in output_str.split(',')]
                    tester.test_set_output(output_list)
                except IndexError:
                    print("Usage: output <list> (e.g., acc,time)")
            elif cmd.startswith("baudrate "):
                try:
                    baudrate = int(cmd.split()[1])
                    tester.test_set_baudrate(baudrate)
                except (IndexError, ValueError):
                    print("Usage: baudrate <value> (9600, 115200, 230400)")
            elif cmd.startswith("hex "):
                try:
                    hex_cmd = cmd.split(maxsplit=1)[1]
                    tester.test_raw_hex(hex_cmd)
                except IndexError:
                    print("Usage: hex <command> (e.g., FF AA 03 00 64)")
            elif cmd == "unlock":
                tester.test_unlock()
            elif cmd == "save":
                tester.test_save()
            elif cmd == "reset":
                confirm = input("Are you sure? Factory reset will erase all settings (y/N): ")
                if confirm.lower() == 'y':
                    tester.test_factory_reset()
                else:
                    print("Factory reset cancelled")
            else:
                print("Unknown command. Type 'quit' to exit.")
            
            # Wait a moment between commands
            time.sleep(1)
            
        except KeyboardInterrupt:
            break
        except EOFError:
            break
    
    print("\nExiting interactive mode...")

def demo_mode(tester: MQTTConfigTester):
    """Demo mode with predefined commands"""
    print("\n🚀 Demo Mode - Sending test commands...")
    
    # Test sequence
    tests = [
        ("Reading current configuration", lambda: tester.test_read_config()),
        ("Setting rate to 100 Hz", lambda: tester.test_set_rate(100)),
        ("Setting output to acc,time", lambda: tester.test_set_output(["acc", "time"])),
        ("Unlocking sensor", lambda: tester.test_unlock()),
        ("Saving configuration", lambda: tester.test_save()),
        ("Sending raw hex command (read rate register)", lambda: tester.test_raw_hex("FF AA 27 03 00")),
    ]
    
    for description, test_func in tests:
        print(f"\n🧪 {description}...")
        test_func()
        time.sleep(3)  # Wait between tests
    
    print("\n✅ Demo completed!")

if __name__ == "__main__":
    main()
