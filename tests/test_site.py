import gzip
import io
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

    def test_sitemap_gzip_metadata_does_not_make_site_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            fresh, tracked = Path(temp) / "fresh", Path(temp) / "tracked"
            payload = b"<urlset><url>https://example.org/</url></urlset>"
            for root, mtime, filename in ((fresh, 0, "sitemap.xml"), (tracked, 123, "old.xml")):
                root.mkdir()
                data = io.BytesIO()
                with gzip.GzipFile(filename=filename, mode="wb", fileobj=data, mtime=mtime) as archive:
                    archive.write(payload)
                (root / "sitemap.xml.gz").write_bytes(data.getvalue())
            self.assertNotEqual(
                (fresh / "sitemap.xml.gz").read_bytes(), (tracked / "sitemap.xml.gz").read_bytes()
            )
            self.assertEqual(compare_directories(fresh, tracked), [])

    def test_changed_sitemap_payload_is_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            fresh, tracked = Path(temp) / "fresh", Path(temp) / "tracked"
            for root, payload in ((fresh, b"<urlset/>"), (tracked, b"<urlset><url/></urlset>")):
                root.mkdir()
                (root / "sitemap.xml.gz").write_bytes(gzip.compress(payload, mtime=0))
            self.assertEqual(compare_directories(fresh, tracked), ["different: sitemap.xml.gz"])

    def test_identical_corrupt_sitemap_archives_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fresh, tracked = Path(temp) / "fresh", Path(temp) / "tracked"
            for root in (fresh, tracked):
                root.mkdir()
                (root / "sitemap.xml.gz").write_bytes(gzip.compress(b"<urlset/>", mtime=0)[:-4])
            self.assertEqual(compare_directories(fresh, tracked), ["different: sitemap.xml.gz"])

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
