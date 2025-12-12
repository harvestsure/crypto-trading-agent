"""
CryptoAgent Backend - Main Entry Point
Python + ccxt.pro for exchange WebSocket connections and REST API

Requirements:
- pip install -r requirements.txt
"""

import uvicorn
from base_app import create_app

if __name__ == "__main__":
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000)


# ============== Main ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
