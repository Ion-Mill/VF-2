"""DB 없이 도는 순수 로직: 비밀번호·토큰·권한표·비서 도구 입력 확인·감시 파일 이름."""
import datetime as dt
import re
import tempfile
import unittest
from pathlib import Path

import jwt

from app.assistant import tools
from app.domain.passwords import DUMMY_HASH, hash_password, verify_password
from app.domain.permissions import Grant, PermissionTable
from app.domain.tokens import create_token, decode_token
from app.domain import synthetic
from app.domain.events import event_names, visible_events
from app import errors
from app.errors import AppError
from app.workers.cmm_watcher import classify, free_path

DATA = Path(__file__).parent / "data"


class TestPasswords(unittest.TestCase):
    def test_roundtrip(self):
        h = hash_password("비밀번호123!")
        self.assertTrue(h.startswith("scrypt$16384$8$1$"))
        self.assertTrue(verify_password("비밀번호123!", h))
        self.assertFalse(verify_password("비밀번호123", h))

    def test_salt_differs(self):
        self.assertNotEqual(hash_password("x1"), hash_password("x1"))

    def test_bad_inputs(self):
        self.assertFalse(verify_password("a", None))
        self.assertFalse(verify_password("a", "md5$abc"))
        self.assertFalse(verify_password("a", "scrypt$broken"))
        self.assertFalse(verify_password("", DUMMY_HASH))
        with self.assertRaises(ValueError):
            hash_password("")


class TestTokens(unittest.TestCase):
    def test_roundtrip(self):
        t = create_token("U10", "SUP", "s" * 32, 60)
        c = decode_token(t, "s" * 32)
        self.assertEqual((c["sub"], c["role"]), ("U10", "SUP"))

    def test_expired_and_wrong_secret(self):
        old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)
        with self.assertRaises(jwt.ExpiredSignatureError):
            decode_token(create_token("a", "OPR", "s" * 32, 60, now=old), "s" * 32)
        with self.assertRaises(jwt.InvalidSignatureError):
            decode_token(create_token("a", "OPR", "s" * 32, 60), "t" * 32)


class TestPermissions(unittest.TestCase):
    def setUp(self):
        self.t = PermissionTable([Grant("SUP", "SHIPMENT", "CONFIRM", "ALL"),
                                  {"role_code": "OPR", "target": "REVISION_HISTORY", "action": "VIEW", "scope": "OWN"}])

    def test_scope(self):
        self.assertEqual(self.t.scope("SUP", "SHIPMENT", "CONFIRM"), "ALL")
        self.assertEqual(self.t.scope("OPR", "REVISION_HISTORY", "VIEW"), "OWN")
        self.assertIsNone(self.t.scope("OPR", "SHIPMENT", "CONFIRM"))
        self.assertFalse(self.t.allows("MNT", "SHIPMENT", "CONFIRM"))
        self.assertEqual(self.t.targets("SUP"), {"SHIPMENT": ["CONFIRM"]})


def seed_table() -> PermissionTable:
    """db/seed/20_roles_permissions.sql 의 권한 행 + MGR 전부 보기 (R-76) — DB 없이 권한표를 읽는다"""
    sql = (Path(__file__).parents[1] / "db/seed/20_roles_permissions.sql").read_text(encoding="utf-8")
    rows = [Grant(*m) for m in re.findall(r"\('(OPR|MNT|SUP|MGR)','([A-Z_]+)','([A-Z]+)','([A-Z_]+)'\)", sql)]
    rows += [Grant("MGR", t, "VIEW", "ALL") for t in {g.target for g in rows}]
    return PermissionTable(rows)


class TestPermissionMatrix(unittest.TestCase):
    """역할 4개의 권한이 기획서 13.1·13.2 표와 API명세서 권한 칸대로인가 (○ = 할 수 있음, - = 못 함)"""
    MATRIX = [
        # 대상, 동작,                     OPR  MNT  SUP  MGR
        ("GUIDE_CARD", "VIEW",            "○", "○", "○", "○"),
        ("WORK_ORDER", "VIEW",            "○", "○", "○", "○"),
        ("WORK_ORDER", "EDIT",            "-", "○", "-", "-"),
        ("WORK_ORDER", "ASSIGN",          "-", "-", "○", "-"),
        ("WORK_ORDER", "APPROVE",         "-", "-", "○", "-"),     # 반장만
        ("WORK_ORDER", "CANCEL",          "-", "-", "-", "-"),     # 취소는 두지 않음
        ("WORK_RECORD", "CONFIRM",        "-", "○", "-", "-"),
        ("WORK_RECORD", "CHECK",          "-", "-", "○", "-"),
        ("WORK_RECORD", "VIEW",           "-", "○", "○", "○"),     # OPR은 간이 기록만
        ("WORK_RECORD_SIMPLE", "CONFIRM", "○", "○", "-", "-"),
        ("PM_RECORD", "VIEW",             "-", "○", "○", "○"),     # 13.1 OPR "—"
        ("PM_RECORD", "CONFIRM",          "-", "○", "-", "-"),
        ("PM_SCHEDULE", "VIEW",           "○", "○", "○", "○"),     # API PM-01 "전"
        ("SHIFT_REPORT", "VIEW",          "○", "○", "○", "○"),
        ("SHIFT_REPORT", "CONFIRM",       "-", "-", "○", "-"),     # 그 교대 반장만 (처리기·R-36)
        ("DAILY_REPORT", "VIEW",          "-", "○", "○", "○"),
        ("DAILY_REPORT", "CONFIRM",       "-", "-", "-", "○"),
        ("SHIPMENT", "VIEW",              "○", "○", "○", "○"),
        ("SHIPMENT", "CONFIRM",           "-", "-", "○", "-"),
        ("INTERNAL_DOC", "APPROVE",       "-", "-", "-", "○"),
        ("FIELD_VIEW", "VIEW",            "○", "○", "○", "○"),
        ("LINE_VIEW", "VIEW",             "○", "○", "○", "○"),
        ("ASSISTANT", "INPUT",            "○", "○", "○", "○"),
        ("DOWNTIME_REASON", "INPUT",      "○", "○", "-", "-"),
        ("DOWNTIME_REASON", "CONFIRM",    "-", "-", "○", "-"),
        ("LOT_HOLD", "INPUT",             "-", "-", "○", "○"),
        ("LOT_SCRAP", "APPROVE",          "-", "-", "-", "○"),
        ("INV_RECEIPT", "INPUT",          "-", "○", "○", "-"),     # 관리 품목만 (OWNED_ITEMS, R-77)
        ("MATERIAL_CHECK", "INPUT",       "-", "-", "○", "-"),
        ("SAFETY_STOCK", "SETTING",       "-", "-", "-", "○"),
        ("TOOL_CHANGE", "INPUT",          "○", "○", "-", "-"),
        ("QUALITY", "VIEW",               "○", "○", "○", "○"),     # API QLT-01·04·05 "전"
        ("QUALITY", "INPUT",              "○", "-", "-", "-"),     # 측정 담당 작업자 (처리기가 OP-50 확인)
        ("QUALITY", "CHECK",              "-", "-", "○", "-"),
        ("SETTINGS", "SETTING",           "-", "-", "-", "○"),
        ("STAFF", "VIEW",                 "-", "-", "-", "○"),     # 직원 관리 (2026-10-25, NFR-SEC-04)
        ("STAFF", "EDIT",                 "-", "-", "-", "○"),
    ]

    def test_matrix(self):
        t = seed_table()
        for target, action, *marks in self.MATRIX:
            for role, mark in zip(("OPR", "MNT", "SUP", "MGR"), marks):
                with self.subTest(role=role, target=target, action=action):
                    self.assertEqual(t.allows(role, target, action), mark == "○")

    def test_scopes(self):
        t = seed_table()
        self.assertEqual(t.scope("OPR", "BRIEFING", "VIEW"), "SUMMARY")           # 작업자는 요약 브리핑
        self.assertEqual(t.scope("OPR", "REVISION_HISTORY", "VIEW"), "OWN")       # 자기 문서 이력만
        self.assertEqual(t.scope("SUP", "WORK_ORDER", "APPROVE"), "ALL")
        self.assertIsNone(t.scope("MGR", "WORK_ORDER", "APPROVE"))
        self.assertIsNone(t.scope("MGR", "WORK_ORDER", "CANCEL"))
        self.assertIsNone(t.scope("SUP", "WORK_ORDER", "CANCEL"))
        self.assertEqual(t.scope("SUP", "INV_RECEIPT", "INPUT"), "OWNED_ITEMS")

    def test_live_events_by_role(self):
        """실시간 사건도 역할별로 거른다 — 받은 사람만 긴급 팝업, 볼 수 없는 문서는 안 보냄"""
        t = seed_table()
        urgent = {"table": "notification", "op": "INSERT", "id": "7", "importance": "URGENT"}
        self.assertEqual(visible_events(urgent, "MNT", t, received=True), ["urgent_popup", "notification"])
        self.assertEqual(visible_events(urgent, "OPR", t, received=False), [])
        self.assertEqual(visible_events(urgent, "MGR", t, received=False), ["notification"])   # 목록 갱신만
        daily = {"table": "document_revision", "op": "INSERT", "id": "2026-09-15", "doc_type": "DAILY_REPORT"}
        self.assertEqual(visible_events(daily, "OPR", t), [])
        self.assertEqual(visible_events(daily, "MNT", t), ["document_changed"])
        staff = {"table": "document_revision", "op": "INSERT", "id": "U02", "doc_type": "APP_USER"}   # 직원 배치 (2026-10-25)
        self.assertEqual([r for r in ("OPR", "MNT", "SUP", "MGR") if visible_events(staff, r, t)], ["MGR"])
        full = {"table": "work_record", "op": "UPDATE", "id": "MR-0901", "status": "CONFIRMED"}
        self.assertEqual(visible_events(full, "OPR", t), ["kpi_updated"])                  # 정식 기록은 못 봄
        simple = dict(full, id="MR-S-0901")
        self.assertEqual(visible_events(simple, "OPR", t), ["kpi_updated", "document_changed"])
        state = {"table": "equipment_state_log", "op": "INSERT", "id": "1"}
        for role in ("OPR", "MNT", "SUP", "MGR"):
            self.assertEqual(visible_events(state, role, t), ["state_changed"])
        self.assertEqual(visible_events({"table": "*", "op": "RESYNC"}, "OPR", t), ["connection"])


class TestAssistantTools(unittest.TestCase):
    def test_schema_shape(self):
        s = tools.schemas()
        self.assertEqual(len(s), 14)
        for x in s:
            self.assertEqual(set(x), {"name", "description", "input_schema"})
            self.assertFalse(x["input_schema"]["additionalProperties"])

    def test_validate(self):
        a = tools.validate(tools.TOOLS["kpi"], {"from_date": "2026-09-14", "to_date": "2026-09-15"})
        self.assertEqual(a["from_date"], dt.date(2026, 9, 14))
        self.assertIsNone(a["equipment_id"])
        al = tools.validate(tools.TOOLS["alarms"], {"from": "2026-09-15T08:00", "to": "2026-09-15T17:00+09:00"})
        self.assertEqual(al["from"].utcoffset(), dt.timedelta(hours=9))     # 시간대 없으면 한국 시간
        st = tools.validate(tools.TOOLS["sensor_trend"], {"equipment_id": "VF2-01", "minutes": "30"})
        self.assertEqual((st["minutes"], st["sensor_code"]), (30, None))

    def test_reject(self):
        cases = [("kpi", {"from_date": "2026-09-14"}),                                   # 필수 빠짐
                 ("kpi", {"from_date": "2026-01-01", "to_date": "2026-09-15"}),          # 31일 넘음
                 ("kpi", {"from_date": "2026-09-15", "to_date": "2026-09-14"}),          # 거꾸로
                 ("kpi", {"from_date": "x", "to_date": "2026-09-14"}),                   # 형식
                 ("kpi", {"from_date": "2026-09-14", "to_date": "2026-09-15", "sql": "1"}),   # 모르는 칸
                 ("kpi", {"from_date": "2026-09-14", "to_date": "2026-09-15", "shift_type": "EVE"}),
                 ("pm_due", {"within_days": 400}),
                 ("sensor_trend", {"minutes": 60}),                                       # 설비 빠짐
                 ("sensor_trend", {"equipment_id": "VF2-01", "minutes": 0}),             # 1~360분
                 ("sensor_trend", {"equipment_id": "VF2-01", "minutes": 1000}),
                 ("stop_reasons", {"from": "2026-08-01T00:00", "to": "2026-09-15T00:00"})]
        for name, args in cases:
            with self.subTest(name=name, args=args), self.assertRaises(AppError):
                tools.validate(tools.TOOLS[name], args)


class TestEventsAndErrors(unittest.TestCase):
    def test_event_names(self):
        """실시간 사건 이름 (API명세서 3장)"""
        self.assertEqual(event_names({"table": "equipment_state_log", "op": "INSERT"}), ["state_changed"])
        self.assertEqual(event_names({"table": "notification", "op": "INSERT", "importance": "URGENT"}),
                         ["urgent_popup", "notification"])
        self.assertEqual(event_names({"table": "notification", "op": "UPDATE", "importance": "URGENT"}), ["notification"])
        self.assertEqual(event_names({"table": "work_record", "op": "UPDATE"}), ["kpi_updated", "document_changed"])
        self.assertEqual(event_names({"table": "*", "op": "RESYNC"}), ["connection"])

    def test_synthetic_marker(self):
        """모든 운영 데이터 응답에 is_synthetic (API명세서 1장) — 객체는 맨 위, 목록은 줄마다"""
        self.assertEqual(synthetic.mark({"a": 1}, True), {"a": 1, "is_synthetic": True})
        self.assertEqual(synthetic.mark([{"a": 1}, 2], True), [{"a": 1, "is_synthetic": True}, 2])
        self.assertEqual(synthetic.mark({"is_synthetic": False}, True), {"is_synthetic": False})
        self.assertTrue(synthetic.applies("/api/line/twin"))
        for path in ("/api/auth/login", "/api/me", "/api/health", "/api/stream/events", "/api/ingest/alarms",
                     "/api/assistant/tools/kpi", "/docs"):
            self.assertFalse(synthetic.applies(path), path)

    def test_error_codes_are_spec_codes(self):
        """오류 코드는 API명세서 1장의 7개만 (500 내부 오류 제외)"""
        self.assertEqual(len(errors.CODES), 7)
        self.assertTrue({c for _, c, _ in errors.SQLSTATE_MAP.values()} <= set(errors.CODES))
        self.assertTrue(set(errors.HTTP_STATUS_CODE.values()) <= set(errors.CODES))
        used = set()
        for path in Path(__file__).resolve().parent.parent.joinpath("app").rglob("*.py"):
            used |= set(re.findall(r'AppError\(\d+, "([A-Z_]+)"', path.read_text(encoding="utf-8")))
        self.assertTrue(used <= set(errors.CODES), used - set(errors.CODES))


class TestWatcherHelpers(unittest.TestCase):
    def test_free_path(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "a.csv").write_text("x")
            (p / "a_2.csv").write_text("x")
            self.assertEqual(free_path(p, "a.csv").name, "a_3.csv")
            self.assertEqual(free_path(p, "b.csv").name, "b.csv")

    def test_classify(self):
        text, err = classify((DATA / "CMM-01_LOT-2609-038-1_S01_FIRST.csv").read_bytes())
        self.assertIsNone(err)
        self.assertIn("#lot_no", text)
        text, err = classify("char_no,actual\n1,2\n".encode("cp949"))
        self.assertIsNotNone(err)
        self.assertEqual(err.error_kind, "FORMAT")


if __name__ == "__main__":
    unittest.main()
