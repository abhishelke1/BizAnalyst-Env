"""OpenEnv Server Entry Point - required for multi-mode deployment."""

import uvicorn
from scout_server import app

def main():
    """Run the SCOUT AI server."""
    uvicorn.run(app, host="0.0.0.0", port=7860)

if __name__ == "__main__":
    main()
