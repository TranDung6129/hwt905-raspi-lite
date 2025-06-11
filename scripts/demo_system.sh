#!/bin/bash
# Demo script để test HWT905 system với MQTT config service
# Chạy cả main app và config service đồng thời

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT" || {
    echo "❌ Error: Cannot change to project directory"
    exit 1
}

echo "🚀 HWT905 System Demo"
echo "===================="
echo "📂 Project: $PROJECT_ROOT"
echo ""

# Kiểm tra dependencies
echo "🔍 Checking dependencies..."
python3 -c "import serial, paho.mqtt.client" 2>/dev/null || {
    echo "❌ Missing dependencies. Please install:"
    echo "   pip install pyserial paho-mqtt"
    exit 1
}

echo "✅ Dependencies OK"
echo ""

# Tạo session IDs
MAIN_SESSION="hwt905_main_$$"
CONFIG_SESSION="hwt905_config_$$"

echo "📋 Starting services..."
echo "   Main app session: $MAIN_SESSION"
echo "   Config service session: $CONFIG_SESSION" 
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    
    # Kill main app
    if tmux has-session -t "$MAIN_SESSION" 2>/dev/null; then
        tmux kill-session -t "$MAIN_SESSION"
        echo "   ✅ Main app stopped"
    fi
    
    # Kill config service  
    if tmux has-session -t "$CONFIG_SESSION" 2>/dev/null; then
        tmux kill-session -t "$CONFIG_SESSION"
        echo "   ✅ Config service stopped"
    fi
    
    echo "🏁 Demo completed"
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Kiểm tra tmux
if ! command -v tmux &> /dev/null; then
    echo "❌ tmux is required for this demo"
    echo "   Install with: sudo apt install tmux"
    exit 1
fi

# Start main application in tmux
echo "▶️  Starting main application..."
tmux new-session -d -s "$MAIN_SESSION" -c "$PROJECT_ROOT" \
    "echo '🔥 HWT905 Main Application'; echo '========================='; ./scripts/run_app.sh"

sleep 2

# Start config service in tmux
echo "▶️  Starting MQTT config service..."
tmux new-session -d -s "$CONFIG_SESSION" -c "$PROJECT_ROOT" \
    "echo '📡 HWT905 MQTT Config Service'; echo '============================'; ./scripts/start_mqtt_config.sh"

sleep 2

echo ""
echo "✅ Services started successfully!"
echo ""
echo "📊 Service Status:"
echo "=================="

# Check main app
if tmux has-session -t "$MAIN_SESSION" 2>/dev/null; then
    echo "   ✅ Main Application: Running (session: $MAIN_SESSION)"
else
    echo "   ❌ Main Application: Failed to start"
fi

# Check config service
if tmux has-session -t "$CONFIG_SESSION" 2>/dev/null; then
    echo "   ✅ Config Service: Running (session: $CONFIG_SESSION)"
else
    echo "   ❌ Config Service: Failed to start"
fi

echo ""
echo "🎮 Control Commands:"
echo "==================="
echo "   View main app logs:    tmux attach-session -t $MAIN_SESSION"
echo "   View config logs:      tmux attach-session -t $CONFIG_SESSION"
echo "   Test config commands:  python3 scripts/mqtt_config_tester.py"
echo "   Stop demo:             Ctrl+C (or run this script again)"

echo ""
echo "⏳ Demo running... Press Ctrl+C to stop"

# Keep script running
while true; do
    sleep 5
    
    # Check if sessions are still alive
    if ! tmux has-session -t "$MAIN_SESSION" 2>/dev/null; then
        echo "⚠️ Main application session ended"
        break
    fi
    
    if ! tmux has-session -t "$CONFIG_SESSION" 2>/dev/null; then
        echo "⚠️ Config service session ended"
        break
    fi
done
