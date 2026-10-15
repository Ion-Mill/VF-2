"""CMM 결과 파일 읽기 시험 — 사용자 폴더 Claude outputs/ 의 예시 3개(그대로 복사한 tests/data/)와 깨진 변형."""
import unittest
from pathlib import Path

from app.domain.cmm_csv import CmmFormatError, parse, part_seq_from_sample

DATA = Path(__file__).parent / "data"


class TestExamples(unittest.TestCase):
    def test_first(self):
        h, rows = parse((DATA / "CMM-01_LOT-2609-038-1_S01_FIRST.csv").read_text(encoding="utf-8"))
        self.assertEqual(h["lot_no"], "LOT-2609-038-1")
        self.assertEqual(h["insp_kind"], "FIRST")
        self.assertEqual(h["part_seq"], 1)            # sample_no S01 → 1 ([선택 필요] 규칙)
        self.assertEqual(h["part_temp_c"], "23.8")
        self.assertIs(h["temp_comp"], True)
        self.assertEqual(h["measured_at"], "2026-09-15T08:41:20+09:00")
        self.assertEqual([r["item_seq"] for r in rows], [1, 2, 3, 4, 5, 8])
        self.assertTrue(all(r["position"] is None for r in rows))   # 표준 위치 = 빈칸(None) (논리 ERD 5.F.4, 2026-10-14)
        self.assertEqual(rows[0]["actual"], "45.011")  # 숫자 글자를 그대로 (소수 정밀도 유지)
        self.assertEqual(h["cte_um_per_m_k"], "23.6")  # 양식에 없는 칸도 머리에 남김

    def test_sample_fail_row(self):
        h, rows = parse((DATA / "CMM-01_LOT-2609-038-1_S06_SAMPLE.csv").read_text(encoding="utf-8"))
        self.assertEqual(h["part_seq"], 6)
        self.assertEqual(rows[0]["cmm_judgement"], "FAIL")
        self.assertEqual(rows[0]["actual"], "45.027")

    def test_enhanced_positions(self):
        h, rows = parse((DATA / "CMM-01_LOT-2609-038-1_F12_ENHANCED.csv").read_text(encoding="utf-8"))
        self.assertEqual(h["insp_kind"], "ENHANCED")
        self.assertEqual(h["part_seq"], 12)
        item1 = [r["position"] for r in rows if r["item_seq"] == 1]
        self.assertEqual(item1, [None, "TOP", "MID", "BOTTOM"])    # 옛 표기 STD·BOT도 받아 새 코드로
        self.assertEqual(len(rows), 9)


class TestGeneratorFlat(unittest.TestCase):
    """생성기 10/1 실시간 cmm_drop 양식 (머리 값이 줄마다 되풀이되는 평평한 표, 2026-10-14)"""
    TEXT = ("lot_no,part_seq,insp_kind,program_name_rev,item_seq,position,nominal,upper_tol,lower_tol,measured_value,judgement,"
            "instrument_id,measure_start_at,measure_end_at,part_temp_c,machine_temp_c,temp_comp_on\r\n"
            "LOT-2609-128-2,1,ENHANCED,BRK-A100_OP50 Rev.0,1,TOP,45,0.025,0,45.011,PASS,CMM-01,2026-10-01T16:14:00+09:00,"
            "2026-10-01T16:19:00+09:00,24.9,20,true\r\n"
            "LOT-2609-128-2,1,ENHANCED,BRK-A100_OP50 Rev.0,1,MID,45,0.025,0,45.012,PASS,CMM-01,2026-10-01T16:14:00+09:00,"
            "2026-10-01T16:19:00+09:00,24.9,20,true\r\n"
            "LOT-2609-128-2,1,ENHANCED,BRK-A100_OP50 Rev.0,2,,150,0.5,-0.5,150.072,PASS,CMM-01,2026-10-01T16:14:00+09:00,"
            "2026-10-01T16:19:00+09:00,24.9,20,true\r\n")

    def test_flat(self):
        h, rows = parse(self.TEXT)
        self.assertEqual((h["lot_no"], h["part_seq"], h["insp_kind"], h["cmm_id"]), ("LOT-2609-128-2", 1, "ENHANCED", "CMM-01"))
        self.assertIs(h["temp_comp"], True)
        self.assertEqual(h["measured_at"], "2026-10-01T16:19:00+09:00")
        self.assertEqual([(r["item_seq"], r["position"], r["actual"]) for r in rows],
                         [(1, "TOP", "45.011"), (1, "MID", "45.012"), (2, None, "150.072")])

    def test_flat_mixed_header(self):
        with self.assertRaises(CmmFormatError):
            parse(self.TEXT.replace("LOT-2609-128-2,1,ENHANCED,BRK-A100_OP50 Rev.0,2,", "LOT-2609-128-2,2,ENHANCED,BRK-A100_OP50 Rev.0,2,"))


class TestBroken(unittest.TestCase):
    BASE = (DATA / "CMM-01_LOT-2609-038-1_S01_FIRST.csv").read_text(encoding="utf-8")

    def assertFormat(self, text, needle):
        with self.assertRaises(CmmFormatError) as cm:
            parse(text)
        self.assertEqual(cm.exception.error_kind, "FORMAT")
        self.assertIn(needle, cm.exception.text)

    def test_missing_column(self):
        self.assertFormat(self.BASE.replace(",actual,", ",value,"), "열 빠짐")

    def test_not_number(self):
        self.assertFormat(self.BASE.replace("45.011", "45.O11"), "숫자 아님")

    def test_unknown_position(self):
        self.assertFormat(self.BASE.replace("부싱 압입 구멍 지름 Ø45 H7,STD", "부싱 압입 구멍 지름 Ø45 H7,LEFT"), "측정 위치")

    def test_missing_lot(self):
        self.assertFormat(self.BASE.replace("#lot_no,LOT-2609-038-1\n", ""), "lot_no")

    def test_bad_lot_format(self):
        self.assertFormat(self.BASE.replace("LOT-2609-038-1", "LOT-38"), "로트 번호")

    def test_naive_time(self):
        self.assertFormat(self.BASE.replace("2026-09-15T08:41:20+09:00", "2026-09-15T08:41:20"), "시간대")

    def test_duplicate_row(self):
        lines = self.BASE.splitlines()
        self.assertFormat("\n".join(lines + [lines[-1]]), "두 번")

    def test_empty_table(self):
        self.assertFormat("\n".join(l for l in self.BASE.splitlines() if l.startswith("#")), "측정 표")

    def test_bom_and_korean_aliases(self):
        text = "﻿" + self.BASE.replace("#insp_kind,FIRST", "#insp_kind,초품").replace("#temp_comp,ON", "#temp_comp,켬")
        h, _ = parse(text)
        self.assertEqual(h["insp_kind"], "FIRST")
        self.assertIs(h["temp_comp"], True)

    def test_explicit_part_seq_wins(self):
        h, _ = parse(self.BASE.replace("#sample_no,S01", "#sample_no,S01\n#part_seq,5"))
        self.assertEqual(h["part_seq"], 5)

    def test_part_seq_rule(self):
        self.assertEqual(part_seq_from_sample("F12"), 12)
        self.assertIsNone(part_seq_from_sample("X"))


if __name__ == "__main__":
    unittest.main()
