import gc, os, sqlite3, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from context_player.feedback import FeedbackStore

def open_fds(path):
    found=[]
    for f in Path('/proc/self/fd').iterdir():
        try:
            if os.readlink(f)==str(path): found.append(str(f))
        except FileNotFoundError: pass
    return found

class Resources(unittest.TestCase):
    def test_corruption_closes_immediately_preserves_bytes_and_error(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'events.sqlite3'; raw=b'CORRUPT USER BYTES';p.write_bytes(raw)
            # Keep traceback alive: production must close, not rely on GC.
            error=None
            try: FeedbackStore(d)
            except sqlite3.DatabaseError as e: error=e
            self.assertIsNotNone(error)
            self.assertEqual(p.read_bytes(),raw)
            self.assertEqual(open_fds(p),[])
    def test_external_schema_failure_closes_real_connection(self):
        real_connect=sqlite3.connect; captured=[]
        class Failure(sqlite3.Connection):
            def executescript(self,sql): raise sqlite3.OperationalError('injected external schema failure')
        def connect(*args,**kwargs):
            db=real_connect(*args,**kwargs,factory=Failure);captured.append(db);return db
        with tempfile.TemporaryDirectory() as d:
            with patch('sqlite3.connect',connect):
                with self.assertRaisesRegex(sqlite3.OperationalError,'injected external'): FeedbackStore(d)
            with self.assertRaises(sqlite3.ProgrammingError):captured[0].execute('SELECT 1')
    def test_success_create_close_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            db=FeedbackStore(d);db.close();self.assertEqual(open_fds(Path(d)/'events.sqlite3'),[])
        self.assertFalse(Path(d).exists())
if __name__=='__main__':unittest.main()
