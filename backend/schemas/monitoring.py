"""Pydantic models for Zabbix monitoring module."""
from __future__ import annotations

from pydantic import BaseModel


class MonitoringConfig(BaseModel):
    url: str
    api_token: str = ""
    username: str = ""
    password: str = ""


class MonitoringConfigResponse(BaseModel):
    configured: bool = False
    url: str = ""
    api_token: str = ""
    auth_mode: str = "token"
    username: str = ""


class MonitoringHost(BaseModel):
    id: str = ""
    name: str = ""
    host: str = ""
    status: str = ""
    available: str = ""
    groups: list[str] = []
    ip: str = ""
    description: str = ""
    last_problem: str = ""


class MonitoringProblem(BaseModel):
    id: str = ""
    host: str = ""
    severity: str = ""
    name: str = ""
    timestamp: str = ""
    acknowledged: bool = False


class MonitoringStats(BaseModel):
    total_hosts: int = 0
    available: int = 0
    unavailable: int = 0
    unknown: int = 0
    active_problems: int = 0
    synced_at: str | None = None


class SyncResponse(BaseModel):
    total_hosts: int = 0
    total_problems: int = 0
    synced_at: str = ""
