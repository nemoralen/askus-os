"""Offline updater regressions: python3 -m unittest discover -s tests -v."""
import gzip
import hashlib
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "config/includes.chroot/usr/local/sbin/askus-update"
SPEC = spec_from_loader("askus_update", SourceFileLoader("askus_update", str(PATH)))
updater = module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def chunks(data, size):
    return [(off, len(data[off:off + size]), digest(data[off:off + size]))
            for off in range(0, len(data), size)]


def index(data, size):
    rows = [f"askus-delta-index 1 test.iso {len(data)}"]
    rows += [f"{off} {n} {h}" for off, n, h in chunks(data, size)]
    return gzip.compress(('\n'.join(rows) + '\n').encode())


class DeltaResume(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name)
        self.status = patch.object(updater, "write_status")
        self.status.start()
        self.addCleanup(self.status.stop)

    def pieces(self, data, sizes, cached=None):
        result, off = [], 0
        for i, size in enumerate(sizes):
            name = f"test.iso.part{i:02}"
            result.append({'name': name, 'size': size, 'url': f'https://example.invalid/{name}'})
            if cached is not None:
                (self.dest / name).write_bytes(cached[off:off + size])
            off += size
        self.assertEqual(off, len(data))
        return result

    def prepare(self, data, pieces, size=64, old=(), disk=None):
        return updater.delta_prepare(pieces, str(self.dest), chunks(data, size), old, disk)

    def test_partial_request_recovery_saves_75_percent_of_download_bytes(self):
        size = 256 * 1024
        data = b''.join(bytes([i + 1]) * size for i in range(8))
        pieces = self.pieces(data, [len(data)], cached=data[:6 * size])
        need, reused = self.prepare(data, pieces, size=size)
        ranges = updater.ranges_for_pieces(need, pieces)
        requested = sum(b - a + 1 for _, a, b in ranges)
        self.assertEqual(reused, 6 * size)
        self.assertEqual(requested, 2 * size)
        self.assertEqual(requested / len(data), .25)

    def test_cached_chunks_skip_usb_reads(self):
        data = b'a' * 64 + b'b' * 64
        pieces = self.pieces(data, [len(data)], cached=data)
        disk = self.dest / 'old.iso'
        disk.write_bytes(data)
        real_pread = updater.os.pread
        with patch.object(updater.os, 'pread', wraps=real_pread) as pread:
            need, reused = self.prepare(data, pieces, old=chunks(data, 64), disk=str(disk))
        self.assertEqual((need, reused), ([], len(data)))
        # Two cache reads; no additional reads from the old USB image.
        self.assertEqual(pread.call_count, 2)

    def test_cached_chunk_can_cross_split_piece_boundary(self):
        data = b'a' * 64 + b'b' * 64
        pieces = self.pieces(data, [40, 88], cached=data)
        self.assertEqual(self.prepare(data, pieces), ([], len(data)))

    def test_corruption_in_either_half_of_split_chunk_requires_download(self):
        data = b'a' * 64 + b'b' * 64
        for offset in (1, 50):
            with self.subTest(corrupt_offset=offset):
                damaged = data[:offset] + b'x' + data[offset + 1:]
                pieces = self.pieces(data, [40, 88], cached=damaged)
                self.assertEqual(self.prepare(data, pieces), ([(0, 63)], 64))

    def test_missing_or_truncated_piece_is_not_counted_as_cached(self):
        data = b'a' * 64 + b'b' * 64
        pieces = self.pieces(data, [40, 88], cached=data)
        for content in (None, b'a' * 10):
            with self.subTest(content=content):
                path = self.dest / pieces[1]['name']
                if content is None:
                    path.unlink()
                else:
                    path.write_bytes(content)
                self.assertEqual(self.prepare(data, pieces), ([(0, 63), (64, 127)], 0))

    def test_invalid_cache_falls_back_to_verified_usb_chunk(self):
        data = b'a' * 64 + b'b' * 64
        pieces = self.pieces(data, [len(data)], cached=b'x' * len(data))
        disk = self.dest / 'old.iso'
        disk.write_bytes(data)
        self.assertEqual(self.prepare(data, pieces, old=chunks(data, 64), disk=str(disk)), ([], len(data)))
        self.assertEqual((self.dest / pieces[0]['name']).read_bytes(), data)

    def test_corrupt_usb_chunk_is_not_reused(self):
        data = b'a' * 64
        pieces = self.pieces(data, [len(data)])
        disk = self.dest / 'old.iso'
        disk.write_bytes(b'x' * len(data))
        self.assertEqual(self.prepare(data, pieces, old=chunks(data, 64), disk=str(disk)), ([(0, 63)], 0))

    def test_stale_delta_metadata_cannot_skip_a_needed_range(self):
        data = b'a' * 64
        pieces = self.pieces(data, [len(data)], cached=b'x' * len(data))
        rid = f'{pieces[0]["name"]}:0-63'
        (self.dest / updater.STATE_NAME).write_text(json.dumps({'delta': [rid]}))
        # No real network: an attempted fetch proves the stale entry was ignored.
        with patch.object(updater.subprocess, 'Popen', side_effect=OSError('offline test')) as fetch:
            with self.assertRaises(updater.Failure):
                updater.download(pieces, str(self.dest), len(data), ranges=[(pieces[0], 0, 63)], workers=1)
        fetch.assert_called_once()

    def fetch(self, data, pieces, raw, expected=None):
        assets = [{'name': 'test.iso.index.gz', 'url': 'https://example.invalid/index'}]
        with patch.object(updater, 'curl_bytes', return_value=raw), \
             patch.object(updater, 'boot_disk', return_value=None), \
             patch.object(updater, 'download') as download:
            result = updater.fetch_image({}, assets, pieces, str(self.dest), len(data),
                                         expected or digest(data), 1, 'download', 'check')
        return result, download

    def test_fetch_image_resumes_without_an_old_index(self):
        data = b'a' * 64 + b'b' * 64
        pieces = self.pieces(data, [40, 88], cached=data)
        (ok, _), download = self.fetch(data, pieces, index(data, 64))
        self.assertTrue(ok)
        self.assertEqual(download.call_args.kwargs['ranges'], [])
        self.assertEqual((self.dest / updater.VERIFIED_NAME).read_text(), digest(data))

    def test_unsigned_index_cannot_override_signed_whole_image_hash(self):
        data = b'a' * 64
        pieces = self.pieces(data, [len(data)], cached=data)
        (ok, _), download = self.fetch(data, pieces, index(data, 64), expected=digest(b'authentic image'))
        self.assertFalse(ok)
        self.assertEqual(download.call_count, 2)  # delta, then the existing full fallback
        self.assertNotIn('ranges', download.call_args.kwargs)
        self.assertFalse((self.dest / updater.VERIFIED_NAME).exists())

    def test_mismatched_index_total_falls_back_before_reading_the_boot_disk(self):
        data = b'a' * 64
        pieces = self.pieces(data, [len(data)], cached=data)
        for size in (32, 128):
            with self.subTest(index_size=size):
                (self.dest / updater.VERIFIED_NAME).unlink(missing_ok=True)
                with patch.object(updater, 'boot_disk', side_effect=AssertionError('must reject first')):
                    with patch.object(updater, 'curl_bytes', return_value=index(b'x' * size, 32)), \
                         patch.object(updater, 'download') as download:
                        updater.fetch_image({}, [{'name': 'test.iso.index.gz', 'url': 'unused'}], pieces,
                                            str(self.dest), len(data), digest(data), 1, 'download', 'check')
                download.assert_called_once()
                self.assertNotIn('ranges', download.call_args.kwargs)

    def test_index_rejects_unbounded_chunks_and_nonhex_fingerprints(self):
        for n, h in ((updater.MAX_INDEX_CHUNK + 1, 'a' * 64), (64, 'z' * 64)):
            with self.subTest(length=n, fingerprint=h):
                raw = gzip.compress(f'askus-delta-index 1 test.iso {n}\n0 {n} {h}\n'.encode())
                with self.assertRaises(ValueError):
                    updater.parse_index(raw)


if __name__ == '__main__':
    unittest.main()
