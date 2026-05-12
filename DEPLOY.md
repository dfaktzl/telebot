# 🚀 Oracle Cloud Deployment Guiv/bin/activate
pip install -r de: Perth Gatekeeper Bot

This guide provides step-by-step instructions for deploying the **Gatekeeper Bot** to an Ubuntu-based Oracle Cloud instance for 24/7 high-security operation.

## 📋 Prerequisites
1. **Server**: Oracle Cloud Compute Instance (Ubuntu 22.04+ recommended).
2. **Tools**: SSH client, Git, Python 3.10+.
3. **Telegram**: A valid `BOT_TOKEN` from @BotFather.

---

## 🛠️ Step 1: Server Preparation
Connect to your server via SSH and run:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv git -y
```

## 📂 Step 2: Clone & Environment Setup
Clone your repository (or upload your files via SCP):
```bash
git clone https://github.com/dfaktzl/telebot.git gatekeeper
cd gatekeeper
```

Create a virtual environment:
```bash
python3 -m venv venv
source venrequirements.txt
```

Create the `.env` file:
```bash
nano .env
```
Paste your token:
```env
BOT_TOKEN=your_token_here
```
*(Press CTRL+O, Enter, and CTRL+X to save)*

## 🗄️ Step 3: Database Migration
If you are moving from a local setup to the cloud, upload your `reputation.db` (50k history) to the project root. The bot will automatically handle the schema migration for `gatekeeper.db` on the first run.

## 🔄 Step 4: Systemd Configuration (24/7 Uptime)
To ensure the bot restarts automatically if the server reboots or the process crashes:

1. Create a service file:
```bash
sudo nano /etc/systemd/system/gatekeeper.service
```

2. Paste the following configuration (replace `ubuntu` and path if different):
```ini
[Unit]
Description=Perth Gatekeeper Telegram Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/gatekeeper
ExecStart=/home/ubuntu/gatekeeper/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Enable and Start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gatekeeper
sudo systemctl start gatekeeper
```

## 📊 Step 5: Monitoring & Management
- **Check Status**: `sudo systemctl status gatekeeper`
- **View Live Logs**: `journalctl -u gatekeeper -f`
- **Restart Bot**: `sudo systemctl restart gatekeeper`

---

## 🎨 Aesthetic Customization
Once the bot is live, use the `/admin` command in Telegram to:
- Edit all welcome, vouch, and access messages.
- Manage illegal word lists for the Content Guardian.
- Update the invite link dynamically.

**Your Gatekeeper is now patrolling the perimeter 24/7.**
