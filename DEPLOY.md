# 🚀 Ubuntu 22.04 Deployment Guide: Perth Gatekeeper Bot

This guide is specifically for an **Ubuntu 22.04** instance on Oracle Cloud.

## 🛠️ Step 1: Server Preparation
Log in to your server: `ssh -i your_key.key ubuntu@YOUR_IP`

Run these commands to prepare the server:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y
```

---

## 📂 Step 2: Project Setup
```bash
# Clone the repository
git clone https://github.com/dfaktzl/telebot.git gatekeeper
cd gatekeeper

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

---

## 🔑 Step 3: Configuration
```bash
nano .env
```
Paste this inside:
```env
BOT_TOKEN=8502950869:AAGSp_8-dH9SKuZeHBMvRxqtZ8zLcZ5ysgE
```
*(Press **CTRL+O**, **Enter**, then **CTRL+X** to save)*

---

## 🔄 Step 4: Systemd (24/7 Uptime)
1. Create the service file:
```bash
sudo nano /etc/systemd/system/gatekeeper.service
```

2. Paste this configuration:
```ini
[Unit]
Description=Perth Gatekeeper Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/gatekeeper
ExecStart=/home/ubuntu/gatekeeper/venv/bin/python main.py
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

---

## 📊 Step 5: Check Status
```bash
sudo systemctl status gatekeeper
journalctl -u gatekeeper -f
```
