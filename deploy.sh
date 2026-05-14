#!/bin/bash
# deploy.sh — First-time setup for Gatekeeper Bot on a fresh OCI Ubuntu 22.04 instance
# Bot token prefix: 8502950869 (Gatekeeper — separate from Vouch/Rep bot 8581140481)
# Run as: sudo bash deploy.sh
# After running: sudo systemctl start gatekeeper

set -e

REPO_URL="https://github.com/dfaktzl/telebot.git"
BOT_DIR="/home/ubuntu/gatekeeper"
SERVICE_NAME="gatekeeper"

echo "═══════════════════════════════════════════════"
echo "  Perth Gatekeeper Bot — OCI Deploy Script"
echo "  Token prefix: 8502950869"
echo "  Server: $(hostname -I | awk '{print $1}')"
echo "═══════════════════════════════════════════════"

# ── Swap (prevents OOM on 1GB instances) ─────────────────────────────────────
if [ ! -f /swapfile_gatekeeper ]; then
    echo "📦 Adding 1GB swap..."
    dd if=/dev/zero of=/swapfile_gatekeeper bs=1M count=1024
    chmod 600 /swapfile_gatekeeper
    mkswap /swapfile_gatekeeper
    swapon /swapfile_gatekeeper
    echo "/swapfile_gatekeeper swap swap defaults 0 0" >> /etc/fstab
else
    echo "✅ Swap already exists."
fi

# ── System packages ───────────────────────────────────────────────────────────
echo "📦 Updating system packages..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git sqlite3

# ── Clone / update repo ───────────────────────────────────────────────────────
if [ -d "$BOT_DIR/.git" ]; then
    echo "🔄 Repo already exists — pulling latest..."
    git -C "$BOT_DIR" pull
else
    echo "📥 Cloning repo..."
    git clone "$REPO_URL" "$BOT_DIR"
fi

# ── Python venv + deps ────────────────────────────────────────────────────────
echo "🐍 Installing Python dependencies..."
cd "$BOT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ── .env file ─────────────────────────────────────────────────────────────────
if [ ! -f "$BOT_DIR/.env" ]; then
    echo ""
    echo "⚙️  Creating .env from template..."
    cp "$BOT_DIR/.env.example" "$BOT_DIR/.env"
    chmod 600 "$BOT_DIR/.env"
    echo ""
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  .env is pre-filled with the Gatekeeper token.     │"
    echo "  │  No edits needed unless you change the bot token.  │"
    echo "  └─────────────────────────────────────────────────────┘"
else
    echo "✅ .env already exists — skipping."
fi

# ── Systemd service ───────────────────────────────────────────────────────────
echo "⚙️  Installing systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Perth Gatekeeper Bot (8502950869)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${BOT_DIR}
ExecStart=${BOT_DIR}/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}
EnvironmentFile=${BOT_DIR}/.env
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=${BOT_DIR}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo ""
echo "  NEXT STEPS:"
echo "  1. Start the bot:   sudo systemctl start $SERVICE_NAME"
echo "  2. Watch logs:      sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "  FUTURE UPDATES:"
echo "  cd $BOT_DIR && git pull && sudo systemctl restart $SERVICE_NAME"
echo "═══════════════════════════════════════════════"
