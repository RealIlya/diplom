import tempfile
import unittest
from pathlib import Path

from scripts.check_site import compare_directories


class SiteSyncTests(unittest.TestCase):
    def test_detects_missing_page_and_changed_search_index(self):
        with tempfile.TemporaryDirectory() as temp:
            expected = Path(temp) / "fresh"
            tracked = Path(temp) / "tracked"
            for root in (expected, tracked):
                (root / "search").mkdir(parents=True)
                (root / "search/search_index.json").write_text('{"docs":[]}', encoding="utf-8")
            (expected / "architecture").mkdir()
            (expected / "architecture/index.html").write_text("new architecture", encoding="utf-8")
            (tracked / "search/search_index.json").write_text('{"docs":[1]}', encoding="utf-8")

            differences = compare_directories(expected, tracked)

            self.assertIn("missing: architecture/index.html", differences)
            self.assertIn("different: search/search_index.json", differences)

    def test_identical_tree_is_current(self):
        with tempfile.TemporaryDirectory() as temp:
            expected = Path(temp) / "fresh"
            tracked = Path(temp) / "tracked"
            for root in (expected, tracked):
                root.mkdir()
                (root / "index.html").write_text("same", encoding="utf-8")
            self.assertEqual(compare_directories(expected, tracked), [])


if __name__ == "__main__":
    unittest.main()
