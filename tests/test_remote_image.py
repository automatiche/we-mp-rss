import socket
import unittest
from unittest.mock import patch

from core.remote_image import RemoteImageError, validate_remote_image_url


class RemoteImageUrlValidationTests(unittest.TestCase):
    def test_rejects_non_http_protocols(self):
        for url in ("file:///etc/passwd", "gopher://example.com/", "dict://example.com/"):
            with self.subTest(url=url), self.assertRaises(RemoteImageError):
                validate_remote_image_url(url)

    def test_rejects_localhost_and_non_standard_ports(self):
        for url in (
            "http://localhost/image.png",
            "http://127.0.0.1/image.png",
            "http://[::1]/image.png",
            "http://169.254.169.254/latest/meta-data/",
            "http://example.com:6379/image.png",
        ):
            with self.subTest(url=url), self.assertRaises(RemoteImageError):
                validate_remote_image_url(url)

    @patch("core.remote_image.socket.getaddrinfo")
    def test_rejects_any_private_dns_result(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ]
        with self.assertRaises(RemoteImageError):
            validate_remote_image_url("https://example.com/image.png")

    @patch("core.remote_image.socket.getaddrinfo")
    def test_allows_public_https_destination(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ]
        self.assertEqual(
            validate_remote_image_url("https://example.com/image.png"),
            "https://example.com/image.png",
        )


if __name__ == "__main__":
    unittest.main()
