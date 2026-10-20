#!/usr/bin/env python
import argparse
import http.server
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Toolathlon's own default, from configs/token_key_session_example.py:36.
DEFAULT_PROJECT = "mcp-bench0606"


class TokenStub(http.server.BaseHTTPRequestHandler):
    """Answers the one route google-auth needs."""

    def do_POST(self) -> None:
        """Hand back a bearer token, whatever the assertion says.

        The signature is not checked. This exists so that minting succeeds
        offline, not to authenticate anything -- the emulator behind it does
        not read the token at all.
        """
        body = json.dumps({
            "access_token": "fake-access-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        """Stay quiet; the harness prints its own progress."""


def write_key(path: Path,
              project: str,
              port: int,
              advertise: str | None = None) -> None:
    """Generate a service-account key that points back at this server.

    Args:
        path (Path): where to write the JSON.
        project (str): the GCP project id the key claims.
        port (int): the port this stub will listen on.
        advertise (str | None): base URL to write into the key, for a
            client that resolves this stub by a name other than loopback --
            a sibling container, say. Defaults to loopback on `port`, which
            is right for every caller on this host.
    """
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()).decode()
    base = (advertise or f"http://127.0.0.1:{port}").rstrip("/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": project,
                "private_key_id": "vfs-bench",
                "private_key": pem,
                "client_email": f"agent@{project}.iam.gserviceaccount.com",
                "client_id": "000000000000000000000",
                "auth_uri": f"{base}/auth",
                "token_uri": f"{base}/token",
                "auth_provider_x509_cert_url": f"{base}/certs",
                "client_x509_cert_url": f"{base}/cert",
                "universe_domain": "googleapis.com",
            },
            indent=2) + "\n")


def main() -> int:
    """Entry point.

    Returns:
        int: process exit status.
    """
    parser = argparse.ArgumentParser(
        description='Mint OAuth tokens locally, so a '
        'service-account key can reach a fake.')
    parser.add_argument("--port", type=int, default=9061)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--write-key",
                        type=Path,
                        help="write a service-account key here first")
    parser.add_argument("--bind",
                        default="127.0.0.1",
                        help="0.0.0.0 in a container, where binding the "
                        "loopback would publish a port nothing answers on")
    parser.add_argument("--advertise",
                        help="the base URL the written key points at, when "
                        "the client resolves this stub by some name other "
                        "than loopback (default http://127.0.0.1:<port>)")
    args = parser.parse_args()

    if args.write_key:
        write_key(args.write_key, args.project, args.port, args.advertise)
        print(f"key: {args.write_key}")

    server = http.server.HTTPServer((args.bind, args.port), TokenStub)
    print(f"GCP_TOKEN_STUB=http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
