"""가짜 fastapi — import와 라우트 목록 수집만 (tests/stubs/README.md)."""


class _Dep:
    def __init__(self, dependency=None):
        self.dependency = dependency


def Depends(dependency=None, **_):  # noqa: N802
    return _Dep(dependency)


class _Param:
    def __init__(self, default=None, **kw):
        self.default, self.kw = default, kw


def Query(default=None, **kw):  # noqa: N802
    return _Param(default, **kw)


def Header(default=None, **kw):  # noqa: N802
    return _Param(default, **kw)


def File(default=None, **kw):  # noqa: N802
    return _Param(default, **kw)


class Request:
    pass


class UploadFile:
    pass


class APIRouter:
    def __init__(self, prefix: str = "", tags=None, dependencies=None):
        self.prefix, self.tags, self.dependencies, self.routes = prefix, tags or [], list(dependencies or []), []

    def _add(self, method: str, path: str, **kw):
        def deco(fn):
            self.routes.append({"method": method, "path": self.prefix + path, "endpoint": fn, **kw})
            return fn
        return deco

    def get(self, path, **kw):
        return self._add("GET", path, **kw)

    def post(self, path, **kw):
        return self._add("POST", path, **kw)

    def put(self, path, **kw):
        return self._add("PUT", path, **kw)

    def patch(self, path, **kw):
        return self._add("PATCH", path, **kw)

    def delete(self, path, **kw):
        return self._add("DELETE", path, **kw)


class FastAPI:
    def __init__(self, *a, **kw):
        self.routers = []

    def include_router(self, r):
        self.routers.append(r)

    def add_middleware(self, *a, **kw):
        pass

    def middleware(self, *_):
        return lambda fn: fn

    def exception_handler(self, *_):
        return lambda fn: fn

    def get(self, *a, **kw):
        return lambda fn: fn
