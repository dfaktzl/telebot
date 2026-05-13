# 🚀 Production Deployment Guide: Perth Gatekeeper Bot

This guide is pre-configured for your instance at **159.13.61.203**.

## 🛠️ Step 1: Connect from your Computer
Open **PowerShell** on your Windows PC and run this command:
```powershell
# Replace 'YOUR_KEY_NAME' with the actual name of the key file on your desktop
ssh -i "C:\Users\defak\OneDrive\Desktop\ssh-key-2026-05-13.key" ubuntu@159.13.61.203
```

---

## 📂 Step 2: Server Preparation
Once you are logged into the server (it should say `ubuntu@telebot`), run these:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y
```

---

## 🏗️ Step 3: Project Setup
```bash
# Clone and enter the folder
git clone https://github.com/dfaktzl/telebot.git gatekeeper
cd gatekeeper

# Create environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 🔑 Step 4: Configuration
```bash
nano .env
```
Paste this exactly:
```env
BOT_TOKEN=8502950869:AAGSp_8-dH9SKuZeHBMvRxqtZ8zLcZ5ysgE
```
*(Press **CTRL+O**, **Enter**, then **CTRL+X** to save)*

---

## 🔄 Step 5: Systemd (24/7 Uptime)
1. Create the service:
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

3. Start everything:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gatekeeper
sudo systemctl start gatekeeper
```
