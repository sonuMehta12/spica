"""
A stand-in for the claude.ai connector, for running the work sync by hand.
spec/work-sync.md § Build order — the step before deployment.

It does what claude.ai does when Spica is added as a custom connector:
discovers the OAuth endpoints, registers itself, sends the person to approve in
the app, swaps the one-time code for tokens, and calls the MCP tools with them.
Tokens go to a file (0600) and are never printed.

    PYTHONPATH=. uv run python scripts/work_sync_client.py login --store /tmp/t.json
    PYTHONPATH=. uv run python scripts/work_sync_client.py tools --store /tmp/t.json
    PYTHONPATH=. uv run python scripts/work_sync_client.py call work_sync_begin '{}' --store …
"""

import argparse
import asyncio
import base64
import hashlib
import json
import os
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

CALLBACK_PORT = 8765
REDIRECT = f"http://localhost:{CALLBACK_PORT}/callback"
HEADERS = {"Accept": "application/json, text/event-stream",
           "Content-Type": "application/json", "MCP-Protocol-Version": "2025-06-18"}


def _save(store: Path, data: dict) -> None:
    store.write_text(json.dumps(data))
    os.chmod(store, 0o600)


def _load(store: Path) -> dict:
    if not store.exists():
        sys.exit(f"no tokens at {store} — run `login` first")
    return json.loads(store.read_text())


class _Catch(BaseHTTPRequestHandler):
    got: dict = {}
    # A browser opens spare connections it may never use. Without a timeout a
    # handler waits on one forever and the server can never shut down.
    timeout = 5

    def do_GET(self):  # noqa: N802 — http.server's name
        q = parse_qs(urlparse(self.path).query)
        _Catch.got = {k: v[0] for k, v in q.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        said = "Connected. You can close this tab." if "code" in q else \
            f"Not connected: {q.get('error', ['unknown'])[0]}."
        self.wfile.write(f"<p style='font-family:sans-serif'>{said}</p>".encode())

    def log_message(self, *_):
        pass


async def login(base: str, store: Path, open_browser: bool, wait: int) -> None:
    async with httpx.AsyncClient(base_url=base, timeout=30) as c:
        meta = (await c.get("/.well-known/oauth-authorization-server")).json()
        reg = (await c.post(meta["registration_endpoint"], json={
            "client_name": "Spica work sync (local)", "redirect_uris": [REDIRECT],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"]})).json()
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(12)
        url = meta["authorization_endpoint"] + "?" + urlencode({
            "response_type": "code", "client_id": reg["client_id"], "redirect_uri": REDIRECT,
            "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
            "scope": "tasks", "resource": base.rstrip("/") + "/mcp"})

        server = ThreadingHTTPServer(("localhost", CALLBACK_PORT), _Catch)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"APPROVE: {url}", flush=True)
        if open_browser:
            webbrowser.open(url)
        deadline = time.time() + wait
        while not _Catch.got and time.time() < deadline:
            await asyncio.sleep(0.5)
        server.shutdown()
        got = _Catch.got
        if "code" not in got:
            sys.exit(f"no code: {got.get('error', 'timed out')}")
        if got.get("state") != state:
            sys.exit("state mismatch — refusing the code")
        tok = await c.post(meta["token_endpoint"], data={
            "grant_type": "authorization_code", "code": got["code"], "redirect_uri": REDIRECT,
            "client_id": reg["client_id"], "code_verifier": verifier})
        if tok.status_code != 200:
            sys.exit(f"token exchange failed: {tok.status_code} {tok.text}")
        t = tok.json()
        _save(store, {"base": base, "client_id": reg["client_id"],
                      "token_endpoint": meta["token_endpoint"],
                      "access_token": t["access_token"], "refresh_token": t["refresh_token"],
                      "expires_at": time.time() + t.get("expires_in", 3600)})
        print(f"CONNECTED: tokens saved to {store} (scope {t.get('scope')})", flush=True)


async def start(base: str, store: Path, redirect: str) -> None:
    """Two-step login, for a browser that cannot reach a local callback port:
    register and print the approval URL, keeping what `finish` needs. Any page
    the browser can load will do as the redirect — the code is read from the
    URL it lands on."""
    async with httpx.AsyncClient(base_url=base, timeout=30) as c:
        meta = (await c.get("/.well-known/oauth-authorization-server")).json()
        reg = (await c.post(meta["registration_endpoint"], json={
            "client_name": "Spica work sync (local)", "redirect_uris": [redirect],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"]})).json()
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(12)
    url = meta["authorization_endpoint"] + "?" + urlencode({
        "response_type": "code", "client_id": reg["client_id"], "redirect_uri": redirect,
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
        "scope": "tasks", "resource": base.rstrip("/") + "/mcp"})
    _save(store, {"pending": True, "base": base, "client_id": reg["client_id"],
                  "token_endpoint": meta["token_endpoint"], "verifier": verifier,
                  "state": state, "redirect": redirect})
    print(f"APPROVE: {url}", flush=True)


async def finish(store: Path, redirected: str) -> None:
    """Swap the code in the URL the browser was sent back to."""
    d = _load(store)
    q = {k: v[0] for k, v in parse_qs(urlparse(redirected).query).items()}
    if "code" not in q:
        sys.exit(f"no code: {q.get('error', 'none in that URL')}")
    if q.get("state") != d.get("state"):
        sys.exit("state mismatch — refusing the code")
    async with httpx.AsyncClient(timeout=30) as c:
        tok = await c.post(d["token_endpoint"], data={
            "grant_type": "authorization_code", "code": q["code"],
            "redirect_uri": d.get("redirect", REDIRECT),
            "client_id": d["client_id"], "code_verifier": d["verifier"]})
    if tok.status_code != 200:
        sys.exit(f"token exchange failed: {tok.status_code} {tok.text}")
    t = tok.json()
    _save(store, {"base": d["base"], "client_id": d["client_id"],
                  "token_endpoint": d["token_endpoint"], "access_token": t["access_token"],
                  "refresh_token": t["refresh_token"],
                  "expires_at": time.time() + t.get("expires_in", 3600)})
    print(f"CONNECTED: tokens saved to {store} (scope {t.get('scope')})", flush=True)


async def _token(store: Path) -> dict:
    """The saved token, refreshed first if it has expired — as claude.ai would."""
    d = _load(store)
    if time.time() < d["expires_at"] - 60:
        return d
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(d["token_endpoint"], data={
            "grant_type": "refresh_token", "refresh_token": d["refresh_token"],
            "client_id": d["client_id"]})
    if r.status_code != 200:
        sys.exit(f"refresh failed: {r.status_code} {r.text}")
    t = r.json()
    d.update(access_token=t["access_token"], refresh_token=t["refresh_token"],
             expires_at=time.time() + t.get("expires_in", 3600))
    _save(store, d)
    return d


async def rpc(store: Path, method: str, params: dict) -> dict:
    d = await _token(store)
    async with httpx.AsyncClient(base_url=d["base"], timeout=60) as c:
        auth = {"Authorization": f"Bearer {d['access_token']}"}
        r = await c.post("/mcp", headers={**HEADERS, **auth},
                         json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if r.status_code != 200:
        sys.exit(f"{method} → {r.status_code} {r.text[:300]}")
    return r.json()


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["login", "start", "finish", "tools", "call"])
    ap.add_argument("tool", nargs="?")
    ap.add_argument("args", nargs="?", default="{}", help="the tool's arguments, as JSON")
    ap.add_argument("--base", default="http://localhost:8001")
    ap.add_argument("--store", type=Path, required=True, help="where the tokens live")
    ap.add_argument("--open", action="store_true", help="open the approval page")
    ap.add_argument("--wait", type=int, default=300, help="seconds to wait for approval")
    ap.add_argument("--args-file", type=Path, help="read the arguments from a file")
    ap.add_argument("--redirect", default=REDIRECT, help="for `start`: where approval returns")
    a = ap.parse_args()

    if a.command == "login":
        await login(a.base, a.store, a.open, a.wait)
    elif a.command == "start":
        await start(a.base, a.store, a.redirect)
    elif a.command == "finish":
        await finish(a.store, a.tool or "")
    elif a.command == "tools":
        out = await rpc(a.store, "tools/list", {})
        for t in out["result"]["tools"]:
            print(f"{t['name']}: {t.get('description', '')[:90]}")
    else:
        args = json.loads(a.args_file.read_text() if a.args_file else a.args)
        out = await rpc(a.store, "tools/call", {"name": a.tool, "arguments": args})
        res = out.get("result", out)
        body = res.get("structuredContent")
        if body is None and res.get("content"):
            text = res["content"][0].get("text", "")
            try:
                body = json.loads(text)
            except ValueError:
                body = text
        print(json.dumps({"isError": res.get("isError"), "body": body}, indent=1,
                         ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())
