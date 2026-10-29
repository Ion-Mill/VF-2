"""서비스 코드가 실제 DB(PostgreSQL)에서 도는지 — FastAPI·SQLAlchemy 없이 psql로.

필요: db/tests/run_tests.sh 로 만든 mom_test DB (스키마 + 개발 데이터 + db/roles.sql)
      MOM_TEST_PSQL="psql -h <host> -p <port>"   (없으면 이 시험은 건너뜀)
mom_test를 복사한 DB에서 돌리고 끝나면 지운다.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from app.assistant import tools
from app.domain.cmm_csv import CmmFormatError
from app.errors import AppError
from app.services import cmm, documents, records
from app.workers import cmm_watcher
from tests.psqldb import PsqlDb, PsqlError, clone_db, drop_db

PSQL = os.environ.get("MOM_TEST_PSQL")
DATA = Path(__file__).parent / "data"
EXAMPLES = ["CMM-01_LOT-2609-038-1_S01_FIRST.csv", "CMM-01_LOT-2609-038-1_S06_SAMPLE.csv",
            "CMM-01_LOT-2609-038-1_F12_ENHANCED.csv"]


@unittest.skipUnless(PSQL, "MOM_TEST_PSQL 없음 — DB 시험 건너뜀")
class DbCase(unittest.TestCase):
    DB_NAME = "mom_svc_test"

    @classmethod
    def setUpClass(cls):
        cls.psql = clone_db(PSQL, "mom_test", cls.DB_NAME)
        cls.db = PsqlDb(cls.psql)
        cls.db._run("SELECT fn_sim_set('SIM', '2026-09-15 13:00+09', 1, true)", quiet=True)

    @classmethod
    def tearDownClass(cls):
        drop_db(PSQL, cls.DB_NAME)

    def sql(self, text: str) -> list[list[str]]:
        out = self.db._run(text, quiet=True).strip().splitlines()
        return [line.split(",") for line in out[1:]]


class TestDocuments(DbCase):
    DB_NAME = "mom_svc_docs"

    def test_edit_draft_then_confirmed(self):
        v = documents.edit_shift_report(self.db, "2026-09-15-D", "U10", {"notable_text": "VF2-01 992 정지 2회"}, None)
        self.assertEqual(int(v), 1)
        self.assertEqual(self.sql("SELECT status, current_version FROM shift_report WHERE shift_id = '2026-09-15-D'"),
                         [["EDITING", "1"]])
        with self.assertRaises(AppError) as e:
            documents.edit_shift_report(self.db, "2026-09-15-D", "U10", {"notable_text": "VF2-01 992 정지 2회"}, None)
        self.assertEqual((e.exception.code, e.exception.detail["reason"]), ("VALIDATION", "NO_CHANGE"))
        # 버전이 다르면 CONFLICT_VERSION (다른 사람이 먼저 고침 — API명세서 1장)
        with self.assertRaises(AppError) as e:
            documents.edit_shift_report(self.db, "2026-09-15-D", "U10", {"notable_text": "다른 글"}, None, version=0)
        self.assertEqual((e.exception.status, e.exception.code), (409, "CONFLICT_VERSION"))
        # 확정된 9/14 야간: 사유 없으면 VALIDATION (DB도 R-35로 막음), 다른 반장은 DB가 막음, 그 교대 반장 + 사유면 REVISED
        with self.assertRaises(AppError) as e:
            documents.edit_shift_report(self.db, "2026-09-14-N", "U11", {"handover_text": "VF2-02 확인"}, None)
        self.assertEqual((e.exception.status, e.exception.code), (422, "VALIDATION"))
        with self.assertRaises(PsqlError):
            documents.edit_shift_report(self.db, "2026-09-14-N", "U10", {"handover_text": "VF2-02 확인"}, "누락")
        v = documents.edit_shift_report(self.db, "2026-09-14-N", "U11", {"handover_text": "VF2-02 확인"}, "인계 누락")
        self.assertEqual(self.sql("SELECT status FROM shift_report WHERE shift_id = '2026-09-14-N'"), [["REVISED"]])
        self.assertEqual(self.sql(f"SELECT field_name, after_value FROM document_revision_change c JOIN document_revision r "
                                  f"USING (revision_id) WHERE r.doc_key = '2026-09-14-N' AND r.version_no = {int(v)}"),
                         [["handover_text", "VF2-02 확인"]])

    def test_missing_doc(self):
        with self.assertRaises(AppError) as e:
            documents.edit_daily_report(self.db, "2026-01-01", "U12", {"issues_summary": "x"}, None)
        self.assertEqual(e.exception.status, 404)


class TestRecords(DbCase):
    DB_NAME = "mom_svc_records"

    def test_ai_draft_work_order_and_record(self):
        # 작업지시서에는 계기(알람·알림·예방 정비)가 있어야 한다 — 계기 없는 초안은 DB가 막음
        with self.assertRaises(PsqlError) as e:
            self.db.scalar("maintenance.wo_create_draft", equipment_id="VF2-02", title="x", symptom="x", alarm_event_id=None,
                           trigger_notification_id=None, pm_record_id=None, lot_no=None, steps=[], parts=[], author=None)
        self.assertIn("ck_wo_trigger", str(e.exception))
        # 초안 저장 API 자체를 시험 — 정지 알람 자동 초안(2026-10-20)은 끄고 알람만 넣는다 (자동 초안은 db/tests/96d)
        alarm = int(self.db._run("SET app.auto_work_order = 'off'; SELECT fn_ingest_alarm('VF2-02', '254')", quiet=True).splitlines()[1])
        wo = self.db.scalar("maintenance.wo_create_draft", equipment_id="VF2-02", title="알람 254 점검", symptom="과열",
                            alarm_event_id=alarm, trigger_notification_id=None, pm_record_id=None, lot_no=None,
                            steps=[{"step_text": "팬 확인", "source_section": "DOC-03 §2.9"},
                                   {"step_text": "필터 청소", "source_section": "DOC-03 §2.9"}], parts=[], author=None)
        self.assertEqual(wo, "MW-0902")
        row = records.create_work_record_full(self.db, wo, "AI", None, "과열 의심", None)
        self.assertEqual(row["record_no"], "MR-0902")
        self.assertEqual(int(row["checks"]), 9 + 2)                       # 잠금·표지 9 + 작업 순서 2
        self.assertEqual(self.sql("SELECT author_kind, version_no, status_after FROM document_revision "
                                  "WHERE doc_key = 'MR-0902'"), [["AI", "0", "AI_DRAFT"]])
        # 작업지시서 1건 = 작업기록서 1건
        with self.assertRaises(PsqlError):
            records.create_work_record_full(self.db, wo, "HUMAN", "U07")
        # 없는 작업지시서
        with self.assertRaises(AppError):
            records.create_work_record_full(self.db, "MW-0999", "HUMAN", "U07")

    def test_simple_record_with_safety_block(self):
        # 간이 기록은 알람 또는 원인 점검 요청 하나에 딸린다
        with self.assertRaises(PsqlError):
            records.create_work_record_simple(self.db, "U02", "VF2-01", "칩 제거")
        no = records.create_work_record_simple(self.db, "U02", "VF2-01", "칩 제거", alarm_event_id=1,
                                               safety_block_required=True)
        self.assertTrue(no.startswith("MR-S-09"))
        self.assertEqual(self.sql(f"SELECT count(*) FROM work_record_check WHERE record_no = '{no}' AND check_kind = 'LOTO'"),
                         [["9"]])
        self.assertEqual(self.sql(f"SELECT author_kind, author_user_id FROM document_revision WHERE doc_key = '{no}'"),
                         [["HUMAN", "U02"]])

    def test_pm_record(self):
        rid = records.create_pm_record(self.db, "U09", "PM-VF2-01-2.1-01", "2026-09-15", "NORMAL")
        self.assertEqual(self.sql(f"SELECT status, version_no FROM pm_record p JOIN document_revision r "
                                  f"ON r.doc_type = 'PM_RECORD' AND r.doc_key = p.pm_record_id::text WHERE pm_record_id = {rid}"),
                         [["DRAFT", "0"]])


class TestCmmImport(DbCase):
    DB_NAME = "mom_svc_cmm"

    def test_examples_and_duplicates(self):
        got = {}
        for name in EXAMPLES:
            r = cmm.import_text(self.db, name, (DATA / name).read_text(encoding="utf-8"), f"/test/{name}")
            got[name] = r
            self.assertIn(r["status"], ("SUCCESS", "NEEDS_CHECK"), r)
            self.assertGreater(int(r["result_count"]), 0)
        # S01 = 초품 1번 지시(시작됨)와 맞음
        self.assertEqual(got[EXAMPLES[0]]["status"], "SUCCESS", got[EXAMPLES[0]])
        # 같은 이름이 또 오면 #2로 따로 남김 (재측정)
        again = cmm.import_text(self.db, EXAMPLES[0], (DATA / EXAMPLES[0]).read_text(encoding="utf-8"), "/test/again")
        self.assertEqual(again["file_name"], EXAMPLES[0] + "#2")

    def test_format_error(self):
        before = int(self.sql("SELECT count(*) FROM notification WHERE rule_code = 'CMM_FILE_ERROR'")[0][0])
        r = cmm.import_text(self.db, "broken.csv", "#lot_no,LOT-2609-038-1\n#insp_kind,FIRST\n#part_seq,1\nchar_no,actual\n1,2\n",
                            None)
        self.assertEqual((r["status"], r["error_kind"]), ("FAILED", "FORMAT"))
        self.assertIn("cmm_judgement", r["error_text"])
        self.assertEqual(int(self.sql("SELECT count(*) FROM notification WHERE rule_code = 'CMM_FILE_ERROR'")[0][0]), before + 1)
        r = cmm.record_failure(self.db, "bad-enc.csv", None, CmmFormatError("글자 인코딩"))
        self.assertEqual(r["status"], "FAILED")

    def test_watcher_moves_files(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            inbox, ok_dir, err_dir = tmp / "inbox", tmp / "processed", tmp / "error"
            inbox.mkdir()
            shutil.copy(DATA / EXAMPLES[1], inbox / "w1.csv")
            (inbox / "w2.csv").write_text("not,a,cmm,file\n", encoding="utf-8")
            # 양식은 맞지만 없는 로트 → DB가 FAILED → 오류 칸
            (inbox / "w3.csv").write_text((DATA / EXAMPLES[0]).read_text(encoding="utf-8")
                                          .replace("LOT-2609-038-1", "LOT-2609-099-1"), encoding="utf-8")
            seen: dict = {}
            run_tx = lambda fn: fn(self.db)    # noqa: E731  psql은 쿼리마다 바로 저장
            self.assertEqual(cmm_watcher.scan_once(inbox, ok_dir, err_dir, seen, run_tx), [])   # 첫 번째: 다 써졌는지 기다림
            out = cmm_watcher.scan_once(inbox, ok_dir, err_dir, seen, run_tx)
            by_name = {Path(r["moved_to"]).name: r["status"] for r in out}
            self.assertEqual((by_name["w2.csv"], by_name["w3.csv"]), ("FAILED", "FAILED"))
            self.assertIn(by_name["w1.csv"], ("SUCCESS", "NEEDS_CHECK"))
            self.assertEqual(sorted(p.name for p in ok_dir.iterdir()), ["w1.csv"])
            self.assertEqual(sorted(p.name for p in err_dir.iterdir()), ["w2.csv", "w3.csv"])
            self.assertEqual(self.sql("SELECT original_file_ref LIKE '%/error/w3.csv' FROM cmm_import WHERE file_name = 'w3.csv'"),
                             [["t"]])
            self.assertEqual(list(inbox.iterdir()), [])
            self.assertEqual(self.sql("SELECT original_file_ref LIKE '%/processed/w1.csv' FROM cmm_import WHERE file_name = 'w1.csv'"),
                             [["t"]])
        finally:
            shutil.rmtree(tmp)


class TestAssistantReadOnly(DbCase):
    """비서 조회 도구 14개를 읽기 전용 계정(mom_ai_ro)으로 실제 실행"""
    DB_NAME = "mom_svc_ai"
    ARGS = {
        "equipment_status": {},
        "alarms": {"from": "2026-09-15T00:00:00+09:00", "to": "2026-09-16T00:00:00+09:00", "equipment_id": "VF2-01"},
        "kpi": {"from_date": "2026-09-14", "to_date": "2026-09-15"},
        "production": {"from_date": "2026-09-14", "to_date": "2026-09-15"},
        "lot": {"lot_no": "LOT-2609-041-1"},
        "work_orders": {"open_only": True},
        "work_records": {"equipment_id": "VF2-01"},
        "pm_due": {"within_days": 7},
        "tool_life": {"equipment_id": "VF2-01"},
        "inventory": {},
        "reliability": {"equipment_id": "VF2-01"},
        "stop_reasons": {"from": "2026-09-15T00:00:00+09:00", "to": "2026-09-16T00:00:00+09:00"},
        "sensor_trend": {"equipment_id": "VF2-01", "minutes": 360},
        "equipment_spec": {},
    }

    def test_all_tools_as_ai_ro(self):
        ro = PsqlDb(self.psql, prefix="SET default_transaction_read_only = on; SET ROLE mom_ai_ro; ")
        self.assertEqual(set(self.ARGS), set(tools.TOOLS))
        for name, args in self.ARGS.items():
            with self.subTest(tool=name):
                rows = tools.run(ro, name, args)
                self.assertIsInstance(rows, list)
        self.assertEqual(tools.run(ro, "alarms", self.ARGS["alarms"])[0]["equipment_id"], "VF2-01")
        self.assertEqual(len(tools.run(ro, "lot", {"lot_no": "LOT-2609-041-1"})), 1)
        prod = {r["shift_id"]: r for r in tools.run(ro, "production", self.ARGS["production"])}
        self.assertEqual(prod["2026-09-14-N"]["total_target_qty"], "90")          # 총 목표 = 목표 + 이월
        self.assertEqual(len(tools.run(ro, "equipment_spec", {})), 6)
        self.assertEqual(tools.run(ro, "reliability", {"equipment_id": "VF2-01"})[0]["failure_count"], "2")
        with self.assertRaises(PsqlError):      # 쓰기 막힘
            ro._run("UPDATE app_user SET user_name = 'x'", quiet=True)
        with self.assertRaises(PsqlError):      # 비밀번호 해시 못 읽음
            ro.all("common.user_by_id", user_id="U10")
        self.assertEqual(ro.one("common.user_public", user_id="U10")["role_code"], "SUP")

    def test_alarms_counts_split_idle_once(self):
        # 주의 등급 IDLE이 휴식을 끼면 알람 1건에 상태 기록 2줄 → 횟수는 1 (2026-10-26, LLM 담당 요청). COMMIT 없이 끝나 되돌아간다
        split = ("BEGIN; UPDATE equipment_state_log SET end_at = '2026-09-15 10:52+09' WHERE state_log_id = 1; "
                 "INSERT INTO equipment_state_log (equipment_id, state_code, start_at, end_at, alarm_event_id) VALUES "
                 "('VF2-01', 'IDLE', '2026-09-15 10:52+09', '2026-09-15 10:53+09', 1), "
                 "('VF2-01', 'IDLE', '2026-09-15 10:53+09', '2026-09-15 10:54+09', NULL), "
                 "('VF2-01', 'IDLE', '2026-09-15 10:54+09', '2026-09-15 10:55+09', 1); SET LOCAL ROLE mom_ai_ro; ")
        rows = {r["alarm_code"]: r for r in tools.run(PsqlDb(self.psql, prefix=split), "alarms", self.ARGS["alarms"])}
        self.assertEqual(rows["108"]["times"], "1")
        self.assertEqual(rows["994"]["down_min"], "2.0")


class TestScheduleQueries(DbCase):
    DB_NAME = "mom_svc_sched"

    def test_shift_and_daily_due(self):
        self.db._run("SELECT fn_sim_set('SIM', '2026-09-16 06:10+09', 1, true)", quiet=True)
        ended = [r["shift_id"] for r in self.db.all("reports.ended_shifts")]
        self.assertEqual(ended, ["2026-09-15-N"])          # 9/15 주간은 이미 초안이 있음
        self.assertEqual([r["work_date"] for r in self.db.all("reports.daily_due")], ["2026-09-15"])
        self.assertEqual(self.db.scalar("reports.shift_draft", shift_id="2026-09-15-N"), "CREATED")
        self.assertEqual(self.db.all("reports.ended_shifts"), [])
        self.assertGreaterEqual(int(self.db.scalar("reports.daily_draft", work_date="2026-09-15")), 1)
        self.assertEqual(self.db.all("reports.daily_due"), [])
        self.assertGreaterEqual(int(self.db.scalar("reports.time_rules", cmm_wait_min=10)), 0)


if __name__ == "__main__":
    unittest.main()
