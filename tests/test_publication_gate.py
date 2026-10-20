"""Exercise the actual publisher without network calls or real credentials."""
import json
import os
from pathlib import Path
import runpy
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch


class PublicationGateTest(unittest.TestCase):
    def test_only_explicit_public_statuses_are_rendered_and_kept(self):
        source_root = Path(__file__).resolve().parents[1]
        statuses = {
            "ready": "Ready", "published": "Published", "draft": "Draft",
            "blank": "", "missing": None, "unknown": "Review",
        }
        pages = []
        for page_id, status in statuses.items():
            props = {
                "Title": {"type": "title", "title": [{"plain_text": page_id}]},
                "Date": {"type": "date", "date": {"start": "2026-10-20"}},
            }
            if status is not None:
                props["Status"] = {"type": "select", "select": {"name": status}}
            pages.append({"object": "page", "id": page_id, "properties": props,
                          "last_edited_time": "2026-10-20T00:00:00Z"})
        requested_bodies = []

        class Response:
            status_code = 200
            text = ""

            def __init__(self, data):
                self.data = data

            def json(self):
                return self.data

        def request(method, url, **kwargs):
            if method == "POST" and url.endswith("/query"):
                return Response({"results": pages, "has_more": False})
            if method == "GET" and url.endswith("/markdown"):
                page_id = url.split("/")[-2]
                requested_bodies.append(page_id)
                return Response({"markdown": "Public test body"})
            raise AssertionError("Unexpected request")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            for name in ("sync_notion_to_github.py", "cleanup_research_archive.py"):
                shutil.copyfile(source_root / "scripts" / name, root / "scripts" / name)
            stale = root / "research" / "2026-10-20" / "draft" / "index.html"
            stale.parent.mkdir(parents=True)
            stale.write_text("Previously published material")
            old_state = {"pages": {"draft": {"date": "2026-10-20", "slug": "draft"}}}
            (root / "research" / "_notion_state.json").write_text(json.dumps(old_state))
            fake_requests = types.SimpleNamespace(request=request)
            fake_markdown = types.SimpleNamespace(markdown=lambda text, **_: text)
            with patch.dict(os.environ, {"NOTION_API_KEY": "test-only-not-a-credential"}), \
                 patch.dict("sys.modules", {"requests": fake_requests, "markdown": fake_markdown}):
                runpy.run_path(str(root / "scripts" / "sync_notion_to_github.py"))
                runpy.run_path(str(root / "scripts" / "cleanup_research_archive.py"))
            state = json.loads((root / "research" / "_notion_state.json").read_text())
            self.assertEqual(set(state["pages"]), {"ready", "published"})
            self.assertEqual(requested_bodies, ["ready", "published"])
            self.assertFalse(stale.exists())
            for page_id in ("ready", "published"):
                self.assertTrue((root / "research" / "2026-10-20" / page_id / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
