"""Quick search to list ALL databases the integration can see."""

from __future__ import annotations
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from notion_client import AsyncClient

load_dotenv(Path(__file__).parent / ".env")

async def main() -> None:
    client = AsyncClient(auth=os.getenv("NOTION_TOKEN", ""))

    print("Searching for ALL databases accessible to the integration...\n")
    response = await client.search(query="")

    results = response.get("results", [])
    if not results:
        print("❌ No databases found. The integration has no access to any database.")
        print()
        print("Fix: Open your Notion database → click '...' → 'Connections' → add 'infoRoutine'")
        return

    print(f"Found {len(results)} database(s):\n")
    for db in results:
        title_parts = db.get("title", [])
        title = "".join(t.get("plain_text", "") for t in title_parts) or "(untitled)"
        db_id = db["id"]
        print(f"  📁 '{title}'")
        print(f"     ID: {db_id}")
        props = db.get("properties", {})
        print(f"     Properties: {', '.join(props.keys())}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
