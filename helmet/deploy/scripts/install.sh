#!/bin/bash
# Installation script for Helmet OS on Jetson

set -e

INSTALL_DIR="/opt/helmet"
SERVICE_USER="helmet"
VENV_DIR="$INSTALL_DIR/venv"

echo "Installing Helmet OS..."

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)"
   exit 1
fi

# Create system user
echo "Creating system user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/false -d $INSTALL_DIR $SERVICE_USER
    usermod -a -G video,audio,dialout $SERVICE_USER
fi

# Create installation directory
echo "Setting up directory structure..."
mkdir -p $INSTALL_DIR
mkdir -p $INSTALL_DIR/{logs,recordings,models}
mkdir -p /var/log/helmet

# Copy application files
echo "Copying application files..."
cp -r . $INSTALL_DIR/
chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR
chown -R $SERVICE_USER:$SERVICE_USER /var/log/helmet

# Set up Python virtual environment
echo "Setting up Python environment..."
cd $INSTALL_DIR
python3 -m venv $VENV_DIR
$VENV_DIR/bin/pip install --upgrade pip

# Install dependencies
echo "Installing Python dependencies..."
$VENV_DIR/bin/pip install -r libs/messages/requirements.txt
$VENV_DIR/bin/pip install -r services/video/requirements.txt
$VENV_DIR/bin/pip install -r services/perception/requirements.txt
$VENV_DIR/bin/pip install -r services/voice/requirements.txt
$VENV_DIR/bin/pip install -r services/orchestrator/requirements.txt
$VENV_DIR/bin/pip install -r apps/visor-ui/requirements.txt

# Generate protobuf files
echo "Generating protobuf files..."
cd $INSTALL_DIR/libs/messages
$VENV_DIR/bin/python generate_pb.py

# Install systemd services
echo "Installing systemd services..."
cp $INSTALL_DIR/deploy/systemd/*.service /etc/systemd/system/
cp $INSTALL_DIR/deploy/systemd/*.target /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable services
echo "Enabling services..."
systemctl enable helmet.target
systemctl enable helmet-orchestrator.service
systemctl enable helmet-video.service
systemctl enable helmet-perception.service
systemctl enable helmet-voice.service
systemctl enable helmet-ui.service

# Set up GPU clocks (Jetson specific)
if [[ -f /usr/bin/jetson_clocks ]]; then
    echo "Setting up Jetson performance mode..."
    /usr/bin/jetson_clocks
    echo "@reboot /usr/bin/jetson_clocks" | crontab -u root -
fi

# Create startup script
cat > /usr/local/bin/helmet-start << 'EOF'
#!/bin/bash
# Start Helmet OS
systemctl start helmet.target
EOF

cat > /usr/local/bin/helmet-stop << 'EOF'
#!/bin/bash
# Stop Helmet OS
systemctl stop helmet.target
EOF

cat > /usr/local/bin/helmet-status << 'EOF'
#!/bin/bash
# Check Helmet OS status
systemctl status helmet.target
echo ""
echo "Service Status:"
systemctl list-units --state=active helmet-*
EOF

chmod +x /usr/local/bin/helmet-*

# Set up log rotation
cat > /etc/logrotate.d/helmet << 'EOF'
/var/log/helmet/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 helmet helmet
}
EOF

echo ""
echo "Installation complete!"
echo ""
echo "Commands:"
echo "  helmet-start    - Start the system"
echo "  helmet-stop     - Stop the system"
echo "  helmet-status   - Check system status"
echo ""
echo "Configuration files are in: $INSTALL_DIR/configs/profiles/"
echo "Edit field.json for production settings"
echo ""
echo "To start now: sudo helmet-start"