#!/bin/bash

# launch backend server
conda activate ezto
cd ezto-agent/src
uvicorn backend.api.server:app --port 8001

# launch frontend server
cd ezto-agent/src/frontend
npm run dev