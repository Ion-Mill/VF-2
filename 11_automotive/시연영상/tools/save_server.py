"""시연영상용 작은 서버 — 11_automotive 폴더를 그대로 내주고, POST /save/<파일이름> 으로 받은 그림을 커서시안/ 에 저장한다.
이브 3D 모델(frontend/src/components/robot3d.js)로 커서 그림을 뽑을 때만 켠다 (포트 8777, 내 PC에서만).
"""
import http.server
import socketserver
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # 11_automotive
OUT = Path(__file__).resolve().parents[1] / "커서시안"


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def do_POST(self):
        name = Path(urllib.parse.unquote(self.path.rsplit("/", 1)[-1])).name   # 폴더 밖으로 못 나가게 이름만
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        OUT.mkdir(exist_ok=True)
        (OUT / name).write_bytes(body)
        self.send_response(200); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers(); self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", 8777), H) as s:
    s.serve_forever()
