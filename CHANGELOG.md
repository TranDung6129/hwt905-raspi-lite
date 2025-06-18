# Changelog

All notable changes to the HWT905 RaspberryPi Sensor Data Processing System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.0] - 2025-06-18

### Added
- **Auto-Reconnection System**: Intelligent automatic sensor connection recovery
  - Real-time detection of USB/serial device disconnections
  - Automatic thread management and restart capabilities
  - Queue cleanup to prevent stale data processing
  - Configurable retry limits and delays
  - Zero manual intervention required for common hardware issues
- **Enhanced Connection Monitoring**: Continuous connection health checking
- **Thread-Safe Recovery**: Safe shutdown and restart of all processing threads
- **Production Reliability Features**: 
  - Handles cable disconnections automatically
  - Recovers from USB port resets
  - Manages power fluctuation scenarios
  - Maintains continuous data logging with minimal loss

### Enhanced
- **SerialReaderThread**: Added connection loss detection with event signaling
- **Main Application Loop**: Implemented reconnection workflow with timeout handling
- **Connection Manager**: Enhanced with retry logic and connection validation
- **Error Handling**: Improved I/O error detection and recovery procedures
- **Logging**: Added detailed reconnection event logging for monitoring

### Fixed
- **Connection Loss Handling**: System no longer terminates on sensor disconnection
- **Thread Management**: Proper cleanup and restart of all processing threads
- **Queue Management**: Prevents data corruption during reconnection events
- **MQTT Reconnection**: Ensures MQTT connections are re-established after sensor recovery
- **MQTT Warning Log Spam**: Eliminated repetitive WARNING messages for unpublished MQTT messages
  - Single throttled warning line shows recent Mid values instead of spamming logs
  - Implemented 5-second throttling with Mid aggregation for better monitoring

### Technical Improvements
- Added `connection_lost` event flag in SerialReaderThread
- Implemented maximum retry attempt limits (configurable)
- Enhanced main loop with nested connection monitoring
- Improved error throttling to prevent log spam
- Added graceful thread termination with timeouts
- **MQTT Publisher Throttling**: Added intelligent warning aggregation for unpublished messages
  - Collects multiple Mid values and displays them in consolidated warnings
  - Prevents memory leaks by maintaining only recent 50 Mid values
  - Shows up to 10 recent Mids with total count for better debugging

### Production Benefits
- **Industrial Reliability**: System handles common field deployment issues automatically
- **Reduced Maintenance**: Eliminates need for manual restarts due to connection issues
- **Continuous Operation**: Maintains data collection during temporary disconnections
- **Remote Monitoring**: Connection events are logged and can be monitored remotely

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
