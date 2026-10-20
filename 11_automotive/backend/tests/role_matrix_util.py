"""역할 × API 권한표 계산 도구 (tests/test_role_matrix.py 와 문서 생성에서 씀).

role_permission 시드(db/seed/20_roles_permissions.sql)를 SQL 없이 읽어 PermissionTable로 만들고,
라우터 처리기에 걸린 require(...)/require_any(...)로 역할별 통과 여부를 계산한다.
"""
import inspect
import os
import re
from pathlib import Path

from tests.stubs_loader import use_stubs_if_needed

use_stubs_if_needed()
os.environ.setdefault("MOM_JWT_SECRET", "matrix-only-" + "x" * 32)

from app.domain.permissions import Grant, PermissionTable  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("OPR", "MNT", "SUP", "MGR")
TUPLE = re.compile(r"\('(OPR|MNT|SUP|MGR)',\s*'([A-Z_]+)',\s*'([A-Z_]+)',\s*'([A-Z_]+)'\)")


def seed_table() -> PermissionTable:
    text = (ROOT / "db/seed/20_roles_permissions.sql").read_text(encoding="utf-8")
    grants = {(r, t, a): s for r, t, a, s in TUPLE.findall(text)}
    # 시드 맨 아래 "MGR은 모든 기능·문서 조회 (R-76)": 표에 나온 대상마다 MGR VIEW
    if "SELECT DISTINCT 'MGR', target, 'VIEW', 'ALL' FROM role_permission" in text:
        for t in {t for _, t, _ in grants}:
            grants.setdefault(("MGR", t, "VIEW"), "ALL")
    return PermissionTable([Grant(r, t, a, s) for (r, t, a), s in grants.items()])


def _api_routes(app):
    """(method, path, 처리기, 의존성 목록). 가짜 fastapi(tests/stubs)와 진짜 fastapi 둘 다 읽는다.
    라우터 모듈(app.routers.*)의 처리기만 — /api/health 같은 앱 직속 경로는 뺀다 (가짜 fastapi도 모으지 않음)"""
    if hasattr(app, "routers"):                  # 가짜: include_router 한 라우터를 그대로 모아 둔다, 경로는 dict
        for r in app.routers:
            for route in r.routes:
                yield route["method"], route["path"], route["endpoint"], list(r.dependencies) + list(route.get("dependencies") or [])
        return
    pending = list(app.routes)
    while pending:
        route = pending.pop(0)
        sub = getattr(route, "original_router", None)    # fastapi 0.14x: include_router 한 라우터를 _IncludedRouter로 감싼다
        if sub is not None:
            pending[0:0] = list(sub.routes)
            continue
        fn = getattr(route, "endpoint", None)
        if fn is None or not fn.__module__.startswith("app.routers.") or not getattr(route, "methods", None):
            continue
        for method in sorted(route.methods):     # 라우터 수준 의존성(dependencies=)은 진짜 fastapi가 경로마다 붙여 둔다
            yield method, route.path, fn, list(route.dependencies)


def routes():
    import app.main as main
    for method, path, fn, deps in _api_routes(main.app):
        service = next((getattr(d.dependency, "service", None) for d in deps if getattr(d.dependency, "service", None)), None)
        perm = None
        for p in inspect.signature(fn).parameters.values():
            dep = getattr(p.default, "dependency", None)
            if dep is not None and hasattr(dep, "permission"):
                perm = dep.permission
        yield method, path, fn, service, perm


def actual_matrix(table: PermissionTable) -> dict[tuple[str, str], str]:
    out = {}
    for method, path, _fn, service, perm in routes():
        if service:
            out[(method, path)] = "svc"
        elif perm is None:
            out[(method, path)] = "login"
        else:
            out[(method, path)] = "".join(r[0] if any(table.allows(r, t, a) for t, a in perm) else "." for r in ROLES)
    return out
