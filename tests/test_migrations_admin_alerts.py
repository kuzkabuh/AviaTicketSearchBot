import sqlite3
from pathlib import Path
import tempfile
import unittest

from scripts.run_migrations import apply_migrations
from services.admin_alerts_service import AdminAlertsService, ensure_admin_alerts_schema


class MigrationRunnerTest(unittest.TestCase):
    def test_repeated_migrations_do_not_duplicate_subscription_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "bot.sqlite3"
            migrations_dir = Path("migrations")
            apply_migrations(db_path, migrations_dir, log=lambda _: None)
            apply_migrations(db_path, migrations_dir, log=lambda _: None)
            with sqlite3.connect(db_path) as connection:
                columns = [row[1] for row in connection.execute("PRAGMA table_info(subscriptions)")]
                self.assertEqual(columns.count("notification_mode"), 1)
                self.assertEqual(columns.count("target_price"), 1)

    def test_partial_003_schema_is_recovered_as_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "bot.sqlite3"
            migrations_dir = Path("migrations")
            with sqlite3.connect(db_path) as connection:
                connection.execute("CREATE TABLE subscriptions (id INTEGER PRIMARY KEY, notification_mode TEXT NOT NULL DEFAULT 'any_change')")
            apply_migrations(db_path, migrations_dir, log=lambda _: None)
            with sqlite3.connect(db_path) as connection:
                row = connection.execute("SELECT note FROM schema_migrations WHERE name = '003_subscription_notification_mode.sql'").fetchone()
                self.assertIsNotNone(row)
                self.assertIn("schema already exists", row[0])


class AdminAlertsTest(unittest.TestCase):
    def test_alert_dedup_and_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "alerts.sqlite3")
            service = AdminAlertsService(database_path=db_path)
            self.assertTrue(service.should_send("api_error", "aviasales", 60))
            service.record("api_error", "aviasales", {"status": 429})
            self.assertFalse(service.should_send("api_error", "aviasales", 60))
            service.resolve("api_error", "aviasales")
            self.assertTrue(service.should_send("api_error", "aviasales", 60))
            with sqlite3.connect(db_path) as connection:
                ensure_admin_alerts_schema(connection)
                self.assertGreaterEqual(connection.execute("SELECT COUNT(*) FROM admin_alerts_history").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
