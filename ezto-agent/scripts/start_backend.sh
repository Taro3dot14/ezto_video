#!/bin/bash

# launch backend server
conda activate ezto
cd "$(dirname "$0")/../src"
uvicorn backend.api.server:app --port 8001

# launch frontend server
cd frontend
npm run dev