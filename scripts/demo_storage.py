#!/usr/bin/env python3
"""
Storage System Demonstration Script

Script này demo khả năng lưu trữ và truyền dữ liệu của hệ thống mới.
Hiển thị cách dữ liệu được lưu vào thư mục data và cách truy xuất để truyền đi.
"""

import sys
import os
import time
import json
from pathlib import Path

# Thêm thư mục gốc vào Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.processing.data_storage import ProcessedDataStorage, StorageManager
from src.processing.data_processor import SensorDataProcessor
from src.utils.common import load_config

def demo_storage_basic():
    """Demo chức năng cơ bản của storage system."""
    print("=== DEMO: Basic Storage Functionality ===")
    
    # Khởi tạo storage
    storage = ProcessedDataStorage(
        base_data_dir="demo_data",
        storage_format="csv",
        max_file_size_mb=1.0,  # File nhỏ để demo
        session_prefix="demo"
    )
    
    # Tạo một số dữ liệu mẫu
    sample_data = [
        {
            'acc_x': 0.1, 'acc_y': 0.2, 'acc_z': 0.9,
            'displacement_x': 0.001, 'displacement_y': 0.002, 'displacement_z': 0.0,
            'displacement_magnitude': 0.0022,
            'dominant_frequency_x': 1.5, 'dominant_frequency_y': 2.0, 'dominant_frequency_z': 1.8,
            'overall_dominant_frequency': 2.0,
            'rls_warmed_up': True
        },
        {
            'acc_x': 0.15, 'acc_y': 0.18, 'acc_z': 0.95,
            'displacement_x': 0.0015, 'displacement_y': 0.0018, 'displacement_z': 0.001,
            'displacement_magnitude': 0.0027,
            'dominant_frequency_x': 1.6, 'dominant_frequency_y': 1.9, 'dominant_frequency_z': 1.7,
            'overall_dominant_frequency': 1.9,
            'rls_warmed_up': True
        }
    ]
    
    print(f"Storing {len(sample_data)} data samples...")
    
    # Lưu dữ liệu
    for i, data in enumerate(sample_data):
        timestamp = time.time() + i
        storage.store_processed_data(data, timestamp)
        print(f"  Stored sample {i+1} at timestamp {timestamp}")
        time.sleep(0.1)  # Simulate processing delay
    
    # Lấy danh sách file đã tạo
    files = storage.get_stored_data_files()
    print(f"\nCreated files: {[f.name for f in files]}")
    
    # Đọc dữ liệu từ file
    if files:
        print(f"\nReading data from {files[0].name}:")
        stored_data = storage.read_stored_data(files[0])
        for item in stored_data:
            print(f"  Timestamp: {item['timestamp']}, Acc: ({item['acc_x']}, {item['acc_y']}, {item['acc_z']})")
    
    storage.close()
    print("✅ Basic storage demo completed\n")

def demo_storage_manager():
    """Demo StorageManager với các chế độ khác nhau."""
    print("=== DEMO: Storage Manager ===")
    
    # Demo 1: Immediate transmission mode
    print("1. Immediate Transmission Mode:")
    config1 = {
        "enabled": True,
        "immediate_transmission": True,
        "base_dir": "demo_data_manager",
        "format": "json",
        "max_file_size_mb": 1.0
    }
    
    manager1 = StorageManager(config1)
    
    test_data = {
        'acc_x': 0.12, 'acc_y': 0.25, 'acc_z': 0.88,
        'displacement_magnitude': 0.003,
        'rls_warmed_up': True
    }
    
    result = manager1.store_and_prepare_for_transmission(test_data)
    print(f"  Data stored and returned for immediate transmission: {result is not None}")
    if result:
        print(f"  Sample returned data: acc_x={result['acc_x']}, acc_y={result['acc_y']}")
    
    manager1.close()
    
    # Demo 2: Storage-only mode
    print("\n2. Storage-Only Mode:")
    config2 = {
        "enabled": True,
        "immediate_transmission": False,
        "batch_transmission_size": 10,
        "base_dir": "demo_data_manager",
        "format": "csv"
    }
    
    manager2 = StorageManager(config2)
    
    # Store multiple samples
    for i in range(5):
        sample = {
            'acc_x': 0.1 + i*0.01, 'acc_y': 0.2 + i*0.01, 'acc_z': 0.9 + i*0.005,
            'displacement_magnitude': 0.001 + i*0.0005,
            'rls_warmed_up': True
        }
        result = manager2.store_and_prepare_for_transmission(sample)
        print(f"  Sample {i+1}: stored, immediate transmission = {result is not None}")
    
    # Get batch for transmission
    batch = manager2.get_batch_for_transmission()
    print(f"  Retrieved batch of {len(batch)} items for transmission")
    
    manager2.close()
    print("✅ Storage manager demo completed\n")

def demo_enhanced_processor():
    """Demo SensorDataProcessor với storage."""
    print("=== DEMO: Enhanced Sensor Data Processor ===")
    
    # Load config
    try:
        app_config = load_config("config/app_config.json")
        storage_config = app_config.get("data_storage", {"enabled": True})
        storage_config["base_dir"] = "demo_data_processor"  # Use separate dir for demo
        
        # Tạo processor với storage
        processor = SensorDataProcessor(
            dt_sensor=0.005,
            gravity_g=9.80665,
            rls_sample_frame_size=5,  # Smaller for quick demo
            rls_calc_frame_multiplier=10,
            fft_n_points=32,  # Smaller for quick demo
            storage_config=storage_config
        )
        
        print("Processing acceleration samples with storage...")
        
        # Simulate some acceleration data
        acc_samples = [
            (0.1, 0.2, 1.0),
            (0.12, 0.18, 1.02),
            (0.08, 0.22, 0.98),
            (0.15, 0.17, 1.05),
            (0.09, 0.21, 0.97),
            (0.13, 0.19, 1.01),
        ]
        
        transmission_count = 0
        for i, (acc_x, acc_y, acc_z) in enumerate(acc_samples):
            result = processor.process_new_sample(acc_x, acc_y, acc_z)
            if result:
                transmission_count += 1
                print(f"  Sample {i+1}: Processed and ready for transmission")
                # Convert numpy arrays to floats for formatting safely
                try:
                    acc_x_val = float(result['acc_x'])
                    acc_y_val = float(result['acc_y']) 
                    acc_z_val = float(result['acc_z'])
                    print(f"    Acc: ({acc_x_val:.3f}, {acc_y_val:.3f}, {acc_z_val:.3f})")
                except (ValueError, TypeError):
                    print(f"    Acc: ({result['acc_x']}, {result['acc_y']}, {result['acc_z']})")
                
                if 'displacement_magnitude' in result:
                    try:
                        disp_val = float(result['displacement_magnitude'])
                        print(f"    Displacement magnitude: {disp_val:.6f}")
                    except (ValueError, TypeError):
                        print(f"    Displacement magnitude: {result['displacement_magnitude']}")
            else:
                print(f"  Sample {i+1}: Processed, building buffer...")
        
        print(f"\nTotal samples ready for transmission: {transmission_count}")
        
        # Demo batch retrieval for offline transmission
        batch = processor.get_batch_for_transmission()
        print(f"Batch data available for offline transmission: {len(batch)} items")
        
        processor.close()
        print("✅ Enhanced processor demo completed\n")
        
    except Exception as e:
        print(f"❌ Enhanced processor demo failed: {e}")

def demo_data_directory_structure():
    """Hiển thị cấu trúc thư mục data được tạo."""
    print("=== DEMO: Data Directory Structure ===")
    
    data_dirs = ["demo_data", "demo_data_manager", "demo_data_processor", "data"]
    
    for data_dir in data_dirs:
        data_path = Path(data_dir)
        if data_path.exists():
            print(f"\n📁 {data_dir}/")
            for item in data_path.rglob("*"):
                if item.is_file():
                    size_kb = item.stat().st_size / 1024
                    relative_path = item.relative_to(data_path)
                    print(f"  📄 {relative_path} ({size_kb:.1f} KB)")
        else:
            print(f"\n📁 {data_dir}/ (not created)")

def main():
    """Chạy tất cả các demo."""
    print("🚀 Storage System Demonstration")
    print("=" * 50)
    
    try:
        demo_storage_basic()
        demo_storage_manager()
        demo_enhanced_processor()
        demo_data_directory_structure()
        
        print("=" * 50)
        print("✅ All demonstrations completed successfully!")
        print("\n💡 Key Features Demonstrated:")
        print("  • Automatic data storage during processing")
        print("  • Configurable immediate vs. batch transmission")
        print("  • CSV and JSON storage formats")
        print("  • File rotation based on size limits")
        print("  • Integration with existing processing pipeline")
        print("  • Support for intermittent connectivity scenarios")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
