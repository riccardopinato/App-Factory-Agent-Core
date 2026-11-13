import sqlite3
import tempfile
import unittest
from pathlib import Path

try:
    from scripts.x10_windows_autopilot_receipt import FILES, make_receipt, source_inventory
except ModuleNotFoundError:
    from x10_windows_autopilot_receipt import FILES, make_receipt, source_inventory


class WindowsReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in FILES:
            (self.root / name).write_text('VERSION = "0.6.0"\n', encoding='utf-8')

    def test_inventory_exact_allowlist(self):
        (self.root / '.env').write_text('SENSITIVE', encoding='utf-8')
        inventory, errors, contents = source_inventory(self.root)
        self.assertEqual(set(inventory), set(FILES))
        self.assertEqual(errors, [])
        self.assertNotIn('.env', contents)

    def test_optional_upgrader_missing_is_safe(self):
        receipt = make_receipt(self.root, export=self.root / 'safe.zip')
        self.assertEqual(set(receipt['source_files']), set(FILES))

    def test_secret_blocks_export(self):
        (self.root / FILES[0]).write_text('token="ghp_' + 'A' * 35 + '"\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            make_receipt(self.root, export=self.root / 'import.zip')
        self.assertFalse((self.root / 'import.zip').exists())

    def test_export_no_state_or_logs(self):
        import zipfile
        (self.root / 'autopilot-state').mkdir()
        (self.root / 'autopilot-state' / 'queue.sqlite3').write_text('PRIVATE')
        output = self.root / 'private.zip'
        receipt = make_receipt(self.root, export=output)
        self.assertFalse(receipt['x10_008_complete'])
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(set(archive.namelist()),
                             {'source/' + name for name in FILES} | {'MANIFEST.json'})

    def test_readonly_db_sanitized(self):
        state = self.root / 'autopilot-state'
        state.mkdir()
        with sqlite3.connect(state / 'queue.sqlite3') as con:
            con.execute('CREATE TABLE jobs (repo text, issue integer, status text, pr integer, '
                        'pr_sha text, attempts integer, ci_repairs integer, created_at real, task text)')
            con.execute('INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        ('riccardopinato/180FlipCharge', 6, 'ci_pass', 7, 'a' * 40,
                         1, 0, 1, 'PRIVATE_CONTENT_DO_NOT_LEAK'))
        receipt = make_receipt(self.root)
        self.assertNotIn('PRIVATE_CONTENT_DO_NOT_LEAK', str(receipt))
        self.assertEqual(receipt['local_queue']['jobs'][0]['pr'], 7)
        self.assertFalse(receipt['x10_015_complete'])

    def test_missing_source_not_complete(self):
        (self.root / FILES[1]).unlink()
        receipt = make_receipt(self.root)
        self.assertTrue(receipt['source_problems'])
        self.assertFalse(receipt['x10_008_complete'])


if __name__ == '__main__':
    unittest.main()
