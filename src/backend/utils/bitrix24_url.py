"""Utility functions for parsing Bitrix24 webhook URLs."""
from urllib.parse import urlparse


def parse_bitrix24_webhook_url(webhook_url: str) -> tuple[str, str]:
    """Parse Bitrix24 webhook URL and extract portal URL and token.

    Args:
        webhook_url: Full webhook URL (e.g., https://domain.bitrix24.ru/rest/1/token/)

    Returns:
        Tuple of (portal_url, webhook_token)

    Raises:
        ValueError: If URL format is invalid
    """
    webhook_url = webhook_url.strip().rstrip("/")

    # Parse URL
    parsed = urlparse(webhook_url)

    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid webhook URL format")

    # Extract portal URL
    portal_url = f"{parsed.scheme}://{parsed.netloc}"

    # Extract token from path (format: /rest/1/token or /rest/1/token/)
    path_parts = parsed.path.strip("/").split("/")

    if len(path_parts) < 3 or path_parts[0] != "rest":
        raise ValueError("Invalid webhook URL format. Expected: https://domain.bitrix24.ru/rest/1/token")

    # Token is the last part after /rest/1/
    webhook_token = path_parts[-1]

    if not webhook_token:
        raise ValueError("Webhook token not found in URL")

    return portal_url, webhook_token


def extract_domain_from_webhook_url(webhook_url: str) -> str:
    """Extract domain from Bitrix24 webhook URL.

    Args:
        webhook_url: Full webhook URL (e.g., https://domain.bitrix24.ru/rest/1/token/)

    Returns:
        Domain string (e.g., domain.bitrix24.ru)

    Raises:
        ValueError: If URL format is invalid
    """
    webhook_url = webhook_url.strip().rstrip("/")

    # Parse URL
    parsed = urlparse(webhook_url)

    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid webhook URL format")

    # Extract domain from netloc (hostname)
    return parsed.netloc

