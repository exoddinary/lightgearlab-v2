# Local preview server for web/ that tells the browser not to cache, so edits (and re-exported .glb files) show on reload.
#   python3 tools/serve.py   → http://localhost:8123
import http.server, functools, os
class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()
root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')
http.server.ThreadingHTTPServer(('', 8123), functools.partial(NoCache, directory=root)).serve_forever()
