"""Sandbox ownership and byte transport, independent of tasks and surfaces."""
import socket
import socketserver
import threading
from contextlib import contextmanager

from e2b import Sandbox
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect


class Tunnel:
    """Expose a WebSocket byte stream on one loopback TCP port."""

    def __init__(self, url: str, port: int = 0):
        self.connections = set()
        self.lock = threading.Lock()
        owner = self

        class Handler(socketserver.BaseRequestHandler):

            def handle(self):
                # This is the harness's E2B transport, not model-directed
                # traffic. Agent tools temporarily install a dead process-wide
                # proxy to enforce their airgap; a parallel request must not
                # make this bridge inherit that proxy and drop a live service.
                with connect(url, max_size=None, close_timeout=2,
                             proxy=None) as ws:
                    with owner.lock:
                        owner.connections.add((self.request, ws))

                    def send():
                        try:
                            while data := self.request.recv(65536):
                                ws.send(data)
                        except (OSError, ConnectionClosed):
                            pass
                        finally:
                            ws.close()

                    sender = threading.Thread(target=send, daemon=True)
                    sender.start()
                    try:
                        for data in ws:
                            self.request.sendall(data)
                    except (OSError, ConnectionClosed):
                        pass
                    finally:
                        with owner.lock:
                            owner.connections.discard((self.request, ws))
                        try:
                            self.request.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                        sender.join(timeout=3)

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = True

        self.server = Server(('127.0.0.1', port), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        with self.lock:
            connections = list(self.connections)
        for sock, ws in connections:
            ws.close()
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.server.server_close()
        self.thread.join(timeout=3)


@contextmanager
def sandbox(template: str, metadata: dict):
    """Every arm owns a new sandbox, including cleanup on setup failure."""
    from task.toolathlon import TIMEOUT

    # Setup (up to 15 minutes) precedes the agent's wall clock, upstream's
    # task budget, and grading can take another 10 minutes. Keep the
    # fixture for all phases: E2B kills a sandbox at its timeout.
    box = Sandbox.create(template=template,
                         timeout=15 * 60 + TIMEOUT + 10 * 60,
                         metadata=metadata)
    try:
        yield box
    finally:
        box.kill()
