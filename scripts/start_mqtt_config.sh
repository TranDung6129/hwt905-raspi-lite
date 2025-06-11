#!/bin/bash
# Start HWT905 MQTT Configuration Service
# Chạy service cấu hình MQTT độc lập với main application

# Đường dẫn tới project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Chuyển đến thư mục project
cd "$PROJECT_ROOT" || {
    echo "❌ Error: Cannot change to project directory: $PROJECT_ROOT"
    exit 1
}

echo "🚀 Starting HWT905 MQTT Configuration Service..."
echo "📂 Project root: $PROJECT_ROOT"
echo ""

# Kiểm tra virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️ Warning: No virtual environment activated"
    echo "💡 Consider running: source venv/bin/activate"
    echo ""
fi

# Kiểm tra dependencies
if ! python3 -c "import paho.mqtt.client" 2>/dev/null; then
    echo "❌ Error: Missing paho-mqtt dependency"
    echo "💡 Install with: pip install paho-mqtt"
    exit 1
fi

# Chạy service với log level INFO (có thể thay đổi thành DEBUG)
python3 scripts/mqtt_config_service.py \
    --log-level INFO \
    "$@"

echo "✅ MQTT Configuration Service stopped"
