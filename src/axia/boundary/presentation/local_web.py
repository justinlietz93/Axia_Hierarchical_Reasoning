from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Type
from urllib.parse import urlparse

from axia.boundary.ports.run_store import RunStore, RunStoreFailure
from axia.operation import project_run_trace
from axia.projection import project_web_run
from axia.shared.ids import RunId


def create_local_web_server(run_store: RunStore, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Create a local read-only UI server over existing run-store projections."""

    handler = _handler_for(run_store)
    return ThreadingHTTPServer((host, port), handler)


def serve_local_web(run_store: RunStore, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = create_local_web_server(run_store, host, port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _handler_for(run_store: RunStore) -> Type[BaseHTTPRequestHandler]:
    class LocalWebHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/" or path.startswith("/runs/"):
                _write_html(self, _INDEX_HTML)
                return
            if path == "/api/runs":
                _write_json(
                    self,
                    {
                        "runs": [
                            {
                                "run_id": run.run_id.value,
                                "created_at": run.created_at,
                                "status": run.status,
                                "mode": run.mode,
                            }
                            for run in run_store.list_runs()
                        ]
                    },
                )
                return
            parts = path.split("/")
            if len(parts) in {4, 5} and parts[:3] == ["", "api", "runs"]:
                try:
                    run_id = RunId.from_value(parts[3])
                    stored = run_store.read_run(run_id)
                    payload = (
                        project_run_trace(run_id, run_store).to_payload()
                        if len(parts) == 5 and parts[4] == "trace"
                        else project_web_run(stored.manifest.payload)
                    )
                    _write_json(self, payload)
                except (RunStoreFailure, ValueError) as error:
                    _write_json(self, {"error": str(error)}, status=404)
                return
            _write_json(self, {"error": "not found"}, status=404)

        def log_message(self, format: str, *args: object) -> None:
            return

    return LocalWebHandler


def _write_json(handler: BaseHTTPRequestHandler, payload: object, status: int = 200) -> None:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _write_html(handler: BaseHTTPRequestHandler, content: str) -> None:
    encoded = content.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


_INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Axia Runs</title><style>
body{margin:0;font:14px system-ui,sans-serif;color:#17202a;background:#f6f7f8}header{padding:16px 24px;background:#fff;border-bottom:1px solid #d8dde3}main{display:grid;grid-template-columns:minmax(220px,320px) 1fr;min-height:calc(100vh - 57px)}nav{padding:16px;border-right:1px solid #d8dde3;background:#fff}section{padding:24px;max-width:900px}button{width:100%;text-align:left;padding:10px;border:0;border-bottom:1px solid #e7eaee;background:#fff;color:#17202a;cursor:pointer}.label{font-size:12px;color:#617080}.block{margin:18px 0;padding-top:12px;border-top:1px solid #d8dde3}pre{white-space:pre-wrap;word-break:break-word;background:#fff;border:1px solid #d8dde3;padding:12px;max-height:320px;overflow:auto}h1,h2,h3{margin:0 0 10px}h1{font-size:18px}h2{font-size:20px}@media(max-width:700px){main{grid-template-columns:1fr}nav{border-right:0;border-bottom:1px solid #d8dde3}}</style></head>
<body><header><h1>Axia Local Run Browser</h1></header><main><nav id="runs">Loading local runs...</nav><section id="detail"><p>Select a run to inspect its stored reasoning evidence.</p></section></main>
<script>const runs=document.querySelector('#runs'),detail=document.querySelector('#detail');function show(v){return '<pre>'+JSON.stringify(v,null,2).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))+'</pre>'}async function load(id){let r=await fetch('/api/runs/'+id),v=await r.json();detail.innerHTML='<h2>'+id+'</h2><div class="block"><h3>Run state</h3>'+show({status:v.status,mode:v.mode,completed_nodes:v.completed_nodes})+'</div><div class="block"><h3>Scorecards</h3>'+show(v.scorecards)+'</div><div class="block"><h3>Accepted artifacts</h3>'+show(v.accepted_artifacts)+'</div><div class="block"><h3>Final answer</h3>'+show(v.final_answer)+'</div><div class="block"><h3>Memory candidates</h3>'+show(v.memory_candidates)+'</div>'}fetch('/api/runs').then(r=>r.json()).then(v=>{runs.innerHTML=v.runs.length?'':'<p class="label">No local runs.</p>';v.runs.forEach(x=>{let b=document.createElement('button');b.textContent=x.run_id+' · '+x.status+' · '+x.mode;b.onclick=()=>load(x.run_id);runs.append(b)})}).catch(e=>runs.textContent=String(e));</script></body></html>"""
