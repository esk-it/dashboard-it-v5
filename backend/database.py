from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import aiosqlite
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# When running as PyInstaller bundle, use AppData for persistent storage
if os.environ.get("ITMANAGER_DATA_DIR"):
    BASE_DIR = Path(os.environ["ITMANAGER_DATA_DIR"])
else:
    BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "dashboard.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    """FastAPI dependency – yields an async SQLAlchemy session."""
    async with async_session_factory() as session:
        yield session


async def get_raw_db():
    """FastAPI dependency – yields a raw aiosqlite connection.

    Preferred for read/query endpoints to avoid ORM schema mismatch with
    the existing database.
    """
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    try:
        yield db
    finally:
        await db.close()


def _apply_pending_restore():
    """Apply a staged backup restore before any DB connection is opened.
    The restore endpoint extracts files to *.pending-restore staging paths and
    drops a `.restore-pending` marker; we swap them in here on startup so the
    live SQLite connection is never disturbed.
    """
    import shutil as _shutil
    marker = BASE_DIR / ".restore-pending"
    if not marker.exists():
        return

    print(f"[restore] Applying pending restore (marker: {marker})")
    try:
        # 1. DB file
        staging_db = DB_PATH.with_suffix(".db.pending-restore")
        if staging_db.exists():
            # Clear any leftover WAL/SHM so we don't mix new DB with old journal
            for suffix in [".db-wal", ".db-shm"]:
                p = DB_PATH.parent / (DB_PATH.stem + suffix)
                if p.exists():
                    try: p.unlink()
                    except Exception as e: print(f"[restore] couldn't remove {p}: {e}")
            if DB_PATH.exists():
                try: DB_PATH.unlink()
                except Exception as e: print(f"[restore] couldn't remove old DB: {e}")
            staging_db.rename(DB_PATH)
            print(f"[restore] DB swapped: {DB_PATH}")

        # 2. Config JSONs
        for dest in [
            BASE_DIR / "data" / "general_settings.json",
            BASE_DIR / "data" / "settings.json",
            BASE_DIR / "data" / "rss_feeds.json",
        ]:
            pending = dest.with_suffix(dest.suffix + ".pending-restore")
            if pending.exists():
                if dest.exists():
                    try: dest.unlink()
                    except Exception: pass
                pending.rename(dest)
                print(f"[restore] config swapped: {dest.name}")

        # 3. Logos folder — replace contents (don't blow away the folder, the running
        #    backend may be holding a directory handle to it). Wipe files, then move in
        #    the staged ones.
        pending_logos = BASE_DIR / "logos.pending-restore"
        if pending_logos.exists() and pending_logos.is_dir():
            logos_dir = BASE_DIR / "logos"
            logos_dir.mkdir(parents=True, exist_ok=True)
            for f in logos_dir.iterdir():
                if f.is_file():
                    try: f.unlink()
                    except Exception: pass
            for f in pending_logos.iterdir():
                if f.is_file():
                    try:
                        f.rename(logos_dir / f.name)
                    except Exception as e:
                        print(f"[restore] couldn't move logo {f.name}: {e}")
            try: _shutil.rmtree(pending_logos)
            except Exception: pass
            print(f"[restore] logos swapped")

        # 3b. Establishment logos — same swap pattern.
        pending_estab = BASE_DIR / "data" / "establishments.pending-restore"
        if pending_estab.exists() and pending_estab.is_dir():
            estab_dir = BASE_DIR / "data" / "establishments"
            estab_dir.mkdir(parents=True, exist_ok=True)
            for f in estab_dir.iterdir():
                if f.is_file():
                    try: f.unlink()
                    except Exception: pass
            for f in pending_estab.iterdir():
                if f.is_file():
                    try:
                        f.rename(estab_dir / f.name)
                    except Exception as e:
                        print(f"[restore] couldn't move establishment logo {f.name}: {e}")
            try: _shutil.rmtree(pending_estab)
            except Exception: pass
            print(f"[restore] establishments swapped")

    except Exception as e:
        # Never crash startup over a failed restore — leave the marker so the user can
        # see the staged files and recover manually if needed.
        import traceback; traceback.print_exc()
        print(f"[restore] FAILED to apply: {e} — marker preserved for inspection")
        return

    # All good — remove the marker so we don't try to re-apply on next startup.
    try: marker.unlink()
    except Exception: pass
    print("[restore] Pending restore applied successfully.")


async def init_db():
    """Create all tables if they don't exist (fresh install)."""
    # Apply any pending restore BEFORE opening a DB connection
    _apply_pending_restore()

    db = await aiosqlite.connect(str(DB_PATH))
    await db.execute("PRAGMA journal_mode=WAL")

    statements = [
        # --- Users ---
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            avatar_color TEXT NOT NULL DEFAULT '#8869e1',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT '',
            last_login TEXT NOT NULL DEFAULT ''
        )""",
        # --- Projects ---
        """CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'not_started',
            color TEXT NOT NULL DEFAULT '#3B82F6',
            start_date TEXT NOT NULL DEFAULT '',
            end_date TEXT NOT NULL DEFAULT '',
            budget REAL NOT NULL DEFAULT 0,
            budget_spent REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS project_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS project_suppliers (
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            supplier_id INTEGER NOT NULL,
            PRIMARY KEY (project_id, supplier_id)
        )""",
        """CREATE TABLE IF NOT EXISTS project_documents (
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            document_id INTEGER NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            amount_accepted REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (project_id, document_id)
        )""",
        # --- Tasks ---
        """CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 2,
            due_date TEXT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            site TEXT NOT NULL DEFAULT '',
            recurrence TEXT NOT NULL DEFAULT '',
            project_id INTEGER NULL,
            start_date TEXT NULL,
            is_milestone INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS task_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            sort_order INTEGER NOT NULL DEFAULT 100
        )""",
        """CREATE TABLE IF NOT EXISTS task_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS task_dependencies (
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            depends_on_task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            PRIMARY KEY (task_id, depends_on_task_id),
            CHECK (task_id != depends_on_task_id)
        )""",
        """CREATE TABLE IF NOT EXISTS task_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 2,
            notes TEXT NOT NULL DEFAULT '',
            site TEXT NOT NULL DEFAULT '',
            recurrence TEXT NOT NULL DEFAULT '',
            checklist_json TEXT NOT NULL DEFAULT '[]'
        )""",
        # --- Planning ---
        """CREATE TABLE IF NOT EXISTS planning_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            event_type  TEXT NOT NULL DEFAULT 'other',
            date_start  TEXT NOT NULL,
            date_end    TEXT NOT NULL,
            all_day     INTEGER NOT NULL DEFAULT 1,
            time_start  TEXT NULL,
            time_end    TEXT NULL,
            person      TEXT NOT NULL DEFAULT '',
            notes       TEXT NOT NULL DEFAULT '',
            task_id     INTEGER NULL,
            site        TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL
        )""",
        # --- Establishments (Lycée NDK, Collège SU, Collège NDE) ---
        # Each row carries a stable `code` (NDK/SU/NDE) that other modules
        # reference via their `site` column. `aliases` is a JSON array of
        # strings used to match free-form values (e.g. GLPI locations) onto
        # the right establishment when we extend to the Parc module later.
        """CREATE TABLE IF NOT EXISTS establishments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT NOT NULL UNIQUE,
            name        TEXT NOT NULL,
            color       TEXT NOT NULL DEFAULT '#3B82F6',
            logo_path   TEXT NOT NULL DEFAULT '',
            aliases     TEXT NOT NULL DEFAULT '[]',
            sort_order  INTEGER NOT NULL DEFAULT 0
        )""",
        # --- Email cache (offline Outlook-style) ---
        """CREATE TABLE IF NOT EXISTS emails_cache (
            id              TEXT PRIMARY KEY,
            thread_id       TEXT NOT NULL DEFAULT '',
            folder          TEXT NOT NULL DEFAULT 'inbox',
            sender          TEXT NOT NULL DEFAULT '',
            recipient       TEXT NOT NULL DEFAULT '',
            cc              TEXT NOT NULL DEFAULT '',
            subject         TEXT NOT NULL DEFAULT '',
            snippet         TEXT NOT NULL DEFAULT '',
            body_text       TEXT NOT NULL DEFAULT '',
            body_html       TEXT NOT NULL DEFAULT '',
            date_header     TEXT NOT NULL DEFAULT '',
            internal_date   TEXT NOT NULL DEFAULT '',
            is_unread       INTEGER NOT NULL DEFAULT 1,
            is_starred      INTEGER NOT NULL DEFAULT 0,
            labels          TEXT NOT NULL DEFAULT '[]',
            has_attachments INTEGER NOT NULL DEFAULT 0,
            attachment_names TEXT NOT NULL DEFAULT '[]',
            attachments_json TEXT NOT NULL DEFAULT '[]',
            fetched_full    INTEGER NOT NULL DEFAULT 0,
            synced_at       TEXT NOT NULL DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS email_sync_state (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )""",
        # --- Email FTS5 full-text search index ---
        """CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
            id UNINDEXED, subject, sender, snippet, body_text
        )""",
        # --- Local drafts ---
        """CREATE TABLE IF NOT EXISTS local_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL DEFAULT '',
            cc TEXT NOT NULL DEFAULT '',
            subject TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            reply_to_message_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        # --- Documents ---
        """CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            supplier_id INTEGER NULL,
            doc_date TEXT NULL,
            reference TEXT NOT NULL DEFAULT '',
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
        )""",
        """CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
        """CREATE TABLE IF NOT EXISTS document_tags (
            document_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (document_id, tag_id),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS document_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            link_type TEXT NOT NULL DEFAULT 'AUTRE',
            created_at TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (target_id) REFERENCES documents(id) ON DELETE CASCADE,
            UNIQUE(source_id, target_id)
        )""",
        # --- Changelog ---
        """CREATE TABLE IF NOT EXISTS changelog_entries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            category    TEXT NOT NULL DEFAULT '',
            impact      TEXT NOT NULL DEFAULT 'info',
            author      TEXT NOT NULL DEFAULT '',
            event_date  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            tags        TEXT NOT NULL DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS changelog_categories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            color_hex  TEXT NOT NULL DEFAULT '#64748B',
            icon_key   TEXT NOT NULL DEFAULT 'fa5s.clipboard-list',
            sort_order INTEGER NOT NULL DEFAULT 100
        )""",
        # --- Wiki ---
        """CREATE TABLE IF NOT EXISTS wiki_articles (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            category   TEXT NOT NULL DEFAULT '',
            content    TEXT NOT NULL DEFAULT '',
            tags       TEXT NOT NULL DEFAULT '',
            pinned     INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            source_path TEXT NOT NULL DEFAULT '',
            content_format TEXT NOT NULL DEFAULT 'html'
        )""",
        """CREATE TABLE IF NOT EXISTS wiki_categories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            color_hex  TEXT NOT NULL DEFAULT '#64748B',
            icon_key   TEXT NOT NULL DEFAULT 'fa5s.folder',
            sort_order INTEGER NOT NULL DEFAULT 100
        )""",
        # --- Suppliers ---
        """CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domain TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            contact TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            logo_path TEXT NOT NULL DEFAULT '',
            contacts_json TEXT NOT NULL DEFAULT '[]'
        )""",
        """CREATE TABLE IF NOT EXISTS supplier_domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color_hex TEXT NOT NULL DEFAULT '#AAB3C5',
            icon_key  TEXT NOT NULL DEFAULT 'fa5s.address-book',
            sort_order INTEGER NOT NULL DEFAULT 100,
            color TEXT NOT NULL DEFAULT '#AAB3C5',
            icon TEXT NOT NULL DEFAULT 'fa5s.address-book'
        )""",
        # --- Parc ---
        """CREATE TABLE IF NOT EXISTS parc_sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            city TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS parc_buildings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL REFERENCES parc_sites(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(site_id, name)
        )""",
        """CREATE TABLE IF NOT EXISTS parc_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL REFERENCES parc_buildings(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            floor TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE(building_id, name)
        )""",
        """CREATE TABLE IF NOT EXISTS parc_equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL DEFAULT '',
            equip_type TEXT NOT NULL DEFAULT 'PC',
            os TEXT NOT NULL DEFAULT '',
            serial_number TEXT NOT NULL DEFAULT '',
            brand TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            site_id INTEGER REFERENCES parc_sites(id) ON DELETE SET NULL,
            building_id INTEGER REFERENCES parc_buildings(id) ON DELETE SET NULL,
            room_id INTEGER REFERENCES parc_rooms(id) ON DELETE SET NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            source_ou TEXT NOT NULL DEFAULT '',
            ad_dn TEXT NOT NULL DEFAULT '',
            last_seen_ad TEXT,
            warranty_end TEXT,
            purchase_date TEXT,
            notes TEXT NOT NULL DEFAULT '',
            manual_location INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS parc_site_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            pattern TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 100,
            active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(site_id, pattern),
            FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
        )""",
        # --- Security (WithSecure) ---
        """CREATE TABLE IF NOT EXISTS ws_endpoints (
            hostname TEXT PRIMARY KEY,
            online INTEGER,
            os_name TEXT,
            profile TEXT,
            client_version TEXT,
            malware_protection TEXT,
            sw_updates_state TEXT,
            groups_text TEXT,
            tags_text TEXT,
            ip_addrs TEXT,
            uuid TEXT,
            enrolled_at TEXT,
            updated_at TEXT,
            last_imported_at TEXT NOT NULL,
            dns_address TEXT,
            wins_address TEXT,
            status_update_ts TEXT,
            ws_recent INTEGER,
            serial_number TEXT,
            state TEXT,
            protection_overview TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS ws_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_at TEXT NOT NULL,
            file_name TEXT NOT NULL,
            row_count INTEGER NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS ws_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )""",
        # --- AD ---
        """CREATE TABLE IF NOT EXISTS ad_computers (
            hostname TEXT NOT NULL,
            dnshostname TEXT,
            enabled INTEGER NOT NULL,
            source TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            last_logon_date TEXT,
            PRIMARY KEY (hostname, source)
        )""",
        """CREATE TABLE IF NOT EXISTS ad_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_at TEXT NOT NULL,
            source TEXT NOT NULL,
            file_name TEXT NOT NULL,
            row_count INTEGER NOT NULL
        )""",
        # --- Bastion ---
        """CREATE TABLE IF NOT EXISTS bastion_groups (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL UNIQUE,
            color_hex  TEXT    NOT NULL DEFAULT '#4B8BFF',
            sort_order INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS bastion_servers (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT    NOT NULL,
            hostname     TEXT    NOT NULL,
            port         INTEGER NOT NULL DEFAULT 22,
            username     TEXT    NOT NULL DEFAULT '',
            protocol     TEXT    NOT NULL DEFAULT 'SSH',
            group_name   TEXT    NOT NULL DEFAULT '',
            notes        TEXT    NOT NULL DEFAULT '',
            ssh_key_path TEXT    NOT NULL DEFAULT '',
            created_at   TEXT    NOT NULL DEFAULT '',
            updated_at   TEXT    NOT NULL DEFAULT ''
        )""",
        # --- Misc (sites, buildings, rooms for old parc) ---
        """CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )""",
        """CREATE TABLE IF NOT EXISTS buildings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(site_id, name),
            FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            floor TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            UNIQUE(building_id, floor, name),
            FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS machines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL UNIQUE,
            scope TEXT NOT NULL DEFAULT 'ADMIN',
            site_id INTEGER NULL,
            building_id INTEGER NULL,
            room_id INTEGER NULL,
            location_source TEXT NOT NULL DEFAULT 'UNKNOWN',
            status TEXT NOT NULL DEFAULT 'ACTIF',
            device_type TEXT NOT NULL DEFAULT 'FIXE',
            os TEXT NOT NULL DEFAULT '',
            primary_user TEXT NOT NULL DEFAULT '',
            purchase_date TEXT NULL,
            warranty_end TEXT NULL,
            last_seen_ad TEXT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL,
            FOREIGN KEY (building_id) REFERENCES buildings(id) ON DELETE SET NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE SET NULL
        )""",
        """CREATE TABLE IF NOT EXISTS machine_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id INTEGER NOT NULL,
            at TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE CASCADE
        )""",
        # --- Quick Links / Launcher ---
        """CREATE TABLE IF NOT EXISTS quick_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            icon_type TEXT NOT NULL DEFAULT 'emoji',
            icon_value TEXT NOT NULL DEFAULT '🔗',
            color TEXT NOT NULL DEFAULT '#6C63FF',
            favorite INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 100,
            created_at TEXT NOT NULL
        )""",
    ]

    for stmt in statements:
        await db.execute(stmt)
    await db.commit()

    # --- Migrations for existing databases ---
    await _run_migrations(db)
    await db.commit()

    # --- Insert default data if tables are empty ---
    await _seed_defaults(db)

    await db.commit()
    await db.close()


async def _run_migrations(db):
    """Apply schema migrations for existing databases."""
    # Check if content_format column exists in wiki_articles
    cursor = await db.execute("PRAGMA table_info(wiki_articles)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "content_format" not in columns:
        await db.execute(
            "ALTER TABLE wiki_articles ADD COLUMN content_format TEXT NOT NULL DEFAULT 'html'"
        )

    # GLPI integration columns on parc_equipment
    cursor = await db.execute("PRAGMA table_info(parc_equipment)")
    parc_cols = [row[1] for row in await cursor.fetchall()]
    if "glpi_id" not in parc_cols:
        await db.execute("ALTER TABLE parc_equipment ADD COLUMN glpi_id INTEGER")
    if "glpi_location" not in parc_cols:
        await db.execute(
            "ALTER TABLE parc_equipment ADD COLUMN glpi_location TEXT NOT NULL DEFAULT ''"
        )
    if "last_user" not in parc_cols:
        await db.execute(
            "ALTER TABLE parc_equipment ADD COLUMN last_user TEXT NOT NULL DEFAULT ''"
        )

    # Project budget columns
    try:
        cursor = await db.execute("PRAGMA table_info(projects)")
        proj_cols = [row[1] for row in await cursor.fetchall()]
        if "budget" not in proj_cols:
            await db.execute("ALTER TABLE projects ADD COLUMN budget REAL NOT NULL DEFAULT 0")
            await db.execute("ALTER TABLE projects ADD COLUMN budget_spent REAL NOT NULL DEFAULT 0")
            await db.commit()
    except Exception as e:
        # Schema may have already been migrated by a sibling process — log so we can spot
        # real failures (no permissions, locked DB) instead of swallowing silently.
        import logging
        logging.getLogger(__name__).warning(f"projects budget migration skipped: {e}")

    # Project document amount columns
    try:
        cursor = await db.execute("PRAGMA table_info(project_documents)")
        pd_cols = [row[1] for row in await cursor.fetchall()]
        if "amount" not in pd_cols:
            await db.execute("ALTER TABLE project_documents ADD COLUMN amount REAL NOT NULL DEFAULT 0")
            await db.execute("ALTER TABLE project_documents ADD COLUMN amount_accepted REAL NOT NULL DEFAULT 0")
            await db.execute("ALTER TABLE project_documents ADD COLUMN status TEXT NOT NULL DEFAULT ''")
            await db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"project_documents amount migration skipped: {e}")

    # Project link on tasks + start_date for Gantt
    cursor = await db.execute("PRAGMA table_info(tasks)")
    task_cols = [row[1] for row in await cursor.fetchall()]
    if "project_id" not in task_cols:
        await db.execute("ALTER TABLE tasks ADD COLUMN project_id INTEGER")
        await db.commit()
    if "start_date" not in task_cols:
        await db.execute("ALTER TABLE tasks ADD COLUMN start_date TEXT")
        await db.commit()
    if "is_milestone" not in task_cols:
        await db.execute("ALTER TABLE tasks ADD COLUMN is_milestone INTEGER NOT NULL DEFAULT 0")
        await db.commit()

    # is_acompte flag on documents — marks a Facture as a partial / down-payment invoice.
    # Users want to visually distinguish acomptes from final invoices on the list.
    try:
        cursor = await db.execute("PRAGMA table_info(documents)")
        doc_cols = [row[1] for row in await cursor.fetchall()]
        if "is_acompte" not in doc_cols:
            await db.execute("ALTER TABLE documents ADD COLUMN is_acompte INTEGER NOT NULL DEFAULT 0")
            await db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"documents.is_acompte migration skipped: {e}")

    # Internal reference on documents — every doc gets a stable, auto-generated
    # identifier (DEV-2026-001, FAC-2026-042, ...) independent from any external
    # reference printed on the supplier's PDF. Migration: assign refs to existing
    # rows in chronological order so users see meaningful values right away.
    try:
        cursor = await db.execute("PRAGMA table_info(documents)")
        doc_cols = [row[1] for row in await cursor.fetchall()]
        if "internal_ref" not in doc_cols:
            await db.execute("ALTER TABLE documents ADD COLUMN internal_ref TEXT NOT NULL DEFAULT ''")
            await db.commit()

            # Backfill: compute (type, year) sequence for every existing row
            type_prefix_map = {
                "DEVIS": "DEV", "FACTURE": "FAC", "BPA": "BPA", "BON": "BPA",
                "CONTRAT": "CTR", "RAPPORT": "RAP", "AUTRE": "AUT",
            }
            rows = await db.execute_fetchall(
                "SELECT id, COALESCE(doc_type, 'AUTRE'), COALESCE(doc_date, ''), COALESCE(created_at, '') "
                "FROM documents WHERE internal_ref = '' ORDER BY COALESCE(doc_date, created_at) ASC, id ASC"
            )
            seq_counter = {}  # (prefix, year) -> next n
            for row in rows:
                doc_id, doc_type, doc_date, created_at = row
                prefix = type_prefix_map.get((doc_type or "AUTRE").upper(), "AUT")
                # Year source: doc_date > created_at > today
                year_str = (doc_date or created_at or "")[:4]
                year = year_str if year_str.isdigit() and len(year_str) == 4 else str(datetime.now().year)
                key = (prefix, year)
                seq = seq_counter.get(key, 0) + 1
                seq_counter[key] = seq
                ref = f"{prefix}-{year}-{seq:03d}"
                await db.execute("UPDATE documents SET internal_ref = ? WHERE id = ?", (ref, doc_id))
            await db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"documents.internal_ref migration failed: {e}")

    # Additional supplier contacts (multiple named contacts per supplier)
    try:
        cursor = await db.execute("PRAGMA table_info(suppliers)")
        sup_cols = [row[1] for row in await cursor.fetchall()]
        if "contacts_json" not in sup_cols:
            await db.execute("ALTER TABLE suppliers ADD COLUMN contacts_json TEXT NOT NULL DEFAULT '[]'")
            await db.commit()
    except Exception:
        pass

    # Task dependencies table (may not exist on pre-v6.4 databases)
    try:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS task_dependencies (
                task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                depends_on_task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                PRIMARY KEY (task_id, depends_on_task_id),
                CHECK (task_id != depends_on_task_id)
            )"""
        )
        await db.commit()
    except Exception:
        pass

    # Google Calendar sync columns on planning_events
    cursor = await db.execute("PRAGMA table_info(planning_events)")
    planning_cols = [row[1] for row in await cursor.fetchall()]
    if "google_event_id" not in planning_cols:
        await db.execute(
            "ALTER TABLE planning_events ADD COLUMN google_event_id TEXT"
        )
    if "google_updated_at" not in planning_cols:
        await db.execute(
            "ALTER TABLE planning_events ADD COLUMN google_updated_at TEXT"
        )

    # Gmail cache: cc column was added later. Older databases created before
    # the column existed never got it (CREATE TABLE IF NOT EXISTS doesn't
    # patch existing tables). Add it here so the "Cc" field shows up in the
    # mail viewer and "Reply all" can pre-fill the CC line correctly.
    # After adding the column, force re-fetch of any message that doesn't
    # have CC yet by flipping fetched_full back to 0 — the next time the user
    # opens such a message, get_message_local() will re-download it from
    # Gmail with the full header parsing that captures CC.
    try:
        cursor = await db.execute("PRAGMA table_info(emails_cache)")
        email_cols = [row[1] for row in await cursor.fetchall()]
        if "cc" not in email_cols:
            await db.execute("ALTER TABLE emails_cache ADD COLUMN cc TEXT NOT NULL DEFAULT ''")
            # Brand new column — every cached row needs re-fetching to get CC.
            await db.execute("UPDATE emails_cache SET fetched_full = 0")
            await db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"emails_cache.cc migration skipped: {e}")

    # Site (establishment) column on projects + planning_events. The Tasks
    # module already has `site` since v6.x; we extend the same idea to
    # projects and planning so each entity can carry the NDK/SU/NDE code
    # and the frontend renders the establishment's logo accordingly.
    try:
        cursor = await db.execute("PRAGMA table_info(projects)")
        proj_cols = [row[1] for row in await cursor.fetchall()]
        if "site" not in proj_cols:
            await db.execute("ALTER TABLE projects ADD COLUMN site TEXT NOT NULL DEFAULT ''")
            await db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"projects.site migration skipped: {e}")

    try:
        cursor = await db.execute("PRAGMA table_info(planning_events)")
        plan_cols = [row[1] for row in await cursor.fetchall()]
        if "site" not in plan_cols:
            await db.execute("ALTER TABLE planning_events ADD COLUMN site TEXT NOT NULL DEFAULT ''")
            await db.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"planning_events.site migration skipped: {e}")


async def _seed_defaults(db):
    """Insert default data into empty tables (first launch only)."""

    # Default task categories
    row = await db.execute("SELECT COUNT(*) FROM task_categories")
    count = (await row.fetchone())[0]
    if count == 0:
        categories = [
            "Administration", "Réseau", "Pédagogique",
            "Sécurité", "Serveurs", "Maintenance", "Support",
        ]
        for i, name in enumerate(categories):
            await db.execute(
                "INSERT INTO task_categories (name, sort_order) VALUES (?, ?)",
                (name, 100),
            )

    # Default changelog categories
    row = await db.execute("SELECT COUNT(*) FROM changelog_categories")
    count = (await row.fetchone())[0]
    if count == 0:
        cl_cats = [
            ("Réseau", "#3B82F6", 10),
            ("Serveur", "#8B5CF6", 20),
            ("Sécurité", "#EF4444", 30),
            ("Application", "#22C55E", 40),
            ("Infrastructure", "#F59E0B", 50),
            ("Poste", "#EC4899", 60),
            ("Active Directory", "#06A6C9", 70),
            ("Messagerie", "#F97316", 80),
        ]
        for name, color, order in cl_cats:
            await db.execute(
                "INSERT INTO changelog_categories (name, color_hex, icon_key, sort_order) VALUES (?, ?, '', ?)",
                (name, color, order),
            )

    # Default supplier domains
    row = await db.execute("SELECT COUNT(*) FROM supplier_domains")
    count = (await row.fetchone())[0]
    if count == 0:
        domains = [
            ("Réseau",        "#2D6CDF", "fa5s.network-wired",  10),
            ("Wi-Fi",         "#FF55FF", "fa5s.wifi",           20),
            ("Fibre/Internet","#55007F", "fa5s.project-diagram",30),
            ("Téléphonie",    "#00FF00", "fa5s.phone",          40),
            ("Imprimantes",   "#AA5500", "fa5s.print",          50),
            ("Sécurité",      "#EF4444", "fa5s.shield-alt",     60),
            ("Support",       "#FF5500", "fa5s.tools",          70),
            ("Logiciels",     "#22C55E", "fa5s.puzzle-piece",   80),
            ("Matériel",      "#AAB3C5", "fa5s.toolbox",        90),
        ]
        for name, color, icon, order in domains:
            await db.execute(
                "INSERT INTO supplier_domains (name, color_hex, icon_key, sort_order, color, icon) VALUES (?, ?, ?, ?, ?, ?)",
                (name, color, icon, order, color, icon),
            )

    # Default establishments (3 schools managed by this IT department).
    # User uploads logos via Settings → Établissements. Colors are tweakable
    # too — these are reasonable defaults to start with.
    row = await db.execute("SELECT COUNT(*) FROM establishments")
    count = (await row.fetchone())[0]
    if count == 0:
        establishments = [
            ("NDK", "Lycée Notre Dame du Kreisker", "#3B82F6", 10),
            ("SU",  "Collège Sainte Ursule",         "#22C55E", 20),
            ("NDE", "Collège Notre Dame d'Espérance", "#F59E0B", 30),
        ]
        for code, name, color, order in establishments:
            await db.execute(
                "INSERT INTO establishments (code, name, color, logo_path, aliases, sort_order) VALUES (?, ?, ?, '', '[]', ?)",
                (code, name, color, order),
            )
