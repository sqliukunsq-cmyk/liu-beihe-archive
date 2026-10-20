"""Keep active-ledger essays across legacy sync, cleanup and re-publication."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch


class PublicLedgerTest(unittest.TestCase):
    def prepare(self, root):
        (root / "scripts").mkdir()
        source_root = Path(__file__).resolve().parents[1]
        for name in ("sync_notion_to_github.py", "cleanup_research_archive.py"):
            shutil.copyfile(source_root / "scripts" / name, root / "scripts" / name)
        (root / "research" / "sources").mkdir(parents=True)
        self.page_id = "01234567-89ab-cdef-0123-456789abcdef"
        self.entry = {
            "title": "Test essay", "english_title": "Test essay", "category": "Core Theory",
            "keywords": ["Authorship"], "date": "2026-10-20", "slug": "test-essay",
            "status": "Ready", "last_edited_time": "2026-10-20T00:00:00Z",
            "source_path": "research/sources/test.md", "min_body_cjk": 8,
            "notion_url": f"https://app.notion.com/p/{self.page_id.replace('-', '')}",
        }
        (root / self.entry["source_path"]).write_text("## 正文\n\n这是一篇用于验证的研究文章。\n\n## 参考文献\n来源", "utf-8")
        self.write_manifest(root, self.entry)
        (root / "research" / "_notion_state.json").write_text('{"pages":{}}')

    def write_manifest(self, root, entry):
        (root / "research" / "_public_ledger.json").write_text(
            json.dumps({"version": 1, "pages": {self.page_id: entry}}))

    def run_publisher(self, root, ledger_only=False):
        class Response:
            status_code = 200
            text = ""

            def json(self):
                return {"results": [], "has_more": False}

        calls = []

        def request(*args, **kwargs):
            calls.append(args)
            return Response()

        with patch.dict(os.environ, {"NOTION_API_KEY": "test-only",
                                    "PUBLIC_LEDGER_ONLY": "1" if ledger_only else "0"}), \
             patch.dict("sys.modules", {
                 "requests": types.SimpleNamespace(request=request),
                 "markdown": types.SimpleNamespace(markdown=lambda body, **_: body)}), \
             redirect_stdout(io.StringIO()) as log:
            runpy.run_path(str(root / "scripts" / "sync_notion_to_github.py"))
            runpy.run_path(str(root / "scripts" / "cleanup_research_archive.py"))
        return calls, log.getvalue()

    def test_immediate_then_scheduled_sync_then_revision_and_retraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            calls, _ = self.run_publisher(root, ledger_only=True)
            self.assertEqual(calls, [])
            target = root / "research/2026-10-20/test-essay/index.html"
            original = target.read_text()
            _, log = self.run_publisher(root)  # Empty legacy result must not erase new source.
            self.assertTrue(target.exists())
            self.assertIn("New/updated pages rendered: 0", log)
            self.assertEqual(target.read_text(), original)
            (root / self.entry["source_path"]).write_text(
                "## 正文\n\n这是修改后的研究文章，应该重新发布。", "utf-8")
            self.run_publisher(root, ledger_only=True)
            self.assertIn("修改后的研究文章", target.read_text())
            state = json.loads((root / "research/_notion_state.json").read_text())
            self.assertEqual(set(state["pages"]), {self.page_id})
            self.assertEqual(state["pages"][self.page_id]["source"], "public-ledger")
            self.entry["status"] = "Draft"
            self.write_manifest(root, self.entry)
            self.run_publisher(root)
            self.assertFalse(target.exists())
            self.assertNotIn("test-essay/", (root / "sitemap.xml").read_text())

    def test_bad_source_and_short_body_fail_without_rewriting_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.prepare(root)
            state_path = root / "research/_notion_state.json"
            before = state_path.read_bytes()
            for field, value in (("source_path", "../private.md"),
                                 ("min_body_cjk", 8000), ("slug", "../bad")):
                with self.subTest(field=field):
                    bad = dict(self.entry, **{field: value})
                    self.write_manifest(root, bad)
                    with self.assertRaises(ValueError):
                        self.run_publisher(root)
                    self.assertEqual(state_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
