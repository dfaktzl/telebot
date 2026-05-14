# 🚀 Quick Deploy Reference — Perth Gatekeeper Bot

> **Full instructions** are in [README.md](./README.md).
> This file is a command cheat-sheet for experienced users.

**Bot token prefix:** `8502950869` (Gatekeeper)
**Repo:** `https://github.com/dfaktzl/telebot.git`
**Deploy path:** `/home/ubuntu/gatekeeper`
**Service name:** `gatekeeper`

---

## SSH In (from Windows PowerShell)

```powershell
# Fix key permissions first (only needed once)
icacls "C:\Users\defak\Downloads\botcurrentpriv.key" /inheritance:r /grant:r "$($env:USERNAME):(R)"

# Connect
ssh -i "C:\Users\defak\Downloads\botcurrentpriv.key" ubuntu@<YOUR_OCI_PUBLIC_IP>
```

---

## First-Time Deploy (run on server as ubuntu)

```bash
curl -sO https://raw.githubusercontent.com/dfaktzl/telebot/master/deploy.sh
sudo bash deploy.sh
sudo systemctl start gatekeeper
sudo journalctl -u gatekeeper -f
```

---

## Update (2 commands)

```bash
cd /home/ubuntu/gatekeeper && git pull
sudo systemctl restart gatekeeper
```

---

## Service Commands

```bash
sudo systemctl status gatekeeper    # Check status
sudo systemctl stop gatekeeper      # Stop
sudo systemctl restart gatekeeper   # Restart
sudo journalctl -u gatekeeper -f    # Live logs
sudo journalctl -u gatekeeper -n 50 # Last 50 log lines
```

---

## Both Bots Running?

```bash
sudo systemctl status gatekeeper   # token 8502950869
sudo systemctl status repbot       # token 8581140481
```