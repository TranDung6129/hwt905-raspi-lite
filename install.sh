#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

# --- Script Configuration ---
PYTHON_CMD="python3.11"
VENV_DIR="venv"
PROJECT_NAME="HWT905 Raspi Lite"
TARGET_USER="aitogy"
TARGET_PASSWORD="aitogy"

# --- Helper Functions ---
function print_info() {
    echo -e "\e[34m[INFO]\e[0m $1"
}

function print_success() {
    echo -e "\e[32m[SUCCESS]\e[0m $1"
}

function print_warning() {
    echo -e "\e[33m[WARNING]\e[0m $1"
}

function print_error() {
    echo -e "\e[31m[ERROR]\e[0m $1" >&2
}

function check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "Lệnh '$1' không tìm thấy. Vui lòng cài đặt trước."
        exit 1
    fi
}

# --- Main Installation Logic ---
print_info "Bắt đầu cài đặt $PROJECT_NAME..."

# 1. Check for root privileges
if [[ $EUID -ne 0 ]]; then
   print_error "Kịch bản này cần quyền root. Vui lòng chạy với 'sudo ./install.sh'"
   exit 1
fi

# 2. Check system compatibility
if [[ ! -f "/etc/os-release" ]]; then
    print_warning "Không thể xác định hệ điều hành. Tiếp tục cài đặt..."
else
    source /etc/os-release
    print_info "Hệ điều hành: $PRETTY_NAME"
fi

# 3. System Dependencies
print_info "Đang cập nhật danh sách package và cài đặt các dependency hệ thống..."
apt-get update
apt-get install -y software-properties-common

# Cài đặt Python 3.11 nếu chưa có
if ! command -v python3.11 &> /dev/null; then
    print_info "Python 3.11 chưa được cài đặt. Đang cài đặt..."
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update
    apt-get install -y python3.11 python3.11-venv python3.11-pip python3.11-dev
else
    print_info "Python 3.11 đã được cài đặt."
fi

apt-get install -y libsystemd-dev git wget curl

# Check for additional dependencies for serial communication
apt-get install -y python3-serial

# 4. Create aitogy user if doesn't exist
if ! id "$TARGET_USER" &>/dev/null; then
    print_info "Tạo người dùng '$TARGET_USER'..."
    useradd -m -s /bin/bash "$TARGET_USER"
    echo "$TARGET_USER:$TARGET_PASSWORD" | chpasswd
    usermod -aG sudo "$TARGET_USER"
    print_success "Người dùng '$TARGET_USER' đã được tạo với mật khẩu '$TARGET_PASSWORD'"
else
    print_info "Người dùng '$TARGET_USER' đã tồn tại."
fi

# 5. Project Environment
INSTALL_USER="$TARGET_USER"
INSTALL_GROUP="$TARGET_USER"
PROJECT_DIR=$(pwd)

print_info "Cài đặt cho người dùng: $INSTALL_USER (group: $INSTALL_GROUP)"
print_info "Thư mục dự án: $PROJECT_DIR"

# 6. Set proper ownership of project directory
print_info "Thiết lập quyền sở hữu thư mục dự án cho người dùng '$INSTALL_USER'..."
chown -R "$INSTALL_USER:$INSTALL_GROUP" "$PROJECT_DIR"

# 7. Create data directory
DATA_DIR="$PROJECT_DIR/data"
if [ ! -d "$DATA_DIR" ]; then
    print_info "Tạo thư mục data..."
    sudo -u "$INSTALL_USER" mkdir -p "$DATA_DIR"
else
    print_info "Thư mục data đã tồn tại."
fi

# 8. Create .env file
if [ ! -f ".env" ]; then
    print_info "File .env không tồn tại. Đang tạo từ .env.example..."
    cp .env.example .env
    chown "$INSTALL_USER:$INSTALL_GROUP" .env
    print_warning "Vui lòng kiểm tra và chỉnh sửa file .env với các cấu hình của bạn."
    print_info "Các cấu hình quan trọng:"
    print_info "   - SENSOR_UART_PORT: Cổng kết nối cảm biến (mặc định: /dev/ttyUSB0)"
    print_info "   - DATA_COLLECTION_RATE_HZ: Tần số lưu dữ liệu (mặc định: 200Hz)"
    print_info "   - STORAGE_BASE_DIR: Thư mục lưu dữ liệu (mặc định: data)"
else
    print_info "File .env đã tồn tại. Kiểm tra cấu hình..."
fi

# 9. Python Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    print_info "Đang tạo môi trường ảo Python 3.11 trong '$VENV_DIR'..."
    sudo -u "$INSTALL_USER" $PYTHON_CMD -m venv "$VENV_DIR"
else
    print_info "Thư mục môi trường ảo '$VENV_DIR' đã tồn tại."
fi

print_info "Đang cài đặt các thư viện Python từ requirements.txt..."
sudo -u "$INSTALL_USER" "$PROJECT_DIR/$VENV_DIR/bin/pip3.11" install --upgrade pip
sudo -u "$INSTALL_USER" "$PROJECT_DIR/$VENV_DIR/bin/pip3.11" install -r requirements.txt
print_success "Cài đặt thư viện Python hoàn tất."

# 10. Grant Serial Port Access
print_info "Đang cấp quyền truy cập cổng Serial cho người dùng '$INSTALL_USER'..."
usermod -a -G dialout "$INSTALL_USER"
usermod -a -G tty "$INSTALL_USER"
print_warning "Người dùng '$INSTALL_USER' cần logout và login lại để quyền truy cập cổng Serial có hiệu lực."

# 11. Test sensor connection (optional)
print_info "Kiểm tra kết nối cảm biến..."
SENSOR_PORT=$(grep "SENSOR_UART_PORT" .env | cut -d'=' -f2 | tr -d '"' || echo "/dev/ttyUSB0")
if [ -e "$SENSOR_PORT" ]; then
    print_success "Tìm thấy cổng cảm biến: $SENSOR_PORT"
else
    print_warning "Không tìm thấy cổng cảm biến: $SENSOR_PORT"
    print_info "   Đảm bảo cảm biến đã được kết nối và cổng đúng trong file .env"
fi

# 12. Systemd Service Installation
print_info "Đang cấu hình và cài đặt các file dịch vụ Systemd..."

TEMP_SERVICE_DIR="/tmp/hwt_services"
mkdir -p "$TEMP_SERVICE_DIR"

for service_file in systemd/*; do
    filename=$(basename "$service_file")
    temp_path="$TEMP_SERVICE_DIR/$filename"
    
    print_info "  Đang xử lý file $filename..."
    sed "s#User=pi#User=$INSTALL_USER#g" "$service_file" | \
    sed "s#Group=pi#Group=$INSTALL_GROUP#g" | \
    sed "s#WorkingDirectory=/home/pi/hwt905-raspi-lite#WorkingDirectory=$PROJECT_DIR#g" | \
    sed "s#EnvironmentFile=/home/pi/hwt905-raspi-lite/.env#EnvironmentFile=$PROJECT_DIR/.env#g" | \
    sed "s#ExecStart=/home/pi/hwt905-raspi-lite/venv/bin/python3#ExecStart=$PROJECT_DIR/$VENV_DIR/bin/python3.11#g" > "$temp_path"
done

print_info "Đang sao chép các file dịch vụ vào /etc/systemd/system/..."
cp "$TEMP_SERVICE_DIR"/* /etc/systemd/system/
rm -rf "$TEMP_SERVICE_DIR"

# 13. Enable and Start Services
print_info "Đang reload, enable và start các dịch vụ..."
systemctl daemon-reload
systemctl enable hwt-app.service
systemctl enable hwt-sender.timer
systemctl enable hwt-cleanup.timer

print_info "Khởi động các dịch vụ..."
systemctl restart hwt-app.service
systemctl start hwt-sender.timer
systemctl start hwt-cleanup.timer

# 14. Service Status Check
sleep 5
print_info "Kiểm tra trạng thái dịch vụ..."
if systemctl is-active --quiet hwt-app.service; then
    print_success "hwt-app.service đang chạy"
else
    print_warning "hwt-app.service có vấn đề. Kiểm tra log với: journalctl -u hwt-app.service"
fi

# 15. Run validation script
print_info "Chạy script validation..."
if [ -f "./validate_installation.sh" ]; then
    chmod +x ./validate_installation.sh
    print_info "Chạy validation trong 5 giây..."
    sleep 5
    ./validate_installation.sh
else
    print_warning "Validation script không tồn tại"
fi

print_success "Cài đặt hoàn tất!"
echo "========================================================="
echo "$PROJECT_NAME đã được cài đặt thành công!"
echo ""
echo "Người dùng: $INSTALL_USER (mật khẩu: $TARGET_PASSWORD)"
echo "Python version: $($PYTHON_CMD --version)"
echo ""
echo "Các dịch vụ đã được cài đặt và khởi chạy:"
echo "  - hwt-app.service:      Ứng dụng chính (đọc và lưu dữ liệu góc)"
echo "  - hwt-sender.timer:     Gửi dữ liệu định kỳ"
echo "  - hwt-cleanup.timer:    Dọn dẹp dữ liệu cũ hàng ngày"
echo ""
echo "Cấu hình hiện tại:"
echo "  - Tần số lưu dữ liệu: $(grep DATA_COLLECTION_RATE_HZ .env | cut -d'=' -f2 | tr -d '"' || echo '200')Hz"
echo "  - Thư mục dữ liệu: $DATA_DIR"
echo "  - Cổng cảm biến: $SENSOR_PORT"
echo ""
echo "Để chuyển sang người dùng aitogy:"
echo "  su - aitogy"
echo ""
echo "Lệnh hữu ích:"
echo "  - sudo journalctl -u hwt-app.service -f     (Xem log ứng dụng chính)"
echo "  - sudo journalctl -u hwt-sender.service     (Xem log dịch vụ gửi dữ liệu)"
echo "  - systemctl list-timers                     (Xem trạng thái các timers)"
echo "  - sudo systemctl status hwt-app.service     (Kiểm tra trạng thái dịch vụ)"
echo "  - ls -la $DATA_DIR/                         (Xem file dữ liệu)"
echo ""
echo "Chỉnh sửa cấu hình:"
echo "  - nano .env                                    (Chỉnh sửa cấu hình)"
echo "  - sudo systemctl restart hwt-app.service       (Khởi động lại sau khi đổi cấu hình)"
echo ""
print_warning "Người dùng '$INSTALL_USER' cần logout và login lại để quyền truy cập cổng serial có hiệu lực!"
echo "=========================================================" 