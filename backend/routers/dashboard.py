from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, Query

from ..database import get_raw_db

logger = logging.getLogger(__name__)
from ..schemas.dashboard import (
    CategoryStatItem,
    CompletionResponse,
    KpiResponse,
    SystemMonitorResponse,
    TopTaskResponse,
    WeeklyStatItem,
)
from ..services.system_monitor import get_system_stats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/kpis", response_model=KpiResponse)
async def kpis(db=Depends(get_raw_db)):
    today = date.today().isoformat()
    # End of week (Sunday)
    week_end = (date.today() + timedelta(days=(6 - date.today().weekday()))).isoformat()

    row = await db.execute_fetchall(
        "SELECT COUNT(*) FROM tasks WHERE done = 0"
    )
    open_tasks = row[0][0]

    row = await db.execute_fetchall(
        "SELECT COUNT(*) FROM tasks WHERE done = 0 AND due_date IS NOT NULL AND due_date != '' AND due_date < ?",
        (today,),
    )
    overdue_tasks = row[0][0]

    # Overdue tasks that belong to a project (subset of overdue_tasks)
    overdue_project_tasks = 0
    try:
        row = await db.execute_fetchall(
            "SELECT COUNT(*) FROM tasks WHERE done = 0 AND due_date IS NOT NULL AND due_date != '' AND due_date < ? AND project_id IS NOT NULL",
            (today,),
        )
        overdue_project_tasks = row[0][0]
    except Exception:
        pass

    row = await db.execute_fetchall(
        "SELECT COUNT(*) FROM tasks WHERE done = 0 AND due_date IS NOT NULL AND due_date != '' AND due_date >= ? AND due_date <= ?",
        (today, week_end),
    )
    week_tasks = row[0][0]

    row = await db.execute_fetchall("SELECT COUNT(*) FROM documents")
    documents = row[0][0]

    row = await db.execute_fetchall("SELECT COUNT(*) FROM parc_equipment")
    equipment = row[0][0]

    return KpiResponse(
        open_tasks=open_tasks,
        overdue_tasks=overdue_tasks,
        overdue_project_tasks=overdue_project_tasks,
        week_tasks=week_tasks,
        documents=documents,
        equipment=equipment,
    )


@router.get("/sysmon", response_model=SystemMonitorResponse)
async def sysmon():
    return SystemMonitorResponse(**get_system_stats())


@router.get("/stats/weekly", response_model=list[WeeklyStatItem])
async def stats_weekly(db=Depends(get_raw_db)):
    """Tasks completed per week for the last 8 weeks."""
    results: list[WeeklyStatItem] = []
    today = date.today()
    for i in range(7, -1, -1):
        week_start = today - timedelta(weeks=i, days=today.weekday())
        week_end = week_start + timedelta(days=6)
        row = await db.execute_fetchall(
            "SELECT COUNT(*) FROM tasks WHERE done = 1 AND created_at >= ? AND created_at <= ?",
            (week_start.isoformat(), week_end.isoformat() + "T23:59:59"),
        )
        label = f"S{week_start.isocalendar()[1]}"
        results.append(WeeklyStatItem(label=label, count=row[0][0]))
    return results


@router.get("/stats/categories", response_model=list[CategoryStatItem])
async def stats_categories(db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        "SELECT COALESCE(category, '') as cat, COUNT(*) as cnt FROM tasks WHERE done = 0 GROUP BY cat ORDER BY cnt DESC"
    )
    return [CategoryStatItem(category=r[0] or "Sans catégorie", count=r[1]) for r in rows]


@router.get("/stats/completion", response_model=CompletionResponse)
async def stats_completion(db=Depends(get_raw_db)):
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    month_end = today.isoformat() + "T23:59:59"

    row = await db.execute_fetchall(
        "SELECT COUNT(*) FROM tasks WHERE created_at >= ? AND created_at <= ?",
        (month_start, month_end),
    )
    created = row[0][0]

    row = await db.execute_fetchall(
        "SELECT COUNT(*) FROM tasks WHERE done = 1 AND created_at >= ? AND created_at <= ?",
        (month_start, month_end),
    )
    done = row[0][0]

    rate = round((done / created * 100) if created > 0 else 0, 1)
    return CompletionResponse(created=created, done=done, rate=rate)


@router.get("/top-tasks", response_model=list[TopTaskResponse])
async def top_tasks(limit: int = Query(5, ge=1, le=50), db=Depends(get_raw_db)):
    rows = await db.execute_fetchall(
        """SELECT id, title, COALESCE(category,'') as category, priority,
                  due_date, COALESCE(site,'') as site
           FROM tasks
           WHERE done = 0
           ORDER BY priority ASC, due_date ASC NULLS LAST
           LIMIT ?""",
        (limit,),
    )
    return [
        TopTaskResponse(
            id=r[0], title=r[1], category=r[2], priority=r[3], due_date=r[4], site=r[5]
        )
        for r in rows
    ]


# ── Weather (free, no API key) ────────────────────────────────
_weather_cache: dict = {}

@router.get("/weather")
async def weather():
    """Get weather using configured city or IP geolocation + Open-Meteo (free, no API key needed)."""
    import time

    # Check configured city
    from .settings import GENERAL_FILE, GENERAL_DEFAULTS, _ensure_file, _read_json
    settings_path = _ensure_file(GENERAL_FILE, "general_settings.json", GENERAL_DEFAULTS)
    settings = _read_json(settings_path)
    configured_city = (settings.get("weather_city") or "").strip()

    # Invalidate cache if city changed or cache is older than 30 min
    cached_city = _weather_cache.get("city", "")
    cache_valid = (
        _weather_cache.get("data")
        and time.time() - _weather_cache.get("ts", 0) < 1800
        and cached_city == configured_city
    )
    if cache_valid:
        return _weather_cache["data"]

    try:

        async with httpx.AsyncClient(timeout=10) as client:
            if configured_city:
                # Use Open-Meteo geocoding to resolve city name → coordinates.
                # URL-encode so cities with spaces or accents ("La Rochelle", "Mâcon",
                # "Saint-Étienne") don't break the request URL.
                from urllib.parse import quote_plus
                geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={quote_plus(configured_city)}&count=1&language=fr"
                geo = await client.get(geo_url)
                geo_results = geo.json().get("results", [])
                if geo_results:
                    lat = geo_results[0]["latitude"]
                    lon = geo_results[0]["longitude"]
                    city = geo_results[0].get("name", configured_city)
                else:
                    # Don't silently fall back to Paris coords — that misled the user
                    # into seeing their city's name with another city's weather.
                    logger.warning(f"Weather: geocoding failed for '{configured_city}'")
                    return {
                        "city": configured_city,
                        "temperature": None,
                        "humidity": None,
                        "wind_speed": None,
                        "emoji": "\u2753",
                        "description": f"Ville '{configured_city}' introuvable",
                        "forecast": [],
                    }
            else:
                # Fallback: IP geolocation
                geo = await client.get("http://ip-api.com/json/?fields=city,lat,lon")
                geo_data = geo.json()
                lat = geo_data.get("lat", 48.86)
                lon = geo_data.get("lon", 2.35)
                city = geo_data.get("city", "Paris")

            # 2. Get weather from Open-Meteo (free, no key)
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                f"&daily=temperature_2m_max,temperature_2m_min,weather_code"
                f"&timezone=auto&forecast_days=3"
            )
            resp = await client.get(weather_url)
            data = resp.json()

            current = data.get("current", {})
            daily = data.get("daily", {})

            # WMO weather codes → description + emoji
            wmo = _wmo_code(current.get("weather_code", 0))

            result = {
                "city": city,
                "temperature": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "wind_speed": current.get("wind_speed_10m"),
                "description": wmo["desc"],
                "emoji": wmo["emoji"],
                "forecast": [],
            }

            # 3-day forecast
            for i in range(min(3, len(daily.get("time", [])))):
                fc_wmo = _wmo_code(daily["weather_code"][i])
                result["forecast"].append({
                    "date": daily["time"][i],
                    "temp_max": daily["temperature_2m_max"][i],
                    "temp_min": daily["temperature_2m_min"][i],
                    "description": fc_wmo["desc"],
                    "emoji": fc_wmo["emoji"],
                })

            _weather_cache["data"] = result
            _weather_cache["ts"] = time.time()
            _weather_cache["city"] = configured_city
            return result

    except Exception as e:
        logger.warning(f"Weather fetch failed: {e}")
        return {"city": "N/A", "temperature": None, "emoji": "\u2601\uFE0F", "description": "Indisponible", "forecast": []}


def _wmo_code(code: int) -> dict:
    """Convert WMO weather code to description + emoji."""
    mapping = {
        0: ("Ciel dégagé", "☀️"), 1: ("Peu nuageux", "🌤️"),
        2: ("Partiellement nuageux", "⛅"), 3: ("Couvert", "☁️"),
        45: ("Brouillard", "🌫️"), 48: ("Brouillard givrant", "🌫️"),
        51: ("Bruine légère", "🌦️"), 53: ("Bruine", "🌦️"), 55: ("Bruine forte", "🌧️"),
        61: ("Pluie légère", "🌦️"), 63: ("Pluie", "🌧️"), 65: ("Pluie forte", "🌧️"),
        71: ("Neige légère", "🌨️"), 73: ("Neige", "❄️"), 75: ("Neige forte", "❄️"),
        80: ("Averses", "🌦️"), 81: ("Averses modérées", "🌧️"), 82: ("Averses violentes", "🌧️"),
        85: ("Averses de neige", "🌨️"), 86: ("Averses de neige fortes", "🌨️"),
        95: ("Orage", "⛈️"), 96: ("Orage grêle", "⛈️"), 99: ("Orage grêle fort", "⛈️"),
    }
    desc, emoji = mapping.get(code, ("Inconnu", "🌀"))
    return {"desc": desc, "emoji": emoji}


# ── Recent activity feed ──────────────────────────────────────

@router.get("/activity")
async def recent_activity(limit: int = Query(15, ge=1, le=50), db=Depends(get_raw_db)):
    """Aggregate recent actions across all modules."""
    activities = []

    # Recent tasks (created or completed)
    rows = await db.execute_fetchall(
        "SELECT id, title, done, created_at FROM tasks ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    for r in rows:
        activities.append({
            "type": "task",
            "emoji": "✅" if r[2] else "📋",
            "text": f"{'Terminée' if r[2] else 'Créée'} : {r[1]}",
            "date": r[3],
        })

    # Recent planning events
    rows = await db.execute_fetchall(
        "SELECT id, title, created_at FROM planning_events ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    for r in rows:
        activities.append({
            "type": "planning",
            "emoji": "📅",
            "text": f"Événement : {r[1]}",
            "date": r[2],
        })

    # Recent documents
    rows = await db.execute_fetchall(
        "SELECT id, title, created_at FROM documents ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    for r in rows:
        activities.append({
            "type": "document",
            "emoji": "📄",
            "text": f"Document : {r[1]}",
            "date": r[2],
        })

    # Recent changelog entries
    rows = await db.execute_fetchall(
        "SELECT id, title, created_at FROM changelog_entries ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    for r in rows:
        activities.append({
            "type": "changelog",
            "emoji": "📋",
            "text": f"Changelog : {r[1]}",
            "date": r[2],
        })

    # Recent wiki articles
    rows = await db.execute_fetchall(
        "SELECT id, title, updated_at FROM wiki_articles ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    )
    for r in rows:
        activities.append({
            "type": "wiki",
            "emoji": "📖",
            "text": f"Procédure : {r[1]}",
            "date": r[2],
        })

    # Sort all by date descending
    activities.sort(key=lambda a: a.get("date") or "", reverse=True)
    return activities[:limit]


# ── v7.5.0 — Attention feed (cross-module alerts on the home) ────────────────


@router.get("/attention")
async def attention_items(db=Depends(get_raw_db)):
    """Aggregated list of items requiring user attention across every module.

    Sources surfaced (when relevant data is present in the DB):
      - Overdue tasks: due_date < today and not done
      - Stale dossiers: status != 'archive', no comment activity in 30 days,
        and the dossier itself was created > 30 days ago
      - Devis received without BPA: status='devis_recu' for > 14 days
      - Chromebooks support ending soon: support_end_date < today + 180d
      - Parc warranty ending soon: warranty_end < today + 60d
      - Backups: most recent automatic backup > 7 days old

    Each item has shape:
        { severity, kind, icon, title, sub, target, count }
    `target` is the page path the UI should navigate to on click.
    Severity is one of: 'critical' (red), 'warning' (orange), 'info' (blue).
    """
    today = date.today()
    today_iso = today.isoformat()
    items: list[dict] = []

    # ── 1. Overdue tasks ────────────────────────────────────────────
    try:
        row = await db.execute_fetchall(
            "SELECT COUNT(*) FROM tasks "
            "WHERE done = 0 AND due_date IS NOT NULL AND due_date != '' "
            "AND due_date < ?",
            (today_iso,),
        )
        overdue_tasks = row[0][0]
        if overdue_tasks > 0:
            items.append({
                "severity": "critical",
                "kind": "tasks_overdue",
                "icon": "AlertTriangle",
                "title": f"{overdue_tasks} tâche{'s' if overdue_tasks > 1 else ''} en retard",
                "sub": "À traiter ou reporter",
                "target": "/tasks",
                "count": overdue_tasks,
            })
    except Exception:
        pass

    # ── 2. Stale dossiers (no activity in 30 days) ─────────────────
    try:
        threshold = (today - timedelta(days=30)).isoformat()
        rows = await db.execute_fetchall(
            """SELECT d.id, d.title FROM dossiers d
               WHERE d.status NOT IN ('archive')
                 AND d.created_at < ?
                 AND NOT EXISTS (
                     SELECT 1 FROM dossier_comments c
                     WHERE c.dossier_id = d.id AND c.created_at >= ?
                 )
               LIMIT 20""",
            (threshold, threshold),
        )
        n = len(rows)
        if n > 0:
            items.append({
                "severity": "warning",
                "kind": "dossiers_stale",
                "icon": "Folder",
                "title": f"{n} dossier{'s' if n > 1 else ''} sans activité depuis 30 j",
                "sub": "À relancer auprès du prestataire ou archiver",
                "target": "/documents",
                "count": n,
            })
    except Exception:
        pass

    # ── 3. Devis en attente de BPA depuis > 14 jours ───────────────
    try:
        threshold = (today - timedelta(days=14)).isoformat()
        row = await db.execute_fetchall(
            "SELECT COUNT(*) FROM dossiers "
            "WHERE status = 'devis_recu' AND updated_at < ?",
            (threshold,),
        )
        n = row[0][0]
        if n > 0:
            items.append({
                "severity": "info",
                "kind": "devis_pending_bpa",
                "icon": "FileText",
                "title": f"{n} devis en attente de BPA",
                "sub": "Plus de 14 jours sans transition vers le BPA",
                "target": "/documents",
                "count": n,
            })
    except Exception:
        pass

    # ── 4. Chromebooks fin de support proche ───────────────────────
    try:
        threshold = (today + timedelta(days=180)).isoformat()
        row = await db.execute_fetchall(
            "SELECT COUNT(*) FROM chromebooks "
            "WHERE support_end_date IS NOT NULL AND support_end_date != '' "
            "AND support_end_date <= ?",
            (threshold,),
        )
        n = row[0][0]
        if n > 0:
            items.append({
                "severity": "warning",
                "kind": "chromebooks_support_soon",
                "icon": "Laptop",
                "title": f"{n} Chromebook{'s' if n > 1 else ''} fin de support sous 6 mois",
                "sub": "À anticiper pour la rentrée prochaine",
                "target": "/chromebooks",
                "count": n,
            })
    except Exception:
        pass

    # ── 5. Garanties Parc proches d'expiration ─────────────────────
    try:
        threshold = (today + timedelta(days=60)).isoformat()
        row = await db.execute_fetchall(
            "SELECT COUNT(*) FROM parc_equipment "
            "WHERE warranty_end IS NOT NULL AND warranty_end != '' "
            "AND warranty_end > ? AND warranty_end <= ?",
            (today_iso, threshold),
        )
        n = row[0][0]
        if n > 0:
            items.append({
                "severity": "info",
                "kind": "parc_warranty_soon",
                "icon": "Shield",
                "title": f"{n} équipement{'s' if n > 1 else ''} : garantie sous 60 j",
                "sub": "Décider renouvellement ou remplacement",
                "target": "/parc",
                "count": n,
            })
    except Exception:
        pass

    # ── 6. Backups : > 7 jours sans backup auto ────────────────────
    try:
        import os as _os
        if _os.environ.get("ITMANAGER_DATA_DIR"):
            backup_dir = (
                __import__("pathlib").Path(_os.environ["ITMANAGER_DATA_DIR"])
                / "backups"
            )
        else:
            backup_dir = (
                __import__("pathlib").Path(__file__).resolve().parent.parent
                / "backups"
            )
        if backup_dir.exists():
            autos = sorted(
                backup_dir.glob("auto_backup_*.zip"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if autos:
                last = autos[0]
                age_days = (
                    datetime.now() - datetime.fromtimestamp(last.stat().st_mtime)
                ).days
                if age_days >= 7:
                    items.append({
                        "severity": "warning",
                        "kind": "backup_stale",
                        "icon": "Database",
                        "title": f"Pas de sauvegarde auto depuis {age_days} j",
                        "sub": "Vérifier la configuration dans Paramètres",
                        "target": "/settings",
                        "count": 1,
                    })
    except Exception:
        pass

    # Sort by severity priority (critical first), then by item kind.
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    items.sort(key=lambda i: (severity_rank.get(i["severity"], 99), i["kind"]))
    return {"items": items, "total": len(items)}
