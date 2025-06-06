# Storage Module

This module manages data storage functionality for the HWT905 RaspberryPi sensor system. It has been refactored from the original `data_storage.py` file into multiple focused components.

## Structure

### Files

- `__init__.py` - Module initialization and exports
- `storage_manager.py` - Main interface for storage operations
- `data_storage.py` - Core data storage functionality
- `file_handlers.py` - File format handlers (CSV, JSON)
- `session_manager.py` - Session management

### Classes

#### StorageManager
The main interface class that coordinates storage operations and data transmission.

**Key Features:**
- Configurable storage enable/disable
- Immediate vs. batch transmission modes
- Integration with data processing pipeline

#### ProcessedDataStorage
Core storage functionality for processed sensor data.

**Key Features:**
- Automatic file rotation based on size
- Session-based organization
- Support for multiple storage formats

#### File Handlers
- `CSVFileHandler` - Handles CSV format storage and reading
- `JSONFileHandler` - Handles JSON format storage and reading
- `BaseFileHandler` - Abstract base class for file handlers

#### SessionManager
Manages session creation and tracking for data organization.

## Usage

```python
from src.storage import StorageManager

# Initialize with configuration
storage_config = {
    "enabled": True,
    "format": "csv",
    "immediate_transmission": True,
    "base_dir": "data",
    "max_file_size_mb": 10.0
}

storage_manager = StorageManager(storage_config)

# Store and prepare data for transmission
transmission_data = storage_manager.store_and_prepare_for_transmission(
    processed_data, timestamp
)

# Get batch data for transmission
batch_data = storage_manager.get_batch_for_transmission()
```

## Configuration

The storage system accepts the following configuration options:

- `enabled` (bool): Enable/disable storage functionality
- `format` (str): Storage format ("csv" or "json")
- `immediate_transmission` (bool): Send data immediately vs. batch mode
- `batch_transmission_size` (int): Size of transmission batches
- `base_dir` (str): Base directory for data storage
- `max_file_size_mb` (float): Maximum file size before rotation
- `session_prefix` (str): Prefix for session identifiers

## Data Format

### CSV Format
The CSV format includes the following columns:
- `timestamp` - Unix timestamp
- `acc_x`, `acc_y`, `acc_z` - Acceleration values (g)
- `disp_x`, `disp_y`, `disp_z` - Displacement values (m)
- `disp_magnitude` - Displacement magnitude (m)
- `dominant_freq_x`, `dominant_freq_y`, `dominant_freq_z` - Dominant frequencies (Hz)
- `overall_dominant_freq` - Overall dominant frequency (Hz)
- `rls_warmed_up` - RLS algorithm warm-up status (boolean)

### JSON Format
JSON entries contain:
```json
{
    "timestamp": 1749182726.369,
    "data": {
        "acc_x": 0.00439453125,
        "acc_y": -0.01416015625,
        // ... other fields
    }
}
```

## Migration from Old Structure

This module replaces the monolithic `src/processing/data_storage.py` file with a modular approach:

1. **StorageManager** - Moved from `data_storage.py` to `storage_manager.py`
2. **ProcessedDataStorage** - Refactored and moved to `data_storage.py` 
3. **File handlers** - Extracted to `file_handlers.py`
4. **Session management** - Extracted to `session_manager.py`

## Benefits

- **Separation of Concerns**: Each file has a single responsibility
- **Easier Testing**: Smaller, focused modules are easier to unit test
- **Better Maintainability**: Changes to one aspect don't affect others
- **Extensibility**: Easy to add new file formats or storage backends
- **Cleaner Architecture**: Storage logic is separate from data processing
