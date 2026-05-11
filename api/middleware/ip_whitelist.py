"""
IP Whitelist Middleware for Project Nexus.
Restricts API access to configured CIDR ranges.
Essential for organization-level deployment security.

Usage:
    Set in .env:
        IP_WHITELIST_ENABLED=true
        ALLOWED_IP_RANGES=192.168.1.0/24,10.0.0.0/8,127.0.0.1/32
"""

import ipaddress
from typing import List, Set

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Endpoints that bypass IP whitelist (always accessible)
EXEMPT_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    Block requests from IPs not in the configured whitelist.
    Supports CIDR notation for subnet ranges.
    Handles X-Forwarded-For headers for reverse proxy setups.
    """

    def __init__(self, app):
        super().__init__(app)
        self._networks: List[ipaddress.IPv4Network] = []
        self._parse_ranges()

    def _parse_ranges(self) -> None:
        """Parse ALLOWED_IP_RANGES from config into network objects."""
        raw = settings.ALLOWED_IP_RANGES
        if not raw:
            return

        for cidr in raw.split(","):
            cidr = cidr.strip()
            if not cidr:
                continue
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                self._networks.append(network)
            except ValueError as e:
                logger.warning(
                    "ip_whitelist_invalid_range",
                    cidr=cidr,
                    error=str(e)
                )

        logger.info(
            "ip_whitelist_configured",
            network_count=len(self._networks),
            ranges=[str(n) for n in self._networks]
        )

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract real client IP, respecting X-Forwarded-For for proxies.
        Falls back to direct connection IP.
        """
        # Check X-Forwarded-For (reverse proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP (nginx)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        # Direct connection
        if request.client:
            return request.client.host

        return "unknown"

    def _is_allowed(self, ip_str: str) -> bool:
        """Check if an IP address is in any whitelisted network."""
        if ip_str == "unknown":
            return False

        try:
            # Handle IPv4-mapped IPv6 addresses (::ffff:127.0.0.1 -> 127.0.0.1)
            if ip_str.startswith("::ffff:"):
                ip_str = ip_str[7:]

            client_ip = ipaddress.ip_address(ip_str)
            return any(
                client_ip in network
                for network in self._networks
            )
        except ValueError:
            logger.warning("ip_whitelist_invalid_ip", ip=ip_str)
            return False

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip check if whitelist is disabled (use getattr for safety)
        if not getattr(settings, "IP_WHITELIST_ENABLED", False):
            return await call_next(request)

        # Exempt paths (health check, docs)
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        if not self._is_allowed(client_ip):
            logger.warning(
                "ip_whitelist_blocked",
                client_ip=client_ip,
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=403,
                content={
                    "status": "error",
                    "code": "ACCESS_DENIED",
                    "message": "Access denied. Your IP address is not authorized.",
                }
            )

        return await call_next(request)
