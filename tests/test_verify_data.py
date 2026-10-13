"""Integrity checks use temporary bytes, never models or frozen evidence."""
import csv
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from verify_data import verify_manifest


class ManifestVerificationTests(unittest.TestCase):
    def run_fixture(self, expected, actual=b'snapshot', member='', remove=False):
        scratch = Path(__file__).resolve().parents[1] / 'tmp' / 'verify_data_tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            path = root / ('source.zip' if member else 'source.csv')
            if member:
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr(member, actual)
            else:
                path.write_bytes(actual)
            manifest = root / 'MANIFEST.csv'
            row = {'file': path.name, 'archive_member': member, 'bytes': len(actual),
                   'sha256': expected, 'included_in_git': 'no'}
            with manifest.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(row))
                writer.writeheader(); writer.writerow(row)
            if remove:
                path.unlink()
            return verify_manifest(manifest, root)

    def test_matching_bytes(self):
        self.assertEqual(self.run_fixture(hashlib.sha256(b'snapshot').hexdigest()), 1)

    def test_changed_hash_fails(self):
        with self.assertRaisesRegex(ValueError, 'Snapshot mismatch'):
            self.run_fixture('0' * 64)

    def test_member_bytes_verified(self):
        self.assertEqual(self.run_fixture(hashlib.sha256(b'snapshot').hexdigest(), member='results.csv'), 1)
        with self.assertRaisesRegex(ValueError, 'Snapshot mismatch'):
            self.run_fixture('0' * 64, member='results.csv')

    def test_missing_file_fails(self):
        with self.assertRaises(FileNotFoundError):
            self.run_fixture(hashlib.sha256(b'snapshot').hexdigest(), remove=True)


if __name__ == '__main__':
    unittest.main()
