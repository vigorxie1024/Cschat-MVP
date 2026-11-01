#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cschat —— 碳硅基联合体最小协作中枢（零依赖版）

设计取舍：
  139aina 博士给的原始方案依赖 fastapi/uvicorn/websockets（要 pip install）。
  这里用 Python 标准库实现同样的东西：一个网页聊天室 + SSE 实时推送 + 可选调用 DeepSeek。
  理由：样板产品第一要求是「拉下来就能跑」，而不是先装一堆依赖。

跑起来：
  set DEEPSEEK_API_KEY=你的密钥          （Windows）
  export DEEPSEEK_API_KEY=你的密钥        （macOS/Linux）
  python main.py
  浏览器打开 http://127.0.0.1:8000

接口：
  GET  /            聊天页面
  GET  /events      SSE 实时流
  GET  /history     历史消息 JSON
  POST /say         {"from":"VX","text":"..."}  发一句话
  POST /ask         {"q":"..."}                 问 AI（需要 DEEPSEEK_API_KEY）
"""
import json
import os
import queue
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("CSCHAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("CSCHAT_PORT", "8000"))
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
API_URL = os.environ.get("CSCHAT_API", "https://api.deepseek.com/chat/completions")
MODEL = os.environ.get("CSCHAT_MODEL", "deepseek-chat")

HISTORY = []          # [{id, from, text, at}]
SUBSCRIBERS = []      # [queue.Queue]
LOCK = threading.Lock()
SEQ = {"n": 0}

PAGE = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>Cschat · 碳硅基最小协作中枢</title>
<style>
body{margin:0;font:15px/1.7 -apple-system,'Segoe UI',system-ui,sans-serif;background:#14161a;color:#e6e8eb}
header{padding:12px 16px;background:#1c1f24;border-bottom:1px solid #2a2f36;display:flex;gap:10px;align-items:center}
header b{color:#7fd1ae}#st{color:#8b949e;font-size:12px;margin-left:auto}
#log{height:calc(100vh - 128px);overflow-y:auto;padding:12px 16px}
.m{padding:6px 0;border-bottom:1px solid #1e2228}
.who{color:#7fd1ae;font-weight:600}.t{color:#8b949e;font-size:11px;margin-left:8px}
.txt{white-space:pre-wrap;margin-top:2px}
footer{padding:10px 16px;background:#1c1f24;border-top:1px solid #2a2f36;display:flex;gap:8px}
#who{width:96px;padding:10px;background:#0f1114;border:1px solid #2a2f36;color:#e6e8eb;border-radius:6px}
#say{flex:1;padding:10px;background:#0f1114;border:1px solid #2a2f36;color:#e6e8eb;border-radius:6px}
button{padding:10px 16px;background:#2d6a4f;color:#fff;border:0;border-radius:6px;cursor:pointer;font-weight:600}
</style>
<header><b>Cschat</b><span style="color:#8b949e;font-size:12.5px">碳硅基联合体 · 最小协作中枢</span><span id=st>连接中…</span></header>
<div id=log></div>
<footer>
  <input id=who placeholder="我是谁" value="VX">
  <input id=say placeholder="说一句，回车发出（所有人实时看到）" autofocus>
  <button id=go>发</button>
</footer>
<script>
const log=document.getElementById('log'),st=document.getElementById('st');
function add(m){
  const d=document.createElement('div');d.className='m';
  const w=document.createElement('span');w.className='who';w.textContent=m.from;
  const t=document.createElement('span');t.className='t';t.textContent=new Date(m.at).toLocaleTimeString('zh-CN');
  const x=document.createElement('div');x.className='txt';x.textContent=m.text;
  d.append(w,t,x);log.appendChild(d);log.scrollTop=log.scrollHeight;
}
async function send(){
  const el=document.getElementById('say');const v=el.value.trim();if(!v)return;el.value='';
  await fetch('/say',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({from:document.getElementById('who').value||'Anonymous',text:v})});
}
document.getElementById('go').onclick=send;
document.getElementById('say').addEventListener('keydown',e=>{if(e.key==='Enter')send()});
const es=new EventSource('/events');
es.onopen=()=>{st.textContent='实时在线'};
es.onerror=()=>{st.textContent='重连中…'};
es.onmessage=e=>{try{add(JSON.parse(e.data))}catch(_){}};
fetch('/history').then(r=>r.json()).then(j=>j.messages.forEach(add));
</script></html>"""


def broadcast(msg):
    with LOCK:
        for q in list(SUBSCRIBERS):
            try:
                q.put_nowait(msg)
            except Exception:
                pass


def ask_ai(q, who="Cschat"):
    """调用 DeepSeek（标准库 urllib，无需第三方包）。没配 key 就明确拒绝，不假装。"""
    if not API_KEY:
        return "未配置 DEEPSEEK_API_KEY，无法调用模型（这不是故障，是没配密钥）。"
    body = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是碳硅基联合体里的助手，回答简洁、直接、不客套。"},
            {"role": "user", "content": q},
        ],
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + API_KEY,
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return "调用失败：" + str(e)[:200]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def do_GET(self):
        if self.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/history":
            with LOCK:
                return self._json(200, {"messages": HISTORY[-200:]})
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = queue.Queue()
            with LOCK:
                SUBSCRIBERS.append(q)
            try:
                self.wfile.write(b"retry: 1500\n\n")
                self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=25)
                        self.wfile.write(("data: " + json.dumps(msg, ensure_ascii=False) + "\n\n").encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": ka\n\n")
                    self.wfile.flush()
            except Exception:
                pass
            finally:
                with LOCK:
                    if q in SUBSCRIBERS:
                        SUBSCRIBERS.remove(q)
            return
        self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            return self._json(400, {"ok": False, "error": "bad json"})

        if self.path == "/say":
            text = str(payload.get("text") or "").strip()
            if not text:
                return self._json(400, {"ok": False, "error": "empty"})
            with LOCK:
                SEQ["n"] += 1
                msg = {"id": SEQ["n"], "from": str(payload.get("from") or "Anonymous"),
                       "text": text[:4000], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                HISTORY.append(msg)
            broadcast(msg)
            return self._json(200, {"ok": True, "id": msg["id"]})

        if self.path == "/ask":
            q = str(payload.get("q") or payload.get("text") or "").strip()
            if not q:
                return self._json(400, {"ok": False, "error": "empty"})
            if not API_KEY:
                # 没密钥就明确失败，不返回 ok:true 假装调用过（这条是给接口调用方的诚实底线）
                return self._json(503, {"ok": False, "error": "未配置 DEEPSEEK_API_KEY"})
            answer = ask_ai(q)
            with LOCK:
                SEQ["n"] += 1
                msg = {"id": SEQ["n"], "from": "AI", "text": answer, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                HISTORY.append(msg)
            broadcast(msg)
            return self._json(200, {"ok": True, "answer": answer})

        self._json(404, {"ok": False, "error": "not found"})


if __name__ == "__main__":
    print("Cschat 运行中: http://%s:%d/" % (HOST, PORT))
    print("模型密钥: %s" % ("已配置" if API_KEY else "未配置（/ask 会明确拒绝）"))
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
