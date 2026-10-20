import datetime
import http.client
import http.server
import ssl
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

# slack-mcp-server asks slack.com for `auth.test` before anything else and
# sends every later call to the `url` that reply names (`pkg/provider/api.go`
# at v1.1.23), and it takes no base URL. What it does take is a proxy and a CA
# of its own, `SLACK_MCP_PROXY` and `SLACK_MCP_SERVER_CA`, and this is both:
# every request it sends, the tunnelled one to slack.com included, is answered
# by the fake, whose `auth.test` names the fake itself.
#
# @geobio/google-workspace-server is the same case with fixed origins: its
# googleapis client sends the refresh-token exchange to oauth2.googleapis.com
# and every Calendar call to www.googleapis.com, and takes no base URL, but
# gaxios tunnels through `HTTPS_PROXY` and Node trusts `NODE_EXTRA_CA_CERTS`,
# so the same listener, holding a certificate for both names, answers it too.
HOST = "slack.com"


def certificate(folder: Path, hosts: tuple) -> tuple[Path, Path]:
    """A throwaway certificate for `hosts`, trusted only by its own file.

    Args:
        folder (Path): where to write it.
        hosts (tuple): the names it is for.

    Returns:
        tuple[Path, Path]: the certificate, which is also the CA the server
        is given, and its key.
    """
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hosts[0])])
    now = datetime.datetime.now(datetime.UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(
        name).public_key(key.public_key()).serial_number(
            x509.random_serial_number()).not_valid_before(
                now - datetime.timedelta(hours=1)).not_valid_after(
                    now + datetime.timedelta(days=30)).add_extension(
                        x509.SubjectAlternativeName(
                            [x509.DNSName(host) for host in hosts]),
                        critical=False).add_extension(
                            x509.BasicConstraints(ca=True, path_length=None),
                            critical=True).sign(key, hashes.SHA256()))
    pem, private = folder / f"{hosts[0]}.pem", folder / f"{hosts[0]}.key"
    pem.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(
        key.private_bytes(serialization.Encoding.PEM,
                          serialization.PrivateFormat.PKCS8,
                          serialization.NoEncryption()))
    return pem, private


class Forward(http.server.BaseHTTPRequestHandler):
    """One client connection: a CONNECT is answered in TLS, and every
    request, tunnelled or not, is sent on to the fake."""

    protocol_version = "HTTP/1.1"

    def do_CONNECT(self):
        """Take the tunnel as the host and keep reading requests from it."""
        self.send_response(200)
        self.end_headers()
        self.connection = self.server.tls.wrap_socket(self.connection,
                                                      server_side=True)
        self.rfile = self.connection.makefile("rb")
        self.wfile = self.connection.makefile("wb")
        self.close_connection = False

    def body(self) -> bytes | None:
        """The request's body, whole.

        The edge client's `client.userBoot` streams its form, so it comes
        chunked; every other call states its length.

        Returns:
            bytes | None: the body, None where there is none.
        """
        if self.headers.get("Transfer-Encoding", "").lower() != "chunked":
            length = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(length) if length else None
        chunks = []
        while size := int(self.rfile.readline().split(b";")[0], 16):
            chunks.append(self.rfile.read(size))
            self.rfile.readline()
        while self.rfile.readline() not in (b"\r\n", b"\n", b""):
            pass
        return b"".join(chunks)

    def forward(self):
        """Send the request to the fake under its path, and its reply back."""
        body = self.body()
        parts = urlsplit(self.path)
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in ("host", "connection", "proxy-connection",
                                   "transfer-encoding")
        }
        connection = http.client.HTTPConnection(self.server.target.hostname,
                                                self.server.target.port,
                                                timeout=60)
        try:
            connection.request(self.command, path, body, headers)
            reply = connection.getresponse()
            data = reply.read()
        finally:
            connection.close()
        self.send_response_only(reply.status, reply.reason)
        for key, value in reply.getheaders():
            if key.lower() not in ("connection", "content-length",
                                   "transfer-encoding"):
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = forward

    def log_message(self, format, *args):
        """Say nothing: a line per request would land in the run's output."""


class Host(http.server.ThreadingHTTPServer):
    """The listener, one thread per connection."""

    daemon_threads = True

    def handle_error(self, request, client_address):
        """Report a failure, but not a client hanging up between requests."""
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)


@contextmanager
def serve(target: str, *hosts: str):
    """Answer a server's requests to `hosts` with the fake at `target`.

    Args:
        target (str): the fake's origin.
        *hosts (str): the names the server sends to, slack.com by default.

    Yields:
        dict: `proxy`, this listener's URL, and `ca`, the certificate the
        server has to trust.
    """
    with tempfile.TemporaryDirectory(prefix="slack-host-") as folder:
        pem, key = certificate(Path(folder), hosts or (HOST, ))
        server = Host(("127.0.0.1", 0), Forward)
        server.target = urlsplit(target)
        server.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server.tls.load_cert_chain(pem, key)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield {
                "proxy": f"http://127.0.0.1:{server.server_port}",
                "ca": str(pem),
            }
        finally:
            server.shutdown()
            server.server_close()
