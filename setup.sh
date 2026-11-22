#!/usr/bin/env bash
# ==============================================================================
# Setup & Installation Script for Daily Morning Dashboard
# Target OS: Ubuntu 24.04 LTS (x86_64 / arm64)
# ==============================================================================

set -euo pipefail

# Visual formatting
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}  Morning Intelligence Dashboard Setup (Ubuntu 24.04)${NC}"
echo -e "${BLUE}=====================================================${NC}"

# Check sudo / root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[ERROR] Please run this script with sudo: sudo ./setup.sh${NC}"
  exit 1
fi

APP_DIR="/opt/morning-dashboard"
WEB_DIR="/var/www/morning-dashboard"
VENV_DIR="${APP_DIR}/venv"
SCRIPT_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "\n${YELLOW}[1/6] Installing Ubuntu system prerequisites...${NC}"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip cron curl

echo -e "\n${YELLOW}[2/6] Preparing directories...${NC}"
mkdir -p "${APP_DIR}"
mkdir -p "${WEB_DIR}"
mkdir -p /var/log

# Copy application files
echo "Deploying application files to ${APP_DIR}..."
cp "${SCRIPT_SRC_DIR}/fetch_and_build.py" "${APP_DIR}/"
cp "${SCRIPT_SRC_DIR}/template.html" "${APP_DIR}/"
cp "${SCRIPT_SRC_DIR}/serve.py" "${APP_DIR}/"
cp "${SCRIPT_SRC_DIR}/requirements.txt" "${APP_DIR}/"
if [ -f "${SCRIPT_SRC_DIR}/manifest.json" ]; then
  cp "${SCRIPT_SRC_DIR}/manifest.json" "${APP_DIR}/"
  cp "${SCRIPT_SRC_DIR}/manifest.json" "${WEB_DIR}/"
fi
chmod +x "${APP_DIR}/fetch_and_build.py"
chmod +x "${APP_DIR}/serve.py"

echo -e "\n${YELLOW}[3/6] Setting up Python virtual environment (Ubuntu 24.04 PEP 668)...${NC}"
if [ ! -d "${VENV_DIR}" ]; then
  python3 -m venv "${VENV_DIR}"
fi
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"

# Set permissions
chown -R www-data:www-data "${WEB_DIR}"
chmod -R 755 "${WEB_DIR}"

echo -e "\n${YELLOW}[4/6] Setting up systemd service for Port 8089...${NC}"
cp "${SCRIPT_SRC_DIR}/morning-dashboard.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable morning-dashboard.service
systemctl restart morning-dashboard.service

echo -e "\n${YELLOW}[5/6] Configuring Daily 09:00 AM IST Cron Job...${NC}"
# Determine system timezone to set correct 09:00 AM IST cron
CURRENT_TZ=$(timedatectl show --property=Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || echo "UTC")

if [[ "${CURRENT_TZ}" == "Asia/Kolkata" || "${CURRENT_TZ}" == "IST" ]]; then
  # Server is already in IST
  CRON_TIME="0 9 * * *"
  echo "Server timezone is IST (${CURRENT_TZ}). Cron scheduled for 09:00 IST (0 9 * * *)."
else
  # Server is likely UTC. 09:00 AM IST is 03:30 AM UTC.
  # 30 3 * * * runs at 03:30 UTC = 09:00 IST
  CRON_TIME="30 3 * * *"
  echo "Server timezone is ${CURRENT_TZ}. Setting UTC cron to 03:30 UTC (= 09:00 AM IST)."
fi

CRON_JOB="${CRON_TIME} ${VENV_DIR}/bin/python3 ${APP_DIR}/fetch_and_build.py -o ${WEB_DIR}/index.html --city \"Mumbai\" --lat 19.0760 --lon 72.8777 >> /var/log/morning-dashboard.log 2>&1"
CRON_FILE="/etc/cron.d/morning-dashboard"

echo "# Daily Morning Intelligence Dashboard Generator (09:00 AM IST)" > "${CRON_FILE}"
echo "SHELL=/bin/bash" >> "${CRON_FILE}"
echo "PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin" >> "${CRON_FILE}"
echo "${CRON_JOB}" >> "${CRON_FILE}"
chmod 644 "${CRON_FILE}"

echo -e "\n${YELLOW}[6/6] Executing initial live ingestion & build...${NC}"
"${VENV_DIR}/bin/python3" "${APP_DIR}/fetch_and_build.py" -o "${WEB_DIR}/index.html" || true

# Detect network IP addresses
LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "192.168.x.x")
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "not-connected")

echo -e "\n${GREEN}=====================================================${NC}"
echo -e "${GREEN}  DEPLOYMENT SUCCESSFUL!${NC}"
echo -e "${GREEN}=====================================================${NC}"
echo -e "Dashboard is live and accessible at:"
echo -e "  Local       : ${BLUE}http://localhost:8089${NC}"
echo -e "  LAN Network : ${BLUE}http://${LAN_IP}:8089${NC}"
if [ "${TAILSCALE_IP}" != "not-connected" ]; then
echo -e "  Tailscale   : ${BLUE}http://${TAILSCALE_IP}:8089${NC} or http://$(hostname):8089"
fi
echo -e "\nScheduled Execution: Daily at 09:00 AM IST via ${CRON_FILE}"
echo -e "Logs available at   : /var/log/morning-dashboard.log"
echo -e "Service status      : systemctl status morning-dashboard"
