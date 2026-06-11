#!/bin/bash
conda activate py312
cd /mnt/d/code/ezto_video/ezto-agent
uvicorn app.api.server:app --port 8001
