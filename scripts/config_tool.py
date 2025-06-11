#!/usr/bin/env python3
"""
HWT905 Sensor Configuration Tool - Simplified and Modern
Sử dụng HWT905UnifiedConfigManager để cấu hình cảm biến độc lập.

Usage:
    python3 scripts/config_tool.py --rate 200 --output acc,time
    python3 scripts/config_tool.py --baudrate 115200
    python3 scripts/config_tool.py --factory-reset
    python3 scripts/config_tool.py --info
"""

import sys
import logging
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.utils.common import load_config
from src.sensors.config import HWT905UnifiedConfigManager
from src.sensors.hwt905_constants import (
    RATE_OUTPUT_10HZ, RATE_OUTPUT_50HZ, RATE_OUTPUT_100HZ, RATE_OUTPUT_200HZ,
    BAUD_RATE_9600, BAUD_RATE_115200, BAUD_RATE_230400,
    RSW_ACC_BIT, RSW_GYRO_BIT, RSW_ANGLE_BIT, RSW_MAG_BIT,
    RSW_TIME_BIT, RSW_PRESSURE_HEIGHT_BIT, RSW_GPS_LON_LAT_BIT,
    RSW_GPS_SPEED_BIT, RSW_QUATERNION_BIT, RSW_GPS_ACCURACY_BIT, RSW_PORT_STATUS_BIT,
    REG_RSW, REG_RRATE, REG_BAUD
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_output_content(output_str):
    """Parse output content string to RSW value"""
    rsw_value = 0
    content_map = {
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
    
    for content in output_str.split(','):
        content = content.strip().lower()
        if content in content_map:
            rsw_value |= content_map[content]
        else:
            logger.warning(f"Unknown output content: {content}")
    
    return rsw_value

def main():
    parser = argparse.ArgumentParser(description='HWT905 Sensor Configuration Tool')
    parser.add_argument('--rate', type=int, choices=[10, 50, 100, 200],
                        help='Set output rate in Hz')
    parser.add_argument('--output', type=str,
                        help='Set output content (comma-separated): acc,gyro,angle,mag,time,etc.')
    parser.add_argument('--baudrate', type=int, choices=[9600, 115200, 230400],
                        help='Set serial baudrate')
    parser.add_argument('--factory-reset', action='store_true',
                        help='Perform factory reset')
    parser.add_argument('--info', action='store_true',
                        help='Read current sensor configuration')
    
    args = parser.parse_args()
    
    if not any([args.rate, args.output, args.baudrate, args.factory_reset, args.info]):
        parser.print_help()
        return
    
    try:
        # Load configuration
        config_path = project_root / "config" / "app_config.json"
        app_config = load_config(str(config_path))
        sensor_config = app_config["sensor"]
        
        logger.info("Khởi tạo config manager...")
        config_manager = HWT905UnifiedConfigManager(
            port=sensor_config["uart_port"],
            baudrate=sensor_config["baud_rate"],
            timeout=5.0,
            debug=True
        )
        
        # Không cần kết nối manual - unified manager tự quản lý
        
        if args.info:
            logger.info("Đọc thông tin cấu hình hiện tại...")
            try:
                rsw_val = config_manager.read_current_config(REG_RSW)
                rate_val = config_manager.read_current_config(REG_RRATE)
                baud_val = config_manager.read_current_config(REG_BAUD)
                
                if rsw_val is not None:
                    logger.info(f"RSW (Output Content): 0x{rsw_val:04X}")
                if rate_val is not None:
                    logger.info(f"RRATE (Output Rate): 0x{rate_val:04X}")
                if baud_val is not None:
                    logger.info(f"BAUD (Baudrate): 0x{baud_val:04X}")
            except Exception as e:
                logger.error(f"Lỗi đọc cấu hình: {e}")
                
        if args.factory_reset:
            logger.info("Thực hiện factory reset...")
            if config_manager.unlock_sensor_for_config():
                if config_manager.factory_reset():
                    logger.info("Factory reset thành công.")
                else:
                    logger.error("Factory reset thất bại.")
            else:
                logger.error("Không thể unlock sensor.")
                
        if args.baudrate:
            logger.info(f"Đang thiết lập baudrate: {args.baudrate}")
            baudrate_map = {9600: BAUD_RATE_9600, 115200: BAUD_RATE_115200, 230400: BAUD_RATE_230400}
            if config_manager.unlock_sensor_for_config():
                if config_manager.set_baudrate(baudrate_map[args.baudrate]):
                    config_manager.save_configuration()
                    logger.info(f"Baudrate đã được thiết lập thành {args.baudrate}. Cảm biến sẽ restart.")
                else:
                    logger.error("Thiết lập baudrate thất bại.")
            else:
                logger.error("Không thể unlock sensor.")
                
        if args.rate:
            logger.info(f"Đang thiết lập output rate: {args.rate} Hz")
            rate_map = {10: RATE_OUTPUT_10HZ, 50: RATE_OUTPUT_50HZ, 100: RATE_OUTPUT_100HZ, 200: RATE_OUTPUT_200HZ}
            if config_manager.unlock_sensor_for_config():
                if config_manager.set_update_rate(rate_map[args.rate]):
                    config_manager.save_configuration()
                    logger.info(f"Output rate đã được thiết lập thành {args.rate} Hz.")
                else:
                    logger.error("Thiết lập output rate thất bại.")
            else:
                logger.error("Không thể unlock sensor.")
                
        if args.output:
            rsw_value = parse_output_content(args.output)
            logger.info(f"Đang thiết lập output content: {args.output} (RSW=0x{rsw_value:04X})")
            if config_manager.unlock_sensor_for_config():
                if config_manager.set_output_content(rsw_value):
                    config_manager.save_configuration()
                    logger.info(f"Output content đã được thiết lập.")
                else:
                    logger.error("Thiết lập output content thất bại.")
            else:
                logger.error("Không thể unlock sensor.")
                
    except Exception as e:
        logger.error(f"Lỗi: {e}")
    finally:
        if 'config_manager' in locals():
            config_manager.close()

if __name__ == "__main__":
    main()
