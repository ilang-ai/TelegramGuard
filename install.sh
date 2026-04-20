#!/bin/bash
# TelegramGuard — One-line installer
# curl -sL https://raw.githubusercontent.com/ilang-ai/TelegramGuard/main/install.sh | bash

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${BOLD}TelegramGuard${NC} — AI Group Guardian               ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  Powered by I-Lang Prompt Spec                  ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  https://ilang.ai                               ${CYAN}║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Run as root: sudo bash install.sh${NC}"
  exit 1
fi

# Check Python 3
if ! command -v python3 &> /dev/null; then
  echo -e "${YELLOW}Installing Python 3...${NC}"
  apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv > /dev/null 2>&1
fi

echo -e "${GREEN}[1/5]${NC} Cloning TelegramGuard..."
INSTALL_DIR="/opt/TelegramGuard"
rm -rf "$INSTALL_DIR"
git clone -q https://github.com/ilang-ai/TelegramGuard.git "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo -e "${GREEN}[2/5]${NC} Installing dependencies..."
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

echo -e "${GREEN}[3/5]${NC} Configuration"
echo ""

# Bot Token
echo -e "${BOLD}Telegram Bot Token${NC}"
echo -e "  Get one: open Telegram → find ${CYAN}@BotFather${NC} → send ${CYAN}/newbot${NC}"
echo -e "  Then send these to BotFather:"
echo -e "    ${CYAN}/setjoingroups${NC} → Enable"
echo -e "    ${CYAN}/setprivacy${NC}    → Disable"
echo ""
read -p "  Paste your Bot Token: " BOT_TOKEN
echo ""

# Gemini API Key
echo -e "${BOLD}Gemini API Key${NC} (free)"
echo -e "  Get one: ${CYAN}https://aistudio.google.com/apikey${NC}"
echo ""
read -p "  Paste your API Key: " GEMINI_API_KEY
echo ""

# Write env file
cat > "$INSTALL_DIR/.env" << EOF
BOT_TOKEN=$BOT_TOKEN
GEMINI_API_KEY=$GEMINI_API_KEY
DB_PATH=$INSTALL_DIR/data/bot.db
EOF

mkdir -p "$INSTALL_DIR/data"

echo -e "${GREEN}[4/5]${NC} Creating system service..."

cat > /etc/systemd/system/telegramguard.service << EOF
[Unit]
Description=TelegramGuard - AI Group Guardian
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python3 bot.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable telegramguard

echo -e "${GREEN}[5/5]${NC} Starting TelegramGuard..."
systemctl start telegramguard
sleep 2

if systemctl is-active --quiet telegramguard; then
  echo ""
  echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║${NC}  ${BOLD}TelegramGuard is running!${NC}                       ${GREEN}║${NC}"
  echo -e "${GREEN}╠══════════════════════════════════════════════════╣${NC}"
  echo -e "${GREEN}║${NC}                                                  ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}  Open Telegram and message your bot.             ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}  Add it to any group for auto spam protection.   ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}                                                  ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}  Commands:                                       ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}    systemctl status telegramguard                ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}    systemctl restart telegramguard               ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}    journalctl -u telegramguard -f                ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}                                                  ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}  Customize: edit prompts_demo/*.ilang            ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}  I-Lang Spec: ${CYAN}https://ilang.ai${NC}                   ${GREEN}║${NC}"
  echo -e "${GREEN}║${NC}                                                  ${GREEN}║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
else
  echo -e "${RED}Something went wrong. Check: journalctl -u telegramguard -f${NC}"
fi
