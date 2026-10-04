"""
ipv4_guard.py — Transparent local IPv4 loopback proxy for Google Cloud / Antigravity APIs.

WHY THIS EXISTS:
Many ISPs (especially in Asia/Middle East, e.g. Pakistan) have broken IPv6 routes,
PMTU black holes, or packet drops to Google Cloud IP blocks (2001:4860:...).
Windows default prefix policy gives IPv6 higher priority (precedence 40) than IPv4 (35),
causing agy (compiled Go binary) to connect over IPv6 first.
This results in intermittent or constant TLS handshake resets:
  "error: Eligibility check failed: Post 'https://daily-cloudcode-pa.googleapis.com/v1internal:loadCodeAssist': EOF"
which causes agy to exit with status 1.

Connecting over IPv4 has a 100% success rate.
This module runs a tiny in-memory loopback proxy on 127.0.0.1 (no admin rights needed)
that tunnels HTTP/HTTPS CONNECT requests strictly using socket.AF_INET (IPv4).
Setting HTTP_PROXY and HTTPS_PROXY ensures agy and python requests connect over IPv4.
"""

import os
import sys
import socket
import select
import threading

_RUNNING_PROXY = None
_LOCK = threading.Lock()

class _LocalIPv4Proxy:
    def __init__(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", 0))
        self.server_sock.listen(100)
        self.port = self.server_sock.getsockname()[1]
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True, name="IPv4ProxyThread")
        self.thread.start()

    def _listen_loop(self):
        while self.running:
            try:
                client_sock, _ = self.server_sock.accept()
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except Exception:
                break

    def _handle_client(self, client_sock):
        try:
            req = b""
            while b"\r\n\r\n" not in req:
                chunk = client_sock.recv(4096)
                if not chunk:
                    client_sock.close()
                    return
                req += chunk

            lines = req.split(b"\r\n")
            first_line = lines[0].decode("latin1", errors="replace")
            parts = first_line.split(" ")
            if len(parts) >= 2 and parts[0].upper() == "CONNECT":
                host_port = parts[1]
                host, port_str = host_port.split(":", 1) if ":" in host_port else (host_port, "443")
                port = int(port_str)
                # Resolve strictly to IPv4 address
                addrs = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
                remote_ip = addrs[0][4][0]
                remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                remote_sock.settimeout(15)
                remote_sock.connect((remote_ip, port))
                remote_sock.settimeout(None)
                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self._tunnel(client_sock, remote_sock)
            else:
                # HTTP plain forwarding
                host = None
                for line in lines[1:]:
                    if line.lower().startswith(b"host:"):
                        host_header = line.split(b":", 1)[1].strip().decode("latin1")
                        host = host_header.split(":")[0]
                        port = int(host_header.split(":")[1]) if ":" in host_header else 80
                        break
                if host:
                    addrs = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
                    remote_ip = addrs[0][4][0]
                    remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    remote_sock.settimeout(15)
                    remote_sock.connect((remote_ip, port))
                    remote_sock.settimeout(None)
                    remote_sock.sendall(req)
                    self._tunnel(client_sock, remote_sock)
                else:
                    client_sock.close()
        except Exception:
            try:
                client_sock.close()
            except Exception:
                pass

    def _tunnel(self, s1, s2):
        s1.setblocking(False)
        s2.setblocking(False)
        try:
            while True:
                r, _, _ = select.select([s1, s2], [], [], 30.0)
                if not r:
                    break
                if s1 in r:
                    data = s1.recv(16384)
                    if not data:
                        break
                    s2.sendall(data)
                if s2 in r:
                    data = s2.recv(16384)
                    if not data:
                        break
                    s1.sendall(data)
        except Exception:
            pass
        finally:
            try:
                s1.close()
            except Exception:
                pass
            try:
                s2.close()
            except Exception:
                pass

    def stop(self):
        self.running = False
        try:
            self.server_sock.close()
        except Exception:
            pass


def start_ipv4_guard(force: bool = False) -> int:
    """
    Starts an in-process IPv4-forcing loopback proxy and configures
    HTTP_PROXY / HTTPS_PROXY in os.environ for agy and python processes.
    Returns the port number.
    """
    global _RUNNING_PROXY
    with _LOCK:
        if _RUNNING_PROXY and _RUNNING_PROXY.running:
            return _RUNNING_PROXY.port

        # Don't override if user already specified an external HTTP proxy
        existing = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        if existing and not force and "127.0.0.1" not in existing:
            return 0

        proxy = _LocalIPv4Proxy()
        _RUNNING_PROXY = proxy
        proxy_url = f"http://127.0.0.1:{proxy.port}"

        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url
        os.environ["http_proxy"] = proxy_url
        os.environ["https_proxy"] = proxy_url
        # Force Go's resolver to use internal netgo if needed
        os.environ["GODEBUG"] = os.environ.get("GODEBUG", "") + ",netdns=go"

        return proxy.port


def stop_ipv4_guard():
    global _RUNNING_PROXY
    with _LOCK:
        if _RUNNING_PROXY:
            _RUNNING_PROXY.stop()
            _RUNNING_PROXY = None
            for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
                val = os.environ.get(key, "")
                if "127.0.0.1" in val:
                    os.environ.pop(key, None)
