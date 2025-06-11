#!/bin/bash

# Script để chạy ứng dụng HWT905 với virtual environment
# Sử dụng: ./run_app.sh

# Đường dẫn đến thư mục project
PROJECT_DIR="/home/trandung/Data/Aitogy Projects/hwt905-raspi"

# Chuyển đến thư mục project
cd "$PROJECT_DIR"

# Kiểm tra xem virtual environment đã tồn tại chưa
if [ ! -d "venv" ]; then
    echo "Tạo virtual environment..."
    python3 -m venv venv
    
    echo "Cài đặt dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Activate virtual environment và chạy ứng dụng
echo "Khởi động ứng dụng HWT905..."
echo "Nhấn Ctrl+C để dừng (chỉ cần bấm một lần sau khi fix)"
source venv/bin/activate
python3 main.py
