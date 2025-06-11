# Changelog

All notable changes to the HWT905 RaspberryPi Sensor Data Processing System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0] - 2025-06-11

### Added
- **Standalone MQTT Configuration Service**: Independent service for remote sensor configuration
  - Runs separately from main application for field deployment flexibility
  - Service architecture allows configuration while data logging continues
  - Automatic reconnection and health monitoring
  - Graceful shutdown handling with signal support
- **MQTT Config Command Handler**: Handles high-level and raw hex commands
- **MQTT Config Subscriber**: Dedicated MQTT communication for configuration
- **Service Management Scripts**:
  - `scripts/start_mqtt_config.sh`: Startup script for config service
  - `scripts/demo_system.sh`: Demo script to run both services simultaneously
- **MQTT Config Tester**: Enhanced testing tool for MQTT configuration commands
- **Web Interface**: HTML interface for graphical MQTT command sending
- **Remote Command Support**:
  - Set output rate (10, 50, 100, 200 Hz)
  - Set output content (acc, gyro, angle, mag, time, etc.)
  - Set baudrate (9600, 115200, 230400)
  - Send raw hex commands (FF AA REG DATAL DATAH format)
  - Factory reset, unlock, save, restart sensor
  - Read current configuration

### Changed
- **Main Application**: Removed MQTT config integration for cleaner separation
- **Service Architecture**: MQTT config now runs as independent service
- **Documentation**: Updated with standalone service usage patterns
- **MQTT Module**: Reorganized with config subdirectory structure

### Enhanced
- **Error Handling**: Improved import handling and module organization
- **Logger Setup**: Added simple setup_logger function for services
- **Startup Scripts**: Enhanced with dependency checking and validation

### Fixed
- **Import Issues**: Resolved circular imports in MQTT module
- **Service Independence**: Config service no longer conflicts with main app

### Configuration Topics
- **Commands**: `hwt905/commands` (subscribe)
- **Responses**: `hwt905/responses` (publish)
- **Status**: `sensor/hwt905/status` (publish)

## [2.2.1] - 2025-06-11

### Added
- Modern configuration tool (`scripts/config_tool.py`) using HWT905UnifiedConfigManager
- Organized workspace structure with scripts directory

### Changed
- Moved shell scripts to `scripts/` directory for better organization
- Simplified configuration tool implementation using unified config manager

### Removed
- Legacy `sensor_config_tool.py` (replaced by `scripts/config_tool.py`)
- Deprecated `HWT905ConfigManager` class (replaced by `HWT905UnifiedConfigManager`)
- Temporary documentation files (content merged into main docs)
- Test files after successful validation

### Fixed
- Workspace organization and structure
- Removed redundant and deprecated components

## [2.2.0] - 2025-06-11

### Added
- Dedicated sensor configuration tool (`sensor_config_tool.py`)
- Support for standalone sensor configuration without running main application
- Command-line interface for setting output rate, content, baudrate, and factory reset
- Comprehensive documentation for configuration options

### Changed
- **BREAKING**: Removed automatic sensor reconfiguration from main application startup
- Startup process now only verifies connection and starts data reading immediately
- Cleaner separation between configuration and operational concerns
- Reduced startup time by 2-3 seconds

### Improved
- Faster application startup
- Cleaner operational logs (no configuration noise)
- Safer operation (no accidental configuration changes)
- Better user experience for configuration management

### Rationale
HWT905 sensors persist configuration across power cycles, making automatic reconfiguration on every startup unnecessary and potentially problematic. This change optimizes for production usage where sensors are configured once and then operated continuously.

## [2.1.0] - 2025-06-11

### Fixed
- **Input/Output Error Spam**: Added proper throttling for OSError (Errno 5) to prevent log flooding
- **Ctrl+C Signal Handling**: Enhanced signal processing to ensure single keypress shutdown
- **Connection Loss Detection**: Improved SerialReaderThread to detect and handle disconnections gracefully

### Added
- Proper signal handlers for SIGINT and SIGTERM
- OSError handling with time-based throttling (5-second intervals)
- Virtual environment setup and dependency management scripts
- Comprehensive test scripts for error handling verification

### Changed
- Enhanced exception handling in `hwt905_data_decoder.py`
- Improved main loop stability and shutdown procedure
- Better error logging with reduced spam

### Technical Details
- OSError (including Errno 5) now uses same throttling mechanism as SerialException
- SerialReaderThread automatically stops when connection loss is detected
- Signal handlers provide graceful shutdown with proper resource cleanup

## [2.0.0] - 2025-05-XX

### Added
- MQTT module refactoring with strategy pattern (BasePublisher, RealtimePublisher, BatchPublisher)
- Asynchronous data pipeline with four independent threads
- Configurable payload compression using zlib and msgpack
- Enhanced data storage with automatic file rotation

### Changed
- Complete pipeline architecture overhaul for better performance
- Queue-based communication between processing stages
- Modular MQTT publishing strategies

### Fixed
- Serialization errors with numpy arrays
- Import and naming conflicts in MQTT modules

## [1.0.0] - 2025-04-XX

### Added
- Initial implementation of HWT905 sensor data processing
- Basic RLS (Recursive Least Squares) integration algorithms
- FFT analysis for frequency domain processing
- Local CSV data storage
- Serial communication with HWT905 sensors
- Configuration management system

### Features
- Real-time acceleration data processing at up to 200Hz
- Velocity and displacement calculation through integration
- Frequency analysis and dominant frequency extraction
- Configurable sensor parameters (output rate, content, baudrate)
- Robust error handling and logging system
