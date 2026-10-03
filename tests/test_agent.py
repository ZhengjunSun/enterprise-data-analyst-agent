import sqlite3
import tempfile
import unittest
from pathlib import Path

from data_analyst_agent import AnalystAgent, ReadOnlyDatabase, RulePlanner, SqlPolicy


class AnalystTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "test.db"
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE purchases(month TEXT, crude TEXT, volume REAL, cost REAL)")
            db.executemany("INSERT INTO purchases VALUES(?,?,?,?)", [("2026-01", "A", 10, 60), ("2026-02", "A", 20, 62)])
        self.database = ReadOnlyDatabase(str(self.path), SqlPolicy({"purchases"}, max_rows=10))

    def tearDown(self):
        self.temp.cleanup()

    def test_average_analysis(self):
        result = AnalystAgent(self.database, RulePlanner()).answer("average cost")
        self.assertEqual(result.columns, ("crude", "average_cost"))
        self.assertIsNotNone(result.chart)

    def test_write_query_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.database.query("DELETE FROM purchases")

    def test_unknown_table_is_rejected(self):
        with self.assertRaises(PermissionError):
            self.database.query("SELECT * FROM secrets")


if __name__ == "__main__":
    unittest.main()
