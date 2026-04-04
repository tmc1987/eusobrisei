from __future__ import annotations

from app import create_server


if __name__ == "__main__":
    httpd = create_server()
    print(f"Server scaffold listening on http://{httpd.server_address[0]}:{httpd.server_address[1]}")
    httpd.serve_forever()
