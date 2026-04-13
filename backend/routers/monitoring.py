"""Monitoring (Zabbix) router — hosts, problems, stats, overview, host detail."""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..schemas.monitoring import (
    MonitoringConfig,
    MonitoringConfigResponse,
    MonitoringHost,
    MonitoringProblem,
    MonitoringStats,
    SyncResponse,
)
from ..services.zabbix import (
    delete_config,
    fetch_host_items,
    get_masked_config,
    load_cache,
    load_config,
    save_config,
    sync_all,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


# ── Config ────────────────────────────────────────────────────

@router.get("/config")
async def get_config():
    cfg = get_masked_config()
    if not cfg:
        return {"configured": False, "url": "", "api_token": "", "auth_mode": "token", "username": ""}
    return MonitoringConfigResponse(
        url=cfg["url"],
        api_token=cfg.get("api_token", ""),
        auth_mode=cfg.get("auth_mode", "token"),
        username=cfg.get("username", ""),
        configured=True,
    )


@router.put("/config")
async def update_config(body: MonitoringConfig):
    if not body.url:
        raise HTTPException(400, "URL is required")
    if not body.api_token and not (body.username and body.password):
        raise HTTPException(400, "API token ou login/password requis")
    save_config(body.url, api_token=body.api_token, username=body.username, password=body.password)
    return {"status": "ok"}


@router.delete("/config", status_code=204)
async def remove_config():
    delete_config()


# ── Sync ──────────────────────────────────────────────────────

@router.post("/sync", response_model=SyncResponse)
async def trigger_sync():
    try:
        data = await sync_all()
        return SyncResponse(
            total_hosts=len(data["hosts"]),
            total_problems=len(data["problems"]),
            synced_at=data["synced_at"],
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Zabbix sync failed")
        raise HTTPException(502, f"Sync failed: {e}")


# ── Hosts ─────────────────────────────────────────────────────

def _get_host_availability(raw: dict) -> str:
    """Determine host availability from interfaces or host-level field."""
    # Zabbix 7+: check interface availability
    interfaces = raw.get("interfaces") or []
    for iface in interfaces:
        avail = str(iface.get("available", "0"))
        if avail == "1":
            return "available"
        if avail == "2":
            return "unavailable"
    # Fallback: host-level available field
    avail = str(raw.get("available", "0"))
    if avail == "1":
        return "available"
    if avail == "2":
        return "unavailable"
    return "unknown"


def _normalize_host(raw: dict) -> dict:
    """Map raw Zabbix host to our schema."""
    interfaces = raw.get("interfaces") or []
    ip = interfaces[0].get("ip", "") if interfaces else ""
    groups = [g.get("name", "") for g in (raw.get("hostgroups") or raw.get("groups") or [])]
    status = "enabled" if str(raw.get("status")) == "0" else "disabled"
    availability = _get_host_availability(raw)

    return dict(
        id=raw.get("hostid", ""),
        name=raw.get("name", ""),
        host=raw.get("host", ""),
        status=status,
        available=availability,
        groups=groups,
        ip=ip,
        description=raw.get("description", ""),
        last_problem="",
    )


@router.get("/hosts", response_model=list[MonitoringHost])
async def list_hosts():
    cache = load_cache()
    hosts = [MonitoringHost(**_normalize_host(h)) for h in cache.get("hosts", [])]
    # Enrich with last problem info
    problems = cache.get("problems", [])
    host_problems = {}
    for p in problems:
        for h in (p.get("hosts") or []):
            hname = h.get("name", "")
            if hname and hname not in host_problems:
                host_problems[hname] = p.get("name", "")
    for host in hosts:
        host.last_problem = host_problems.get(host.name, "")
    return hosts


# ── Host detail ──────────────────────────────────────────────

@router.get("/hosts/{hostid}")
async def get_host_detail(hostid: str):
    cache = load_cache()
    # Find host in cache
    raw_host = None
    for h in cache.get("hosts", []):
        if h.get("hostid") == hostid:
            raw_host = h
            break
    if not raw_host:
        raise HTTPException(404, "Host not found in cache")

    host = _normalize_host(raw_host)

    # Get problems for this host
    host_problems = []
    for p in cache.get("problems", []):
        for ph in (p.get("hosts") or []):
            if ph.get("hostid") == hostid or ph.get("name") == host["name"]:
                host_problems.append(_normalize_problem(p))
                break

    # Fetch items/metrics from Zabbix API (live, not cached)
    items = []
    try:
        cfg = load_config()
        if cfg:
            raw_items = await fetch_host_items(cfg, hostid)
            for item in raw_items:
                items.append({
                    "id": item.get("itemid", ""),
                    "name": item.get("name", ""),
                    "key": item.get("key_", ""),
                    "value": item.get("lastvalue", ""),
                    "units": item.get("units", ""),
                    "lastclock": item.get("lastclock", ""),
                })
    except Exception as e:
        logger.warning(f"Failed to fetch items for host {hostid}: {e}")

    return {
        "host": host,
        "problems": host_problems,
        "items": items,
    }


# ── Problems ──────────────────────────────────────────────────

_SEVERITY_MAP = {
    "0": "non classe",
    "1": "information",
    "2": "avertissement",
    "3": "moyen",
    "4": "eleve",
    "5": "catastrophe",
}

_SEVERITY_ORDER = {"5": 0, "4": 1, "3": 2, "2": 3, "1": 4, "0": 5}


def _normalize_problem(raw: dict) -> dict:
    hosts = raw.get("hosts") or []
    host_name = hosts[0].get("name", "") if hosts else ""
    sev_num = str(raw.get("severity", "0"))
    sev = _SEVERITY_MAP.get(sev_num, "inconnu")

    ts = raw.get("clock", "")
    try:
        ts = datetime.fromtimestamp(int(ts)).isoformat(timespec="seconds") if ts else ""
    except (ValueError, OSError):
        pass

    return dict(
        id=raw.get("eventid", ""),
        host=host_name,
        severity=sev,
        severity_num=int(sev_num),
        name=raw.get("name", ""),
        timestamp=ts,
        acknowledged=str(raw.get("acknowledged")) == "1",
    )


@router.get("/problems", response_model=list[MonitoringProblem])
async def list_problems():
    cache = load_cache()
    problems = [_normalize_problem(p) for p in cache.get("problems", [])]
    # Sort by severity descending
    problems.sort(key=lambda p: p.get("severity_num", 0), reverse=True)
    return [MonitoringProblem(**{k: v for k, v in p.items() if k != "severity_num"}) for p in problems]


# ── Overview (aggregated data for charts) ────────────────────

@router.get("/overview")
async def monitoring_overview():
    cache = load_cache()
    hosts = cache.get("hosts", [])
    problems = cache.get("problems", [])
    groups = cache.get("groups", [])

    # Host availability
    avail_counts = {"available": 0, "unavailable": 0, "unknown": 0}
    enabled_hosts = [h for h in hosts if str(h.get("status")) == "0"]
    for h in enabled_hosts:
        a = _get_host_availability(h)
        avail_counts[a] = avail_counts.get(a, 0) + 1

    # Problems by severity
    sev_counts = {v: 0 for v in _SEVERITY_MAP.values()}
    for p in problems:
        sev = _SEVERITY_MAP.get(str(p.get("severity", "0")), "inconnu")
        sev_counts[sev] = sev_counts.get(sev, 0) + 1

    # Groups with host counts
    group_data = []
    for g in groups:
        group_data.append({
            "name": g.get("name", ""),
            "host_count": len(g.get("hosts") or []),
        })
    group_data.sort(key=lambda g: g["host_count"], reverse=True)

    return {
        "host_availability": avail_counts,
        "problems_by_severity": sev_counts,
        "groups": group_data[:15],
    }


# ── Stats ─────────────────────────────────────────────────────

@router.get("/stats", response_model=MonitoringStats)
async def monitoring_stats():
    cache = load_cache()
    hosts = cache.get("hosts", [])
    problems = cache.get("problems", [])

    enabled = [h for h in hosts if str(h.get("status")) == "0"]
    avail = sum(1 for h in enabled if _get_host_availability(h) == "available")
    unavail = sum(1 for h in enabled if _get_host_availability(h) == "unavailable")
    unknown = len(enabled) - avail - unavail

    return MonitoringStats(
        total_hosts=len(enabled),
        available=avail,
        unavailable=unavail,
        unknown=unknown,
        active_problems=len(problems),
        synced_at=cache.get("synced_at"),
    )
