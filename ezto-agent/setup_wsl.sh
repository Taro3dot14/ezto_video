#!/bin/bash
set -e

echo "=== Setting up ezto-agent in WSL ==="
cd /mnt/d/code/ezto_video/ezto-agent

# Install pip + venv if missing
sudo apt update -qq
sudo apt install -y python3-pip python3-venv

# Create & activate venv
python3 -m venv .venv
source .venv/bin/activate

# Install project + dev deps
pip install --upgrade pip
pip install -e .

echo ""
echo "=== Done! Run the server: ==="
echo "  cd /mnt/d/code/ezto_video/ezto-agent"
echo "  source .venv/bin/activate"
echo "  uvicorn app.api.server:app --reload --port 8001"
