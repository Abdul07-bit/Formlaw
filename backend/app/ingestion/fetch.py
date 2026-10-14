"""
SSRF-safe downloads for ingestion. A URL is fetched only if it is https, on the exact host registered
for an APPROVED source, resolves to public IP addresses, and does not redirect. Sizes are capped.
"""
from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlparse

import httpx

USER_AGENT = "FormLawIngest/1.0 (legal research platform; sequential, low-concurrency)"


class FetchRefused(Exception):
    pass


def check_url(url: str, allowed_base: str) -> None:
    u, base = urlparse(url), urlparse(allowed_base)
    if u.scheme != "https" or not u.hostname:
        raise FetchRefused("Only https URLs are allowed")
    if u.username or u.password or (u.port not in (None, 443)):
        raise FetchRefused("Credentials and non-standard ports are not allowed")
    if u.hostname.lower() != (base.hostname or "").lower():
        raise FetchRefused(f"{u.hostname} is not the registered host for this source")
    try:
        infos = socket.getaddrinfo(u.hostname, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise FetchRefused(f"Cannot resolve {u.hostname}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise FetchRefused("Refusing to connect to a non-public address")


class _StreamFile:
    """Minimal file-like wrapper so tarfile can stream ('r|') an HTTP body without buffering it all."""

    def __init__(self, it: Iterator[bytes], cap: int):
        self._it, self._buf, self._cap, self.read_bytes = it, b"", cap, 0

    def read(self, n: int = -1) -> bytes:
        while n < 0 or len(self._buf) < n:
            try:
                chunk = next(self._it)
            except StopIteration:
                break
            self.read_bytes += len(chunk)
            if self.read_bytes > self._cap:
                raise FetchRefused("Download exceeds the configured size cap")
            self._buf += chunk
        if n < 0:
            data, self._buf = self._buf, b""
        else:
            data, self._buf = self._buf[:n], self._buf[n:]
        return data


@contextmanager
def open_stream(url: str, allowed_base: str, *, cap: int):
    check_url(url, allowed_base)
    with httpx.Client(timeout=httpx.Timeout(60, read=120), follow_redirects=False, headers={"user-agent": USER_AGENT}) as c:
        with c.stream("GET", url) as r:
            if r.status_code in (301, 302, 303, 307, 308):
                raise FetchRefused("Redirects are not followed during ingestion")
            r.raise_for_status()
            yield _StreamFile(r.iter_bytes(65536), cap)


def get_json(url: str, allowed_base: str, *, cap: int = 20 * 1024 * 1024):
    import json

    with open_stream(url, allowed_base, cap=cap) as f:
        return json.loads(f.read())
