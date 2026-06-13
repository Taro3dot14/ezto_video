"""CLI entry point for the ezto-agent server."""

import uvicorn
from backend.api.server import app

if __name__ == "__main__":
    uvicorn.run("backend.api.server:app", host="127.0.0.1", port=8001, reload=True)
