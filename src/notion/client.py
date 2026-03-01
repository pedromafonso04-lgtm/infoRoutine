from __future__ import annotations

import json
import logging
from pathlib import Path

from notion_client import AsyncClient

logger = logging.getLogger(__name__)

STATE_FILE = Path(".notion_state.json")


class NotionManager:
    def __init__(self, token: str, target_database_id: str | None = None) -> None:
        self._client = AsyncClient(auth=token)
        self._database_id: str | None = target_database_id
        if not self._database_id:
            self._load_state()

    def _load_state(self) -> None:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text())
            self._database_id = data.get("database_id")
            logger.info("Loaded Notion state: database=%s", self._database_id)

    def _save_state(self) -> None:
        STATE_FILE.write_text(json.dumps({"database_id": self._database_id}, indent=2))

    @property
    def is_configured(self) -> bool:
        return bool(self._database_id)

    @property
    def database_id(self) -> str | None:
        return self._database_id

    async def find_database(self) -> str | None:
        """Search for the existing 'Newsletter diária' database in the workspace."""
        try:
            response = await self._client.search(
                query="Newsletter diária"
            )
            for result in response.get("results", []):
                if result.get("object") != "database":
                    continue
                title_parts = result.get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_parts)
                if "newsletter" in title.lower() and "diária" in title.lower():
                    self._database_id = result["id"]
                    self._save_state()
                    logger.info("✅ Found database '%s': %s", title, self._database_id)
                    return self._database_id

            # Enforce exact match to prevent writing to the wrong database
            logger.error("❌ Could not find an exact match for 'Newsletter diária'. Please ensure the database exists and has been shared with the integration.")
            return None

        except Exception as e:
            logger.error("❌ Failed to search for database: %s", e)

        return None

    @property
    def client(self) -> AsyncClient:
        return self._client
