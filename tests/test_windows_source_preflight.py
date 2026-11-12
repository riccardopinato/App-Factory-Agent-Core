import pathlib
import tempfile
import unittest
from scripts.windows_source_preflight import inventory

class WindowsPreflightTests(unittest.TestCase):
    def test_finds_source_only_and_keeps_no_absolute_root(self):
        with tempfile.TemporaryDirectory() as name:
            root=pathlib.Path(name)
            (root/"agent.py").write_text("print('safe')")
            (root/"patch_retry.py").write_text("pass")
            (root/".env").write_text("SECRET=sensitive")
            (root/"credentials.json").write_text('{"token":"sensitive"}')
            (root/"local.db").write_text("binary")
            (root/"models").mkdir()
            (root/"models"/"model.txt").write_text("sensitive")
            (root/"logs").mkdir()
            (root/"logs"/"run.txt").write_text("sensitive")
            got=inventory(root)
            names={r["relative_path"] for r in got["files"]}
            self.assertEqual(names,{"agent.py","patch_retry.py"})
            self.assertTrue(all(len(r["sha256"])==64 for r in got["files"]))
            self.assertFalse(got["source_imported"])
            self.assertFalse(got["secrets_scanned"])
            self.assertNotIn(name,str(got))
            self.assertNotIn("sensitive",str(got))

    def test_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as name:
            root=pathlib.Path(name)
            (root/"src.py").write_text("pass")
            (root/"outside.py").symlink_to(root/"src.py")
            got=inventory(root)
            self.assertEqual([r["relative_path"] for r in got["files"]],["src.py"])
            self.assertEqual(got["skipped_counts"]["symlink"],1)

    def test_bounded_large_file_and_determinism(self):
        with tempfile.TemporaryDirectory() as name:
            root=pathlib.Path(name)
            (root/"a.py").write_text("one")
            got=inventory(root)
            self.assertEqual(inventory(root),got)
            (root/"large.txt").write_bytes(b"x"*(5*1024*1024+1))
            self.assertEqual(inventory(root)["skipped_counts"]["too_large"],1)

if __name__=="__main__":
    unittest.main()
