# HWT905 Decoder Refactoring Documentation

## Overview

The HWT905 data decoder has been successfully refactored from a monolithic design to a modular architecture using the factory pattern. This refactoring improves maintainability, testability, and extensibility.

## Architecture Changes

### Before (Monolithic Design)
- Single large file (`hwt905_data_decoder.py`) with ~400 lines
- All packet decoding logic in one class
- Difficult to maintain and extend
- Hard to test individual packet types

### After (Modular Design)
- Separated into multiple specialized decoder classes
- Factory pattern for packet type dispatching
- Reduced main decoder class to ~200 lines
- Each decoder is independently testable

## New File Structure

```
src/sensors/decoders/
├── __init__.py                 # Package initialization
├── base_decoder.py            # Abstract base class for all decoders
├── decoder_factory.py         # Factory for managing decoders
├── time_decoder.py            # Time packet decoder
├── acceleration_decoder.py    # Acceleration packet decoder
├── angular_velocity_decoder.py # Angular velocity decoder
├── angle_decoder.py           # Angle packet decoder
├── magnetic_field_decoder.py  # Magnetic field decoder
├── quaternion_decoder.py      # Quaternion decoder
├── gps_decoder.py            # GPS-related decoders
└── misc_decoder.py           # Other packet decoders
```

## Key Components

### 1. BasePacketDecoder
Abstract base class that provides:
- Common byte extraction utilities
- Input validation
- Error handling structure
- Consistent interface for all decoders

### 2. PacketDecoderFactory
Manages decoder registration and dispatching:
- Automatic decoder registration
- Type-safe packet routing
- Easy addition of new packet types
- Centralized decoder management

### 3. Specialized Decoders
Each decoder handles one packet type:
- `TimeDecoder`: 0x50 - Time data
- `AccelerationDecoder`: 0x51 - Acceleration data
- `AngularVelocityDecoder`: 0x52 - Gyroscope data
- `AngleDecoder`: 0x53 - Angle/orientation data
- `MagneticFieldDecoder`: 0x54 - Magnetometer data
- `QuaternionDecoder`: 0x59 - Quaternion data
- Plus GPS and other decoders

### 4. Refactored Main Decoder
The main `HWT905DataDecoder` class now:
- Focuses on serial communication
- Uses factory for packet decoding
- Maintains statistics and error handling
- Provides backward compatibility

## Benefits

### 1. Maintainability
- Each decoder is focused on one packet type
- Clear separation of concerns
- Easier to debug specific packet types
- Reduced cognitive load

### 2. Testability
- Individual decoders can be unit tested
- Mock packets can be easily created
- Isolated testing of packet types
- Better error tracking

### 3. Extensibility
- Adding new packet types is simple
- Just create new decoder class
- Register with factory
- No modification of existing code

### 4. Performance
- Factory pattern provides fast lookup
- Specialized decoders are optimized
- Reduced branching in main decoder
- Better error handling

## Usage

### Basic Usage (Unchanged)
```python
from src.sensors.hwt905_data_decoder import HWT905DataDecoder

# Create decoder (API unchanged)
decoder = HWT905DataDecoder(port='/dev/ttyUSB0', baudrate=9600)

# Use as before
with decoder:
    data = decoder.read_data()
    print(data)
```

### Adding New Decoder
```python
from src.sensors.decoders.base_decoder import BasePacketDecoder

class MyCustomDecoder(BasePacketDecoder):
    def get_packet_type(self) -> int:
        return 0x60  # Your packet type
    
    def decode_payload(self, payload: bytes) -> Dict[str, Any]:
        # Your decoding logic
        return {"custom_data": payload.hex()}

# Register automatically when imported
```

## Testing

A comprehensive test script `test_decoder_refactor.py` has been created to verify:
- Packet decoding functionality
- Factory pattern operation
- Error handling
- Statistics tracking

Run tests with:
```bash
python3.11 test_decoder_refactor.py
```

## Migration Notes

### For Developers
- Import statements remain the same
- Public API is backward compatible
- Internal structure completely changed
- Old decoder backed up as `hwt905_data_decoder_old.py`

### For Maintenance
- Check individual decoder files for packet-specific issues
- Use factory to add new packet types
- Test new decoders independently
- Update factory registration if needed

## Future Enhancements

1. **Configuration-based Decoders**: Load decoder mappings from config
2. **Plugin Architecture**: Dynamic decoder loading
3. **Performance Monitoring**: Per-decoder performance metrics
4. **Advanced Validation**: Packet-specific validation rules
5. **Caching**: Decoder instance caching for performance

## Files Modified

### Replaced
- `src/sensors/hwt905_data_decoder.py` - Completely refactored

### Created
- `src/sensors/decoders/` - New decoder package
- All decoder files in the decoders package
- `test_decoder_refactor.py` - Test suite

### Backed Up
- `src/sensors/hwt905_data_decoder_old.py` - Original implementation

## Verification

The refactoring has been tested and verified:
- ✅ Import compatibility maintained
- ✅ Main application works unchanged
- ✅ All packet types supported
- ✅ Error handling improved
- ✅ Statistics tracking functional
- ✅ Factory pattern operational

## Conclusion

The HWT905 decoder refactoring successfully transforms a monolithic codebase into a clean, modular architecture. The new design is more maintainable, testable, and extensible while maintaining full backward compatibility with existing code.
