"""Cloud reset helpers for keeping dashboard state aligned with local memory."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from lerim.config.settings import Config

_HTTP_TIMEOUT_SECONDS = 30


def _endpoint_candidates(endpoint: str) -> list[str]:
    """Return endpoint URLs to try from the current process."""
    clean_endpoint = endpoint.rstrip("/")
    parsed = urllib.parse.urlsplit(clean_endpoint)
    if parsed.hostname != "host.docker.internal":
        return [clean_endpoint]

    host_endpoint = urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc.replace("host.docker.internal", "localhost", 1),
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    ).rstrip("/")
    return [clean_endpoint, host_endpoint]


def reset_cloud_data(config: Config, *, dry_run: bool) -> dict[str, Any]:
    """Reset authenticated cloud dashboard data when cloud auth is configured."""
    if not config.cloud_endpoint or not config.cloud_token:
        return {"configured": False, "dry_run": dry_run, "deleted": {}}

    if dry_run:
        return {"configured": True, "dry_run": True, "deleted": {}}

    last_error = ""
    for endpoint in _endpoint_candidates(config.cloud_endpoint):
        request = urllib.request.Request(
            f"{endpoint}/api/v1/admin/reset",
            headers={
                "Authorization": f"Bearer {config.cloud_token}",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return {
                "configured": True,
                "dry_run": False,
                "error": False,
                "deleted": payload.get("deleted", {}),
                "endpoint": endpoint,
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            last_error = f"HTTP {exc.code}: {body}"
            break
        except (OSError, json.JSONDecodeError) as exc:
            last_error = str(exc)

    return {
        "configured": True,
        "dry_run": False,
        "error": True,
        "message": f"cloud reset failed: {last_error}",
    }
