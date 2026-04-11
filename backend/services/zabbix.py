"""Zabbix API client.

Connects to a Zabbix server to fetch host and problem data.
Cache is stored in backend/data/zabbix_cache.json.
Config (url, api_token) is stored in backend/data/zabbix_config.json.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

if os.environ.get("ITMANAGER_DATA_DIR"):
    DATA_DIR = Path(os.environ["ITMANAGER_DATA_DIR"]) / "data"
else:
    DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = DATA_DIR / "zabbix_config.json"
CACHE_PATH = DATA_DIR / "zabbix_cache.json"


# ── Config ────────────────────────────────────────────────────

def load_config() -> dict | None:
    if not CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if data.get("url") and (data.get("api_token") or (data.get("username") and data.get("password"))):
            return data
    except Exception:
        pass
    return None


def save_config(url: str, api_token: str = "", username: str = "", password: str = "") -> None:
    data = {"url": url.rstrip("/")}
    if api_token:
        data["api_token"] = api_token
    elif username and password:
        data["username"] = username
        data["password"] = password
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def delete_config() -> None:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()


def get_masked_config() -> dict | None:
    cfg = load_config()
    if not cfg:
        return None
    result = {"url": cfg["url"], "auth_mode": "token"}
    if cfg.get("api_token"):
        token = cfg["api_token"]
        result["api_token"] = "****" + token[-4:] if len(token) > 4 else "****"
    elif cfg.get("username"):
        result["auth_mode"] = "login"
        result["username"] = cfg["username"]
        result["api_token"] = ""
    return result


# ── Zabbix API calls ─────────────────────────────────────────

_session_token: str | None = None


async def _zabbix_api(url: str, token: str, method: str, params: dict | None = None, auth_token: str | None = None) -> dict:
    """Call a Zabbix JSON-RPC API method.

    token: API Bearer token (for API token auth)
    auth_token: session token from user.login (for login/password auth)
    """
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": 1,
    }
    # If using session-based auth (login/password), add auth to payload
    if auth_token:
        payload["auth"] = auth_token

    headers = {"Content-Type": "application/json-rpc"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.post(f"{url}/api_jsonrpc.php", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise ValueError(f"Zabbix API error: {data['error']}")
        return data.get("result", {})


async def _get_session_token(url: str, username: str, password: str) -> str:
    """Authenticate via user.login and return a session token."""
    global _session_token
    payload = {
        "jsonrpc": "2.0",
        "method": "user.login",
        "params": {"username": username, "password": password},
        "id": 1,
    }
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.post(f"{url}/api_jsonrpc.php", json=payload, headers={"Content-Type": "application/json-rpc"})
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise ValueError(f"Zabbix login failed: {data['error']}")
        _session_token = data.get("result", "")
        return _session_token


async def _api_call(cfg: dict, method: str, params: dict) -> list | dict:
    """Call Zabbix API with either token or login/password auth."""
    url = cfg["url"]
    if cfg.get("api_token"):
        return await _zabbix_api(url, cfg["api_token"], method, params)
    else:
        # Login/password auth — get session token
        global _session_token
        if not _session_token:
            _session_token = await _get_session_token(url, cfg["username"], cfg["password"])
        try:
            return await _zabbix_api(url, "", method, params, auth_token=_session_token)
        except ValueError:
            # Session might have expired, retry with fresh login
            _session_token = await _get_session_token(url, cfg["username"], cfg["password"])
            return await _zabbix_api(url, "", method, params, auth_token=_session_token)


async def fetch_hosts(cfg: dict) -> list[dict]:
    """Fetch all monitored hosts with their interfaces."""
    return await _api_call(cfg, "host.get", {
        "output": ["hostid", "host", "name", "status", "description"],
        "selectInterfaces": ["ip"],
        "selectGroups": ["name"],
        "sortfield": "name",
    })


async def fetch_problems(cfg: dict) -> list[dict]:
    """Fetch current active problems (triggers in problem state)."""
    return await _api_call(cfg, "problem.get", {
        "output": ["eventid", "name", "severity", "clock", "acknowledged"],
        "selectHosts": ["name"],
        "recent": True,
        "sortfield": ["eventid"],
        "sortorder": "DESC",
        "limit": 200,
    })


# ── Cache ─────────────────────────────────────────────────────

def load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {"hosts": [], "problems": [], "synced_at": None}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"hosts": [], "problems": [], "synced_at": None}


def save_cache(hosts: list[dict], problems: list[dict]) -> dict:
    data = {
        "hosts": hosts,
        "problems": problems,
        "synced_at": datetime.now().isoformat(timespec="seconds"),
    }
    CACHE_PATH.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return data


async def sync_all() -> dict:
    """Full sync: fetch hosts + problems from Zabbix and cache."""
    cfg = load_config()
    if not cfg:
        raise ValueError("Zabbix credentials not configured")

    hosts = await fetch_hosts(cfg)
    problems = await fetch_problems(cfg)
    return save_cache(hosts, problems)
