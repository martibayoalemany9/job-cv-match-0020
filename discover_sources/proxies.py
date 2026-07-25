"""Proxy helpers for Bright Data and Oxylabs (when boards block residential IPs)."""
from __future__ import annotations

from discover_sources.common import env, log


def bright_data_proxy_url() -> str | None:
    """
    Build Bright Data residential/datacenter proxy URL.

    Env:
      BRIGHTDATA_CUSTOMER, BRIGHTDATA_ZONE, BRIGHTDATA_PASSWORD
      or BRIGHTDATA_PROXY_URL (full URL override)
    """
    full = env("BRIGHTDATA_PROXY_URL")
    if full:
        return full
    customer = env("BRIGHTDATA_CUSTOMER")
    zone = env("BRIGHTDATA_ZONE")
    password = env("BRIGHTDATA_PASSWORD")
    host = env("BRIGHTDATA_HOST", "brd.superproxy.io")
    port = env("BRIGHTDATA_PORT", "22225")
    if not (customer and zone and password):
        return None
    # username format: brd-customer-<id>-zone-<zone>
    user = f"brd-customer-{customer}-zone-{zone}"
    return f"http://{user}:{password}@{host}:{port}"


def oxylabs_proxy_url() -> str | None:
    """
    Build Oxylabs residential proxy URL.

    Env:
      OXYLABS_USERNAME, OXYLABS_PASSWORD
      OXYLABS_HOST (default pr.oxylabs.io), OXYLABS_PORT (default 7777)
      or OXYLABS_PROXY_URL
    """
    full = env("OXYLABS_PROXY_URL")
    if full:
        return full
    user = env("OXYLABS_USERNAME")
    password = env("OXYLABS_PASSWORD")
    host = env("OXYLABS_HOST", "pr.oxylabs.io")
    port = env("OXYLABS_PORT", "7777")
    if not (user and password):
        return None
    return f"http://{user}:{password}@{host}:{port}"


def active_proxy_url() -> str | None:
    """Prefer explicit DISCOVER_PROXY_URL, then Bright Data, then Oxylabs."""
    explicit = env("DISCOVER_PROXY_URL")
    if explicit:
        return explicit
    for name, fn in (("brightdata", bright_data_proxy_url), ("oxylabs", oxylabs_proxy_url)):
        try:
            u = fn()
            if u:
                log(f"proxy: using {name}")
                return u
        except Exception as e:
            log(f"proxy {name} config err: {e}")
    return None
