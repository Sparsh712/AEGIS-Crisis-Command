"""Small async HTTP boundary with deterministic disk caching and fallbacks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import httpx


DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_RETRY_COUNT = 1
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"


@dataclass(frozen=True)
class HttpResult:
    """JSON payload plus machine-readable cache and fallback state."""

    data: Any | None
    metadata: dict[str, Any]


def _cache_path(cache_dir: Path, cache_key: str) -> Path:
    digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.json"


def _load_fixture(fixture: Any) -> Any:
    if isinstance(fixture, Mapping):
        return dict(fixture)
    if isinstance(fixture, (str, Path)):
        path = Path(fixture)
        if not path.exists():
            raise FileNotFoundError(f"fixture not found: {path}")
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return fixture


def _read_cache(path: Path) -> Any | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            envelope = json.load(handle)
        if isinstance(envelope, Mapping) and "data" in envelope:
            return envelope["data"]
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return None


def _write_cache(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump({"data": data}, handle, sort_keys=True)
    temporary.replace(path)


async def fetch_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    cache_key: str | None = None,
    cache_dir: str | Path | None = None,
    fixture: Any = None,
    fixture_only: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    retry_count: int = DEFAULT_RETRY_COUNT,
    client_factory: Callable[..., Any] | None = None,
) -> HttpResult:
    """Fetch JSON once, retry once by default, and keep offline behavior safe."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if retry_count < 0:
        raise ValueError("retry_count must be non-negative")

    cache_root = Path(cache_dir) if cache_dir is not None else DEFAULT_CACHE_DIR
    encoded_params = json.dumps(dict(params or {}), sort_keys=True, default=str)
    effective_key = cache_key or f"{url}?{encoded_params}"
    path = _cache_path(cache_root, effective_key)
    metadata: dict[str, Any] = {
        "url": url,
        "cache_key": effective_key,
        "cache_path": str(path),
        "cache_status": "miss",
        "fallback": False,
        "fallback_source": None,
        "fixture_only": fixture_only,
        "network_attempted": False,
        "attempts": 0,
        "timeout_seconds": timeout_seconds,
        "retry_count": retry_count,
    }

    if fixture_only:
        try:
            data = _load_fixture(fixture)
        except Exception as exc:
            metadata.update(
                {
                    "cache_status": "fallback",
                    "fallback": True,
                    "fallback_source": "none",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            return HttpResult(None, metadata)
        if data is not None:
            metadata.update({"cache_status": "fixture", "fallback_source": "fixture"})
            return HttpResult(data, metadata)

        cached = _read_cache(path)
        if cached is not None:
            metadata.update({"cache_status": "hit", "fallback_source": "cache"})
            return HttpResult(cached, metadata)
        metadata.update({"cache_status": "disabled", "fallback": True, "fallback_source": "none"})
        return HttpResult(None, metadata)

    cached = _read_cache(path)
    if cached is not None:
        metadata.update({"cache_status": "hit", "fallback_source": "cache"})
        return HttpResult(cached, metadata)

    factory = client_factory or httpx.AsyncClient
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        metadata["attempts"] = attempt + 1
        metadata["network_attempted"] = True
        try:
            async with factory(timeout=timeout_seconds) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            try:
                _write_cache(path, data)
                metadata["cache_written"] = True
            except (OSError, TypeError, ValueError) as exc:
                metadata.update({"cache_written": False, "cache_write_error": str(exc)})
            return HttpResult(data, metadata)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            last_error = exc

    metadata.update(
        {
            "cache_status": "fallback",
            "fallback": True,
            "error": str(last_error) if last_error else "request failed",
            "error_type": type(last_error).__name__ if last_error else "RequestError",
        }
    )
    cached = _read_cache(path)
    if cached is not None:
        metadata["fallback_source"] = "cache"
        return HttpResult(cached, metadata)
    if fixture is not None:
        try:
            data = _load_fixture(fixture)
        except Exception as exc:
            metadata.update({"fallback_source": "none", "fixture_error": str(exc)})
            return HttpResult(None, metadata)
        metadata["fallback_source"] = "fixture"
        return HttpResult(data, metadata)
    metadata["fallback_source"] = "none"
    return HttpResult(None, metadata)


request_json = fetch_json
