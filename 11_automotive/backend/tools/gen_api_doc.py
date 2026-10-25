"""라우터에서 API 목록 표 만들기 → docs/03_API_명세.md 의 "엔드포인트 목록" 부분.

쓰는 법: python tools/gen_api_doc.py > /tmp/api_table.md
FastAPI가 없으면 tests/stubs 로 import만 한다. 실제 서버에서는 /docs (OpenAPI)가 더 자세하다.
"""
import inspect
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from tests.stubs_loader import use_stubs_if_needed  # noqa: E402

use_stubs_if_needed()
os.environ.setdefault("MOM_JWT_SECRET", "doc-only")

import app.main as main  # noqa: E402
from app.routers import (alarms, assistant, auth, documents, ingest, inventory, line, maintenance,  # noqa: E402
                         master, notifications, production, qr, quality, staff, stream)

MODULES = [auth, master, line, alarms, notifications, stream, production, maintenance, inventory, qr, quality, documents,
           staff, assistant, ingest]


def who(router, fn, route=None) -> str:
    route_deps = route.get("dependencies", []) if isinstance(route, dict) else getattr(route, "dependencies", [])
    for d in list(router.dependencies) + list(route_deps or []):
        svc = getattr(getattr(d, "dependency", None), "service", None)
        if svc:
            return f"서비스 키 `{svc}`"
    for p in inspect.signature(fn).parameters.values():
        dep = getattr(p.default, "dependency", None)
        if dep is None:
            continue
        if hasattr(dep, "permission"):
            return " 또는 ".join(f"`{t}·{a}`" for t, a in dep.permission)
        if getattr(dep, "__name__", "") == "current_user":
            return "로그인"
    if fn.__name__ in ("stream",):
        return "로그인 (?token=)"
    return "없음"


def parts(route) -> tuple[str, str, object]:
    """가짜 fastapi는 dict, 진짜 FastAPI는 APIRoute"""
    if isinstance(route, dict):
        return route["method"], route["path"], route["endpoint"]
    return ",".join(sorted(route.methods - {"HEAD"})), route.path, route.endpoint


def main_():
    assert main.app is not None          # 앱 전체가 import 되는지도 함께 확인
    routes = [(r, route) for m in MODULES for r in [m.router] for route in r.routes]
    stub = "fastapi" in sys.modules and not hasattr(sys.modules["fastapi"], "__version__")
    print(f"<!-- tools/gen_api_doc.py 가 만든 표 ({len(routes)}개).{' 가짜 fastapi로 import' if stub else ''} -->")
    print("| 방법 | 경로 | 권한 (role_permission target·action) | 설명 |")
    print("|---|---|---|---|")
    for r, route in routes:
        method, path, fn = parts(route)
        doc = (inspect.getdoc(fn) or "").splitlines()
        desc = doc[0] if doc else fn.__name__
        print(f"| {method} | `{path}` | {who(r, fn, route)} | {desc} |")


if __name__ == "__main__":
    main_()
