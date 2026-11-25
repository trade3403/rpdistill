import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.request import urlopen

from rpdistill.transfer import transfer_file, hf_url

DATA = b"abcd" * 1000
SHA = hashlib.sha256(DATA).hexdigest()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        header = self.headers.get("Range")
        self.server.ranges.append(header)
        start = int(header[6:-1]) if header and not self.server.ignore else 0
        body = DATA[start:]
        self.send_response(206 if start else 200)
        if start:
            self.send_header("Content-Range", ("bytes 0-1/2" if self.server.bad_range
                             else f"bytes {start}-{len(DATA)-1}/{len(DATA)}"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TransferTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dest = Path(tmp.name) / "model"
        self.part = self.dest.with_name("model.rpdistill-part")
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.ranges, server.ignore, server.bad_range = [], False, False
        self.server = server
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        self.url = f"http://127.0.0.1:{server.server_port}/model"

    def fetch(self, **kw):
        options = dict(size=len(DATA), sha256=SHA, opener=urlopen, chunk_size=128)
        return transfer_file(self.url, self.dest, **(options | kw))

    def test_real_socket_and_cache(self):
        events = []
        self.fetch(on_bytes=events.append)
        self.assertEqual(sum(events), len(DATA))
        self.assertGreater(len(events), 1)
        self.assertEqual(self.dest.read_bytes(), DATA)
        self.fetch(on_bytes=events.append)
        self.assertEqual(sum(events), len(DATA))
        self.assertEqual(len(self.server.ranges), 1)

    def test_partial_range_resume(self):
        self.part.write_bytes(DATA[:100])
        events = []
        self.fetch(on_bytes=events.append)
        self.assertEqual(self.server.ranges, ["bytes=100-"])
        self.assertEqual(sum(events), len(DATA)-100)
        self.assertFalse(self.part.exists())

    def test_server_ignores_range(self):
        self.part.write_bytes(DATA[:100])
        self.server.ignore = True
        self.fetch()
        self.assertEqual(self.dest.read_bytes(), DATA)

    def test_wrong_range_rejected(self):
        self.part.write_bytes(DATA[:100])
        self.server.bad_range = True
        with self.assertRaisesRegex(ValueError, "Content-Range"):
            self.fetch()
        self.assertFalse(self.dest.exists())
        self.assertEqual(self.part.stat().st_size, 100)

    def test_checksum_failure(self):
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.fetch(sha256="a"*64)
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.part.exists())

    def test_pause_and_resume(self):
        def check():
            if self.part.exists() and self.part.stat().st_size >= 128:
                raise InterruptedError()
        with self.assertRaises(InterruptedError):
            self.fetch(checkpoint=check)
        self.assertTrue(self.part.exists())
        self.assertFalse(self.dest.exists())
        self.fetch()
        self.assertEqual(self.dest.read_bytes(), DATA)

    def test_url_validation(self):
        self.assertEqual(hf_url("Qwen/test", "a"*40, "config.json"),
                         "https://huggingface.co/Qwen/test/resolve/"+"a"*40+"/config.json")
        with self.assertRaises(ValueError):
            hf_url("Qwen/test", "main", "config.json")
