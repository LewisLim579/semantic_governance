#!/usr/bin/env python3
"""시맨틱 레이어 관리 UI 백엔드 (§3.6).

현업이 브라우저 폼/에디터로 원천(YAML)을 수정하면 Git 작업본에 반영한다.
- 표준 라이브러리만으로 동작 (정적 파일 서빙 + 간단 REST API)
- YAML 파싱/직렬화는 PyYAML 사용 (requirements.txt)
- 저장 시 검증기(tools/validate.py)를 실행해 결과를 함께 반환
- (선택) git commit 엔드포인트 제공

실행:  python ui/server.py   →  http://localhost:8765
주의:  로컬 편집 도구이며 인증/권한은 포함하지 않는다(표준 §3.6 '추후 정의').
"""
from __future__ import annotations

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

try:
    import yaml
except ImportError:
    print("[FATAL] PyYAML 이 필요합니다.  pip install -r requirements.txt")
    sys.exit(2)

# Windows 콘솔(cp949 등)에서도 한글/유니코드 출력이 깨지지 않도록 보정
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

UI_DIR = Path(__file__).resolve().parent
REPO_ROOT = UI_DIR.parent
PORT = 8765

# 편집 허용 대상: common/* 와 domains/*/*  (그 외 경로 쓰기 금지)
EDITABLE_PREFIXES = ("common/", "domains/")


def safe_path(rel: str) -> Path:
    """저장소 루트 밖으로 나가지 못하도록 경로를 검증한다."""
    rel = rel.replace("\\", "/").lstrip("/")
    target = (REPO_ROOT / rel).resolve()
    if REPO_ROOT not in target.parents and target != REPO_ROOT:
        raise ValueError("저장소 밖 경로 접근 금지")
    if not rel.endswith(".yaml"):
        raise ValueError("YAML 파일만 허용")
    return target


def build_tree() -> dict:
    tree = {"common": [], "domains": {}}
    common = REPO_ROOT / "common"
    if common.exists():
        tree["common"] = sorted(p.name for p in common.glob("*.yaml"))
    domains = REPO_ROOT / "domains"
    if domains.exists():
        for d in sorted(p for p in domains.iterdir() if p.is_dir()):
            tree["domains"][d.name] = sorted(p.name for p in d.glob("*.yaml"))
    return tree


def run_validation() -> dict:
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "validate.py")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT),
    )
    return {"ok": proc.returncode == 0, "output": (proc.stdout or "") + (proc.stderr or "")}


def git_commit(message: str, rel: str) -> dict:
    try:
        subprocess.run(["git", "add", rel], cwd=str(REPO_ROOT), check=True,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        proc = subprocess.run(["git", "commit", "-m", message], cwd=str(REPO_ROOT),
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        return {"ok": proc.returncode == 0, "output": (proc.stdout or "") + (proc.stderr or "")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "output": str(e)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # 조용히
        pass

    def _send(self, code: int, payload, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---------- GET ----------
    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        if route in ("/", "/index.html"):
            html = (UI_DIR / "index.html").read_bytes()
            return self._send(200, html, "text/html")
        if route == "/api/tree":
            return self._send(200, build_tree())
        if route == "/api/file":
            qs = parse_qs(parsed.query)
            rel = (qs.get("path") or [""])[0]
            try:
                path = safe_path(rel)
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            if not path.exists():
                return self._send(404, {"error": "파일 없음"})
            text = path.read_text(encoding="utf-8")
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as e:
                data = None
            return self._send(200, {"path": rel, "raw": text, "data": data})
        return self._send(404, {"error": "not found"})

    # ---------- POST ----------
    def do_POST(self):
        try:
            self._dispatch_post()
        except Exception:  # noqa: BLE001
            import traceback
            self._send(500, {"error": "server error", "trace": traceback.format_exc()})

    def _dispatch_post(self):
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw_body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return self._send(400, {"error": f"잘못된 JSON: {e}"})
        route = urlparse(self.path).path

        if route == "/api/save":
            return self._handle_save(body)
        if route == "/api/validate":
            return self._send(200, run_validation())
        if route == "/api/commit":
            rel = body.get("path", "")
            msg = body.get("message") or f"chore(semantic): update {rel}"
            return self._send(200, git_commit(msg, rel))
        return self._send(404, {"error": "not found"})

    def _handle_save(self, body: dict):
        rel = body.get("path", "")
        try:
            path = safe_path(rel)
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        if not rel.startswith(EDITABLE_PREFIXES):
            return self._send(403, {"error": "편집 불가 경로"})

        # 두 가지 저장 방식: raw(텍스트) 또는 data(구조 → YAML 직렬화)
        if "raw" in body:
            text = body["raw"]
            try:
                yaml.safe_load(text)  # 문법 검사
            except yaml.YAMLError as e:
                return self._send(400, {"error": f"YAML 문법 오류: {e}"})
        elif "data" in body:
            text = yaml.safe_dump(body["data"], allow_unicode=True, sort_keys=False,
                                  default_flow_style=False)
        else:
            return self._send(400, {"error": "raw 또는 data 필요"})

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        result = run_validation()
        return self._send(200, {"saved": True, "path": rel, "validation": result})


def main():
    print(f"시맨틱 레이어 관리 UI — http://localhost:{PORT}")
    print(f"원천 저장소: {REPO_ROOT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
