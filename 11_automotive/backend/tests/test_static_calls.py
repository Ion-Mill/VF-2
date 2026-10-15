"""코드가 부르는 쿼리 이름·매개변수가 app/sql/*.sql 과 맞는지 (FastAPI 없이 AST로 확인).

  · db.all/one/scalar/exec("파일.이름", k=v, ...) 의 이름이 있어야 하고
  · 넘기는 매개변수 = SQL의 :이름 (빠지거나 남으면 실패)
  · **body.model_dump() 는 같은 모듈의 Pydantic 모델 칸으로 펼쳐 본다
  · AI 비서 도구는 도구 입력 칸 = 쿼리 매개변수
"""
import ast
import unittest
from pathlib import Path

from app.assistant.tools import TOOLS
from app.sqlfiles import load_all, params_of

ROOT = Path(__file__).resolve().parents[1] / "app"
METHODS = {"all", "one", "scalar", "exec"}


def model_fields(tree: ast.Module) -> dict[str, set[str]]:
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    out: dict[str, set[str]] = {}

    def fields(name: str) -> set[str]:
        if name in out:
            return out[name]
        c = classes[name]
        f = {s.target.id for s in c.body if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)}
        for b in c.bases:
            if isinstance(b, ast.Name) and b.id in classes:
                f |= fields(b.id)
        out[name] = f
        return f

    for n in classes:
        fields(n)
    return out


def calls(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    models = model_fields(tree)
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        ann = {a.arg: a.annotation.id for a in fn.args.args if isinstance(a.annotation, ast.Name)}
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in METHODS
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
                    and "." in node.args[0].value):
                continue
            names, dynamic = set(), False
            for kw in node.keywords:
                if kw.arg:
                    names.add(kw.arg)
                elif isinstance(kw.value, ast.Dict) and all(isinstance(k, ast.Constant) for k in kw.value.keys):
                    names |= {k.value for k in kw.value.keys}
                elif (isinstance(kw.value, ast.Call) and isinstance(kw.value.func, ast.Attribute)
                      and kw.value.func.attr == "model_dump" and isinstance(kw.value.func.value, ast.Name)
                      and ann.get(kw.value.func.value.id) in models):
                    names |= models[ann[kw.value.func.value.id]]
                else:
                    dynamic = True
            yield f"{path.relative_to(ROOT.parent)}:{node.lineno}", node.args[0].value, names, dynamic


class TestQueryCalls(unittest.TestCase):
    def test_all_calls_match_sql(self):
        q = load_all()
        problems, n = [], 0
        for path in sorted(ROOT.rglob("*.py")):
            for where, name, given, dynamic in calls(path):
                n += 1
                if name not in q:
                    problems.append(f"{where} 없는 쿼리 {name}")
                    continue
                need = set(params_of(q[name]))
                if dynamic:
                    extra = given - need
                    if extra:
                        problems.append(f"{where} {name}: 남는 매개변수 {sorted(extra)}")
                elif given != need:
                    problems.append(f"{where} {name}: 빠짐 {sorted(need - given)} 남음 {sorted(given - need)}")
        self.assertGreater(n, 100, "쿼리 호출을 거의 못 찾음 — 검사 방식 확인")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_every_query_is_used(self):
        """SQL 파일에만 있고 아무도 안 부르는 쿼리 (지워도 되는지 확인용) — 정해진 목록 밖이면 실패"""
        q = load_all()
        used = {name for p in ROOT.rglob("*.py") for _, name, _, _ in calls(p)} | {t.query for t in TOOLS.values()}
        allowed_unused = {"common.now"} - used   # common.now 는 routers/common.period 에서 부름
        unused = set(q) - used - allowed_unused
        self.assertEqual(sorted(unused), [], "쓰지 않는 쿼리")

    def test_assistant_tools_params(self):
        q = load_all()
        for t in TOOLS.values():
            self.assertIn(t.query, q, t.name)
            self.assertEqual(set(t.properties), set(params_of(q[t.query])), t.name)
            self.assertTrue(set(t.required) <= set(t.properties), t.name)


if __name__ == "__main__":
    unittest.main()
