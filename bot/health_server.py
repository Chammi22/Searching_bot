"""Simple HTTP server for health checks."""

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Handler for health check requests."""

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/health" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        """Override to use our logger."""
        logger.debug(f"Health check: {format % args}")


def run_health_server(port: int = 8080) -> HTTPServer:
    """Run health check server in a separate thread."""
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    
    def run_server() -> None:
        logger.info(f"Health check server started on port {port}")
        server.serve_forever()
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    
    return server


# Global server instance
_health_server: Optional[HTTPServer] = None


def start_health_server(port: int = 8080) -> None:
    """Start health check server."""
    global _health_server
    if _health_server is None:
        _health_server = run_health_server(port)


def stop_health_server() -> None:
    """Stop health check server."""
    global _health_server
    if _health_server is not None:
        _health_server.shutdown()
        _health_server = None
