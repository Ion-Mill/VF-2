"""사건 버튼 번호 검사 (API-SIM-01) — 시연 서버가 누를 수 있는 버튼(생성기 config.json realtime.buttons)과 같아야 한다.

2026-10-25: 백엔드가 `^S[1346]$`만 받아 시연 서버에 있는 S7(알람 없이 작업자가 멈춤)이 422로 막혔다.
"""
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.routers.master import InjectIn

GEN_CONFIG = Path(__file__).resolve().parents[2] / "생성기" / "config.json"


class InjectCodeTest(unittest.TestCase):
    def test_buttons_accepted(self):
        for code in ("S1", "S3", "S4", "S6", "S7"):
            self.assertEqual(InjectIn(scenario_code=code).scenario_code, code)

    def test_others_rejected(self):
        for code in ("S2", "S5", "S8", "S", "s7", "S77"):      # S2·S5는 과거 기록이라 버튼 없음
            with self.assertRaises(ValidationError, msg=code):
                InjectIn(scenario_code=code)

    @unittest.skipUnless(GEN_CONFIG.exists(), "생성기 폴더 없음")
    def test_same_as_sim_buttons(self):
        buttons = json.loads(GEN_CONFIG.read_text(encoding="utf-8"))["realtime"]["buttons"]
        for code in buttons:
            self.assertEqual(InjectIn(scenario_code=code).scenario_code, code)


if __name__ == "__main__":
    unittest.main()
