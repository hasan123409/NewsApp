#!/usr/bin/env python3
"""
Lightweight Static HTTP Server on port 8089.
Zero-dependency, production-ready static server for the Morning Dashboard.
"""

import os
import sys
import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8089
DEFAULT_WEB_DIR = "/var/www/morning-dashboard"

class CustomHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=self.server_dir, **kwargs)

    def end_headers(self):
        # Disable aggressive caching so new morning editions appear instantly
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        # Clean logging
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.address_string()} - {format % args}\n")

def run(port=PORT, directory=DEFAULT_WEB_DIR):
    if not os.path.exists(directory):
        print(f"Directory {directory} does not exist. Using current directory as fallback.")
        directory = os.path.dirname(os.path.abspath(__file__))

    CustomHandler.server_dir = directory
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, CustomHandler)

    print(f"=====================================================")
    print(f"  Morning Dashboard Server running on port {port}")
    print(f"  Serving Directory : {directory}")
    print(f"  Local Access      : http://localhost:{port}")
    print(f"  LAN Access        : http://<LAN_IP>:{port}")
    print(f"  Tailscale Access  : http://<TAILSCALE_IP>:{port}")
    print(f"=====================================================")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        httpd.server_close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Static server for Morning Dashboard")
    parser.add_argument("-p", "--port", type=int, default=PORT, help=f"Port to bind (default: {PORT})")
    parser.add_argument("-d", "--dir", default=DEFAULT_WEB_DIR, help=f"Directory to serve (default: {DEFAULT_WEB_DIR})")
    args = parser.parse_args()

    run(port=args.port, directory=args.dir)
