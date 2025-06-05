#!/usr/bin/env python3
"""
Data Storage Management Utility

Script tiện ích để quản lý và giám sát dữ liệu được lưu trữ trong hệ thống.
"""

import sys
import os
import argparse
from pathlib import Path
from datetime import datetime

# Thêm thư mục gốc vào Python path
sys.path.append(str(Path(__file__).parent.parent))

from src.processing.data_storage import ProcessedDataStorage

def list_stored_data(data_dir: str = "data"):
    """Liệt kê tất cả dữ liệu đã lưu trữ."""
    print(f"📁 Listing stored data in: {data_dir}")
    print("-" * 50)
    
    data_path = Path(data_dir)
    if not data_path.exists():
        print("❌ Data directory does not exist")
        return
    
    processed_dir = data_path / "processed_data"
    if not processed_dir.exists():
        print("❌ Processed data directory does not exist")
        return
    
    # Group files by session
    sessions = {}
    for file_path in processed_dir.glob("*.csv"):
        # Extract session from filename: session_YYYYMMDD_HHMMSS_partXXX_timestamp.csv
        parts = file_path.stem.split('_')
        if len(parts) >= 4:
            session = '_'.join(parts[:3])  # session_YYYYMMDD_HHMMSS
            if session not in sessions:
                sessions[session] = []
            sessions[session].append(file_path)
    
    for file_path in processed_dir.glob("*.json"):
        # Same logic for JSON files
        parts = file_path.stem.split('_')
        if len(parts) >= 4:
            session = '_'.join(parts[:3])
            if session not in sessions:
                sessions[session] = []
            sessions[session].append(file_path)
    
    if not sessions:
        print("📄 No stored data found")
        return
    
    for session, files in sessions.items():
        print(f"\n🗂️  Session: {session}")
        total_size = 0
        for file_path in sorted(files):
            size_kb = file_path.stat().st_size / 1024
            total_size += size_kb
            modified = datetime.fromtimestamp(file_path.stat().st_mtime)
            print(f"   📄 {file_path.name} ({size_kb:.1f} KB, {modified.strftime('%Y-%m-%d %H:%M:%S')})")
        print(f"   📊 Total size: {total_size:.1f} KB, Files: {len(files)}")

def read_data_sample(file_path: str, lines: int = 5):
    """Đọc một vài dòng mẫu từ file dữ liệu."""
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return
    
    print(f"📖 Reading sample from: {file_path.name}")
    print("-" * 50)
    
    try:
        if file_path.suffix == '.csv':
            with open(file_path, 'r') as f:
                for i, line in enumerate(f):
                    if i >= lines + 1:  # +1 for header
                        break
                    print(f"   {line.strip()}")
        elif file_path.suffix == '.json':
            with open(file_path, 'r') as f:
                for i, line in enumerate(f):
                    if i >= lines:
                        break
                    print(f"   {line.strip()}")
        else:
            print("❌ Unsupported file format")
    except Exception as e:
        print(f"❌ Error reading file: {e}")

def analyze_data_stats(data_dir: str = "data"):
    """Phân tích thống kê dữ liệu."""
    print(f"📊 Analyzing data statistics in: {data_dir}")
    print("-" * 50)
    
    data_path = Path(data_dir)
    processed_dir = data_path / "processed_data"
    
    if not processed_dir.exists():
        print("❌ No processed data directory found")
        return
    
    total_files = 0
    total_size = 0
    oldest_file = None
    newest_file = None
    
    for file_path in processed_dir.glob("*"):
        if file_path.is_file():
            total_files += 1
            file_size = file_path.stat().st_size
            total_size += file_size
            
            modified_time = file_path.stat().st_mtime
            if oldest_file is None or modified_time < oldest_file[1]:
                oldest_file = (file_path, modified_time)
            if newest_file is None or modified_time > newest_file[1]:
                newest_file = (file_path, modified_time)
    
    if total_files == 0:
        print("📄 No data files found")
        return
    
        print(f"📈 Statistics:")
    print(f"   Total files: {total_files}")
    print(f"   Total size: {total_size / 1024:.1f} KB ({total_size / (1024*1024):.3f} MB)")
    print(f"   Average file size: {(total_size / total_files) / 1024:.1f} KB")
    
    if oldest_file:
        oldest_time = datetime.fromtimestamp(oldest_file[1])
        print(f"   Oldest file: {oldest_file[0].name} ({oldest_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    if newest_file:
        newest_time = datetime.fromtimestamp(newest_file[1])
        print(f"   Newest file: {newest_file[0].name} ({newest_time.strftime('%Y-%m-%d %H:%M:%S')})")

def cleanup_old_data(data_dir: str = "data", days: int = 7):
    """Dọn dẹp dữ liệu cũ hơn số ngày chỉ định."""
    print(f"🧹 Cleaning up data older than {days} days in: {data_dir}")
    print("-" * 50)
    
    data_path = Path(data_dir)
    processed_dir = data_path / "processed_data"
    
    if not processed_dir.exists():
        print("❌ No processed data directory found")
        return
    
    import time
    cutoff_time = time.time() - (days * 24 * 60 * 60)
    
    deleted_files = 0
    deleted_size = 0
    
    for file_path in processed_dir.glob("*"):
        if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
            file_size = file_path.stat().st_size
            print(f"   🗑️  Deleting: {file_path.name} ({file_size / 1024:.1f} KB)")
            file_path.unlink()
            deleted_files += 1
            deleted_size += file_size
    
    if deleted_files == 0:
        print("✅ No old files found to delete")
    else:
        print(f"✅ Deleted {deleted_files} files, freed {deleted_size / 1024:.1f} KB")

def monitor_realtime_data(data_dir: str = "data"):
    """Giám sát dữ liệu thời gian thực."""
    print(f"👀 Monitoring real-time data in: {data_dir}")
    print("Press Ctrl+C to stop...")
    print("-" * 50)
    
    data_path = Path(data_dir)
    processed_dir = data_path / "processed_data"
    
    if not processed_dir.exists():
        print("❌ No processed data directory found")
        return
    
    import time
    last_check = time.time()
    
    try:
        while True:
            current_time = time.time()
            new_files = []
            
            for file_path in processed_dir.glob("*"):
                if file_path.is_file() and file_path.stat().st_mtime > last_check:
                    new_files.append(file_path)
            
            if new_files:
                for file_path in new_files:
                    modified = datetime.fromtimestamp(file_path.stat().st_mtime)
                    size_kb = file_path.stat().st_size / 1024
                    print(f"📄 New/Updated: {file_path.name} ({size_kb:.1f} KB) at {modified.strftime('%H:%M:%S')}")
            
            last_check = current_time
            time.sleep(2)  # Check every 2 seconds
            
    except KeyboardInterrupt:
        print("\n✅ Monitoring stopped")

def main():
    parser = argparse.ArgumentParser(description="Data Storage Management Utility")
    parser.add_argument("--data-dir", default="data", help="Data directory path")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List stored data")
    
    # Read command
    read_parser = subparsers.add_parser("read", help="Read sample data from file")
    read_parser.add_argument("file", help="File path to read")
    read_parser.add_argument("--lines", type=int, default=5, help="Number of lines to read")
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show data statistics")
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old data")
    cleanup_parser.add_argument("--days", type=int, default=7, help="Delete files older than this many days")
    
    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor real-time data changes")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_stored_data(args.data_dir)
    elif args.command == "read":
        read_data_sample(args.file, args.lines)
    elif args.command == "stats":
        analyze_data_stats(args.data_dir)
    elif args.command == "cleanup":
        cleanup_old_data(args.data_dir, args.days)
    elif args.command == "monitor":
        monitor_realtime_data(args.data_dir)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
