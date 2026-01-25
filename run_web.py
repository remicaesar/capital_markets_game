#!/usr/bin/env python3
"""
Entry point for the Capital Markets Game Web UI

Usage:
    python run_web.py
    
Then open http://localhost:8000 in your browser
"""

import uvicorn


def main():
    """Start the web server"""
    print("=" * 60)
    print("  CAPITAL MARKETS GAME - Web UI")
    print("=" * 60)
    print()
    print("  Starting server...")
    print("  Open http://localhost:8000 in your browser")
    print()
    print("  Press Ctrl+C to stop the server")
    print("=" * 60)
    print()
    
    uvicorn.run(
        "web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes during development
        log_level="info"
    )


if __name__ == "__main__":
    main()
