from __future__ import annotations

import sqlite3
from collections.abc import Generator

from fastapi import Depends

from app.config import database_path
from app.services.campaigns import CampaignService
from app.storage.db import connect


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = connect(database_path())
    try:
        yield conn
    finally:
        conn.close()


def get_campaign_service(
    conn: sqlite3.Connection = Depends(get_db),
) -> CampaignService:
    return CampaignService(conn)
