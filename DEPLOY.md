# Oracle Cloud Deployment Guide

This guide provides clean instructions for your Oracle Cloud server.

## Step 1: Server Preparation
Run these commands based on your OS.

### For Oracle Linux (Default)
```bash
sudo dnf update -y
sudo dnf install python3 python3-pip git -y
```

### For Ubuntu
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y
```

---

## Step 2: Project Setup
```bash
git clone https://github.com/dfaktzl/telebot.git gatekeeper
cd gatekeeper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Step 3: Configuration
```bash
nano .env
```
Paste this inside:
```env
BOT_TOKEN=your_token_here
```
(Press CTRL+O, Enter, and CTRL+X to save)

---

## Step 4: Systemd (24/7 Uptime)
1. Create the service:
```bash
sudo nano /etc/systemd/system/gatekeeper.service
```

2. Paste this (use 'opc' for Oracle Linux, 'ubuntu' for Ubuntu):
```ini
[Unit]
Description=Gatekeeper Bot
After=network.target

[Service]
User=opc
WorkingDirectory=/home/opc/gatekeeper
ExecStart=/home/opc/gatekeeper/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

3. Start the bot:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gatekeeper
sudo systemctl start gatekeeper
```
