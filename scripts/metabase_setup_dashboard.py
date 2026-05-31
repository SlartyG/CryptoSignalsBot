#!/usr/bin/env python3
"""
Create CryptoSignalsBot analytics dashboard in Metabase via API.

Prerequisites:
  - Metabase is running (docker compose --profile analytics up -d metabase)
  - First-time setup completed in browser OR METABASE_EMAIL/PASSWORD set
  - analytics views loaded: docs/sql/analytics_views.sql

Usage (on VPS, from project root):
  docker compose exec bot python scripts/metabase_setup_dashboard.py

Env:
  METABASE_URL          default http://metabase:3000 (inside Docker network)
  METABASE_EMAIL        admin email from Metabase setup
  METABASE_PASSWORD     admin password
  METABASE_DB_HOST      default postgres
  METABASE_DB_NAME      default cryptobot
  METABASE_DB_USER      default app
  METABASE_DB_PASSWORD  default from POSTGRES_PASSWORD or app
"""

from __future__ import annotations

import os
import sys
import time

import httpx

DASHBOARD_NAME = "CryptoSignalsBot Analytics"
DB_DISPLAY_NAME = "CryptoSignalsBot"

CARDS = [
    {
        "name": "Active paid subscribers",
        "display": "scalar",
        "sql": "SELECT active_paid FROM v_active_subscribers",
        "row": 0,
        "col": 0,
        "size_x": 6,
        "size_y": 3,
    },
    {
        "name": "MRR (USDT, 30d)",
        "display": "scalar",
        "sql": "SELECT round(mrr_usdt::numeric, 2) FROM v_mrr_usdt",
        "row": 0,
        "col": 6,
        "size_x": 6,
        "size_y": 3,
    },
    {
        "name": "Total users",
        "display": "scalar",
        "sql": "SELECT count(*) FROM users WHERE banned = false",
        "row": 0,
        "col": 12,
        "size_x": 6,
        "size_y": 3,
    },
    {
        "name": "Signals (7 days)",
        "display": "scalar",
        "sql": "SELECT count(*) FROM signals_log WHERE created_at >= now() - interval '7 days'",
        "row": 0,
        "col": 18,
        "size_x": 6,
        "size_y": 3,
    },
    {
        "name": "Free vs Paid users",
        "display": "pie",
        "sql": """
SELECT 'Paid' AS tier, paid_users AS users FROM v_users_by_tier
UNION ALL
SELECT 'Free', free_users FROM v_users_by_tier
""".strip(),
        "row": 3,
        "col": 0,
        "size_x": 8,
        "size_y": 6,
    },
    {
        "name": "Signals by type (30d)",
        "display": "bar",
        "sql": """
SELECT type, sum(cnt) AS total
FROM v_signals_daily
WHERE day >= now() - interval '30 days'
GROUP BY 1
ORDER BY 2 DESC
""".strip(),
        "row": 3,
        "col": 8,
        "size_x": 8,
        "size_y": 6,
    },
    {
        "name": "Signals per day (30d)",
        "display": "line",
        "sql": """
SELECT day::date AS day, sum(cnt) AS signals
FROM v_signals_daily
WHERE day >= now() - interval '30 days'
GROUP BY 1
ORDER BY 1
""".strip(),
        "row": 3,
        "col": 16,
        "size_x": 8,
        "size_y": 6,
    },
    {
        "name": "Collector uptime (7d)",
        "display": "line",
        "sql": """
SELECT hour, collector_name, uptime_pct
FROM v_collector_uptime
ORDER BY hour, collector_name
""".strip(),
        "row": 9,
        "col": 0,
        "size_x": 12,
        "size_y": 6,
    },
    {
        "name": "Delivery latency by priority (7d)",
        "display": "bar",
        "sql": """
SELECT
  CASE priority WHEN 1 THEN 'Paid' WHEN 2 THEN 'Free' ELSE 'Other' END AS tier,
  round(avg_delay_sec::numeric, 1) AS avg_delay_sec,
  deliveries
FROM v_delivery_latency_by_priority
ORDER BY priority
""".strip(),
        "row": 9,
        "col": 12,
        "size_x": 12,
        "size_y": 6,
    },
    {
        "name": "Registration → payment cohorts",
        "display": "table",
        "sql": """
SELECT
  cohort_week::date AS week,
  registered,
  converted,
  round(100.0 * converted / nullif(registered, 0), 1) AS conversion_pct
FROM v_conversion_cohorts
ORDER BY cohort_week DESC
LIMIT 52
""".strip(),
        "row": 15,
        "col": 0,
        "size_x": 24,
        "size_y": 6,
    },
    {
        "name": "Recent signals",
        "display": "table",
        "sql": """
SELECT created_at, symbol, type, confidence
FROM signals_log
ORDER BY created_at DESC
LIMIT 50
""".strip(),
        "row": 21,
        "col": 0,
        "size_x": 24,
        "size_y": 6,
    },
]


class MetabaseClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = httpx.Client(base_url=self.base_url, timeout=60.0)
        self.token: str | None = None

    def close(self) -> None:
        self.session.close()

    @property
    def headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"X-Metabase-Session": self.token}

    def wait_until_ready(self, attempts: int = 30) -> None:
        for i in range(attempts):
            try:
                resp = self.session.get("/api/health")
                if resp.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(2)
        raise RuntimeError(f"Metabase not ready at {self.base_url}")

    def ensure_setup_done(self) -> None:
        resp = self.session.get("/api/session/properties")
        resp.raise_for_status()
        props = resp.json()
        if not props.get("has-user-setup"):
            raise RuntimeError(
                "Metabase first-time setup not completed. "
                "Open Metabase in browser, create admin account, then re-run this script."
            )

    def login(self, email: str, password: str) -> None:
        resp = self.session.post(
            "/api/session",
            json={"username": email, "password": password},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Metabase login failed: {resp.status_code} {resp.text}")
        self.token = resp.json()["id"]

    def list_databases(self) -> list[dict]:
        resp = self.session.get("/api/database", headers=self.headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", data) if isinstance(data, dict) else data

    def find_database(self, name: str) -> dict | None:
        for db in self.list_databases():
            if db.get("name") == name:
                return db
        return None

    def create_database(self, details: dict) -> dict:
        payload = {
            "name": DB_DISPLAY_NAME,
            "engine": "postgres",
            "details": details,
            "auto_run_queries": True,
            "is_full_sync": True,
            "schedules": {},
        }
        resp = self.session.post("/api/database", json=payload, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def sync_database(self, db_id: int) -> None:
        resp = self.session.post(f"/api/database/{db_id}/sync_schema", headers=self.headers)
        resp.raise_for_status()

    def list_cards(self) -> list[dict]:
        resp = self.session.get("/api/card", headers=self.headers)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data", [])

    def find_card(self, name: str) -> dict | None:
        for card in self.list_cards():
            if card.get("name") == name:
                return card
        return None

    def create_card(self, db_id: int, spec: dict) -> dict:
        payload = {
            "name": spec["name"],
            "display": spec["display"],
            "dataset_query": {
                "type": "native",
                "native": {"query": spec["sql"]},
                "database": db_id,
            },
            "visualization_settings": spec.get("visualization_settings", {}),
        }
        resp = self.session.post("/api/card", json=payload, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def list_dashboards(self) -> list[dict]:
        resp = self.session.get("/api/dashboard", headers=self.headers)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data", [])

    def find_dashboard(self, name: str) -> dict | None:
        for dash in self.list_dashboards():
            if dash.get("name") == name:
                return dash
        return None

    def create_dashboard(self, name: str, description: str) -> dict:
        resp = self.session.post(
            "/api/dashboard",
            json={"name": name, "description": description},
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()

    def update_dashboard_cards(self, dashboard_id: int, dashcards: list[dict]) -> dict:
        resp = self.session.put(
            f"/api/dashboard/{dashboard_id}",
            json={
                "name": DASHBOARD_NAME,
                "description": "Auto-generated analytics for CryptoSignalsBot",
                "dashcards": dashcards,
            },
            headers=self.headers,
        )
        resp.raise_for_status()
        return resp.json()


def main() -> int:
    base_url = os.getenv("METABASE_URL", "http://metabase:3000")
    email = os.getenv("METABASE_EMAIL", "").strip()
    password = os.getenv("METABASE_PASSWORD", "").strip()
    db_host = os.getenv("METABASE_DB_HOST", "postgres")
    db_name = os.getenv("METABASE_DB_NAME", "cryptobot")
    db_user = os.getenv("METABASE_DB_USER", "app")
    db_password = os.getenv("METABASE_DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", "app"))

    if not email or not password:
        print(
            "Set METABASE_EMAIL and METABASE_PASSWORD in .env "
            "(admin credentials from Metabase first-time setup).",
            file=sys.stderr,
        )
        return 1

    client = MetabaseClient(base_url)
    try:
        print(f"Connecting to Metabase at {base_url}...")
        client.wait_until_ready()
        client.ensure_setup_done()
        client.login(email, password)

        db = client.find_database(DB_DISPLAY_NAME)
        if db:
            db_id = db["id"]
            print(f"Database '{DB_DISPLAY_NAME}' already exists (id={db_id})")
        else:
            print(f"Creating database '{DB_DISPLAY_NAME}'...")
            db = client.create_database(
                {
                    "host": db_host,
                    "port": 5432,
                    "dbname": db_name,
                    "user": db_user,
                    "password": db_password,
                    "ssl": False,
                }
            )
            db_id = db["id"]
            print(f"Database created (id={db_id})")

        print("Syncing schema...")
        client.sync_database(db_id)
        time.sleep(3)

        card_ids: list[tuple[dict, int]] = []
        for spec in CARDS:
            existing = client.find_card(spec["name"])
            if existing:
                card_id = existing["id"]
                print(f"  Card exists: {spec['name']} (id={card_id})")
            else:
                card = client.create_card(db_id, spec)
                card_id = card["id"]
                print(f"  Card created: {spec['name']} (id={card_id})")
            card_ids.append((spec, card_id))

        dash = client.find_dashboard(DASHBOARD_NAME)
        if dash:
            dashboard_id = dash["id"]
            print(f"Dashboard exists (id={dashboard_id}), updating layout...")
        else:
            dash = client.create_dashboard(
                DASHBOARD_NAME,
                "Signals, users, subscriptions, collectors and delivery metrics.",
            )
            dashboard_id = dash["id"]
            print(f"Dashboard created (id={dashboard_id})")

        dashcards = []
        for idx, (spec, card_id) in enumerate(card_ids):
            dashcards.append(
                {
                    "id": -(idx + 1),
                    "card_id": card_id,
                    "row": spec["row"],
                    "col": spec["col"],
                    "size_x": spec["size_x"],
                    "size_y": spec["size_y"],
                    "parameter_mappings": [],
                    "visualization_settings": {},
                }
            )

        client.update_dashboard_cards(dashboard_id, dashcards)
        print(f"\nDone. Open Metabase → Dashboards → '{DASHBOARD_NAME}'")
        print(f"Direct link: {base_url}/dashboard/{dashboard_id}")
        return 0
    except httpx.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
