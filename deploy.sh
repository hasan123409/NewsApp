#!/usr/bin/env bash
# ==============================================================================
# 1-Click Deployment Sync to Ubuntu Home Server
# ==============================================================================

set -euo pipefail

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE}  Deploy Morning Dashboard to Ubuntu Server${NC}"
echo -e "${BLUE}=====================================================${NC}"

# Target server IP or hostname (Tailscale / LAN)
TARGET_HOST="${1:-192.168.29.89}"
TARGET_USER="${2:-$USER}"

echo -e "Target Server  : ${YELLOW}${TARGET_HOST}${NC}"
echo -e "Target User    : ${YELLOW}${TARGET_USER}${NC}"
echo -e "Remote Folder  : ${YELLOW}~/NewsApp/${NC}"
echo ""

read -p "Proceed with transfer? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo -e "\n${YELLOW}[1/2] Syncing project files via rsync...${NC}"
rsync -avz --progress \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.git' \
  "${SRC_DIR}/" "${TARGET_USER}@${TARGET_HOST}:~/NewsApp/"

echo -e "\n${GREEN}[✓] Files successfully transferred!${NC}"
echo -e "\n${YELLOW}[2/2] To finish installation on your Ubuntu server, run:${NC}"
echo -e "  ${BLUE}ssh ${TARGET_USER}@${TARGET_HOST}${NC}"
echo -e "  ${BLUE}cd ~/NewsApp && sudo ./setup.sh${NC}"
echo -e "${BLUE}=====================================================${NC}"
