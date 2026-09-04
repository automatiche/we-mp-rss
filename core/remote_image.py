"""Safe downloader primitives for the remote image proxy."""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 3
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}


class RemoteImageError(ValueError):
    """A remote image URL or response failed the proxy safety policy."""


def validate_remote_image_url(url: str) -> str:
    """Validate scheme, port, credentials and every resolved destination IP."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise RemoteImageError("远程图片地址不可用") from exc

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RemoteImageError("远程图片地址不可用")
    if parsed.username is not None or parsed.password is not None:
        raise RemoteImageError("远程图片地址不可用")

    expected_port = 80 if parsed.scheme == "http" else 443
    if port is not None and port != expected_port:
        raise RemoteImageError("远程图片地址不可用")

    hostname = parsed.hostname.rstrip(".")
    if hostname.lower() == "localhost" or hostname.lower().endswith(".localhost"):
        raise RemoteImageError("远程图片地址不可用")

    try:
        addresses = socket.getaddrinfo(
            hostname,
            port or expected_port,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise RemoteImageError("远程图片地址不可用") from exc

    if not addresses:
        raise RemoteImageError("远程图片地址不可用")

    for address in addresses:
        try:
            resolved_ip = ipaddress.ip_address(address[4][0].split("%", 1)[0])
        except ValueError as exc:
            raise RemoteImageError("远程图片地址不可用") from exc
        if not resolved_ip.is_global:
            raise RemoteImageError("远程图片地址不可用")

    return url


async def fetch_remote_image(url: str) -> tuple[bytes, str]:
    """Download one public image, validating the destination after each redirect."""
    current_url = url
    timeout = httpx.Timeout(30.0, connect=10.0)

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        for redirect_count in range(MAX_REDIRECTS + 1):
            await asyncio.to_thread(validate_remote_image_url, current_url)

            try:
                async with client.stream("GET", current_url) as response:
                    if response.status_code in REDIRECT_STATUS_CODES:
                        location = response.headers.get("location")
                        if not location or redirect_count == MAX_REDIRECTS:
                            raise RemoteImageError("无法获取远程图片")
                        current_url = urljoin(current_url, location)
                        continue

                    if response.status_code != 200:
                        raise RemoteImageError("无法获取远程图片")

                    content_type = response.headers.get("content-type", "")
                    if not content_type.lower().startswith("image/"):
                        raise RemoteImageError("远程资源不是图片")

                    content_length = response.headers.get("content-length")
                    if content_length:
                        try:
                            if int(content_length) > MAX_IMAGE_BYTES:
                                raise RemoteImageError("远程图片过大")
                        except ValueError:
                            raise RemoteImageError("无法获取远程图片")

                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > MAX_IMAGE_BYTES:
                            raise RemoteImageError("远程图片过大")
                    return bytes(chunks), current_url
            except httpx.HTTPError as exc:
                raise RemoteImageError("无法获取远程图片") from exc

    raise RemoteImageError("无法获取远程图片")
