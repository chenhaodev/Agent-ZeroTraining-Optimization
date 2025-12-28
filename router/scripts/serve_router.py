#!/usr/bin/env python3
"""
Smart Router API Server

Start the production-ready routing API with hot-reload capability.

Usage:
    python scripts/serve_router.py
    python scripts/serve_router.py --port 8080
    python scripts/serve_router.py --host 0.0.0.0 --port 8000
    python scripts/serve_router.py --reload  # Development mode with auto-reload
"""

import sys
import argparse
import uvicorn
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_router_settings


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Smart Router API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server with default settings
  python scripts/serve_router.py

  # Custom port
  python scripts/serve_router.py --port 8080

  # Development mode with auto-reload
  python scripts/serve_router.py --reload

  # Custom host and port
  python scripts/serve_router.py --host 0.0.0.0 --port 8000

  # Production mode with multiple workers
  python scripts/serve_router.py --workers 4
        """
    )

    parser.add_argument(
        '--host',
        type=str,
        default=None,
        help='Host to bind to (default: from settings or 0.0.0.0)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='Port to bind to (default: from settings or 8000)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Number of worker processes (default: 1 for development, 4 for production)'
    )

    parser.add_argument(
        '--reload',
        action='store_true',
        help='Enable auto-reload on code changes (development mode)'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        default=None,
        choices=['debug', 'info', 'warning', 'error'],
        help='Log level (default: from settings or info)'
    )

    return parser.parse_args()


def main():
    """Start the router API server"""
    args = parse_args()
    settings = get_router_settings()

    # Determine configuration
    host = args.host or settings.HOST
    port = args.port or settings.PORT
    workers = args.workers or (1 if args.reload else settings.WORKERS)
    log_level = args.log_level or settings.LOG_LEVEL.lower()

    print("=" * 60)
    print("🚀 Smart Router API Server")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Workers: {workers}")
    print(f"Log Level: {log_level}")
    print(f"Hot-Reload: {'enabled' if settings.ENABLE_HOT_RELOAD else 'disabled'}")
    print(f"Auto-Reload (code): {'enabled' if args.reload else 'disabled'}")
    print()
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"📖 ReDoc: http://{host}:{port}/redoc")
    print("=" * 60)

    # Start server
    uvicorn.run(
        "router.api.app:app",
        host=host,
        port=port,
        workers=workers if not args.reload else 1,  # reload mode requires single worker
        reload=args.reload,
        log_level=log_level,
        access_log=True
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nRouter API server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)
