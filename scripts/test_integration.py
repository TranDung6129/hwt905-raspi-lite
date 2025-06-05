#!/usr/bin/env python3
"""
Test script to demonstrate integrated storage functionality
with simulated sensor data processing.
"""

import time
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from processing.data_processor import SensorDataProcessor
from utils.common import load_config

def test_continuous_processing():
    """Test continuous data processing with storage integration."""
    print("🧪 Testing Integrated Storage System")
    print("=" * 50)
    
    # Load configuration
    try:
        app_config = load_config("config/app_config.json")
        storage_config = app_config.get("data_storage", {"enabled": True})
        storage_config["base_dir"] = "test_integration_data"
        
        # Enable storage and immediate transmission
        storage_config["enabled"] = True
        storage_config["immediate_transmission"] = True
        storage_config["format"] = "csv"
        
        print(f"📋 Storage Configuration:")
        print(f"   Enabled: {storage_config['enabled']}")
        print(f"   Immediate transmission: {storage_config['immediate_transmission']}")
        print(f"   Format: {storage_config['format']}")
        print(f"   Base directory: {storage_config['base_dir']}")
        print()
        
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Create enhanced processor
    try:
        processor = SensorDataProcessor(
            dt_sensor=0.005,  # 200Hz sampling
            gravity_g=9.80665,
            rls_sample_frame_size=10,
            rls_calc_frame_multiplier=20,
            fft_n_points=64,
            storage_config=storage_config
        )
        print("✅ Enhanced processor created successfully")
    except Exception as e:
        print(f"❌ Error creating processor: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Simulate continuous data processing
    print("\n🔄 Starting continuous data simulation...")
    print("   Processing samples every 5ms (200Hz)")
    print("   Press Ctrl+C to stop\n")
    
    sample_count = 0
    transmission_count = 0
    
    try:
        while sample_count < 100:  # Process 100 samples (0.5 seconds of data)
            # Simulate realistic acceleration data with some noise
            base_time = time.time()
            
            # Simulate vibration with some frequency components
            t = sample_count * 0.005  # Time in seconds
            acc_x = 0.1 + 0.05 * abs(t * 10 % 1 - 0.5)  # Some variation
            acc_y = 0.2 + 0.03 * abs(t * 15 % 1 - 0.5)
            acc_z = 1.0 + 0.02 * abs(t * 8 % 1 - 0.5)   # Near 1g with small variation
            
            # Process the sample
            result = processor.process_new_sample(acc_x, acc_y, acc_z)
            
            if result:
                transmission_count += 1
                print(f"📡 Sample {sample_count + 1}: Ready for transmission")
                print(f"   Timestamp: {result.get('timestamp', 'N/A')}")
                
                # Safely display acceleration values
                try:
                    acc_x_val = float(result['acc_x'])
                    acc_y_val = float(result['acc_y'])
                    acc_z_val = float(result['acc_z'])
                    print(f"   Acceleration: ({acc_x_val:.3f}, {acc_y_val:.3f}, {acc_z_val:.3f}) g")
                except:
                    print(f"   Acceleration: ({result['acc_x']}, {result['acc_y']}, {result['acc_z']}) g")
                
                if 'displacement_magnitude' in result:
                    try:
                        disp_val = float(result['displacement_magnitude'])
                        print(f"   Displacement magnitude: {disp_val:.6f} m")
                    except:
                        print(f"   Displacement magnitude: {result['displacement_magnitude']} m")
                
                print()
            else:
                if sample_count % 10 == 0:  # Show progress every 10 samples
                    print(f"🔄 Processing sample {sample_count + 1}/100...")
            
            sample_count += 1
            time.sleep(0.005)  # 200Hz sampling rate
            
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    
    print(f"\n📊 Processing Summary:")
    print(f"   Total samples processed: {sample_count}")
    print(f"   Samples ready for transmission: {transmission_count}")
    print(f"   Transmission rate: {transmission_count/sample_count*100:.1f}%")
    
    # Test batch retrieval (for offline scenarios)
    print(f"\n📦 Testing batch retrieval for offline transmission...")
    batch = processor.storage_manager.get_batch_for_transmission()
    if batch:
        print(f"   Retrieved batch of {len(batch)} samples for offline transmission")
        print(f"   First sample timestamp: {batch[0].get('timestamp', 'N/A')}")
        print(f"   Last sample timestamp: {batch[-1].get('timestamp', 'N/A')}")
    else:
        print("   No batch data available")
    
    print(f"\n✅ Integration test completed successfully!")

if __name__ == "__main__":
    test_continuous_processing()
