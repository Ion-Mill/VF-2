"""목소리 샘플 만들기 — 같은 문장을 목소리·속도를 바꿔 목소리샘플/ 에 저장한다 (2026-10-23).
edge-tts는 Microsoft 신경망 음성이라 인터넷이 필요하고 문장이 Microsoft로 나간다 (가상 시연 문장뿐).
쓰는 법: .venv 의 python 으로 tools/make_voice_samples.py 를 실행
"""
import asyncio
from pathlib import Path

import edge_tts

OUT = Path(__file__).resolve().parents[1] / "목소리샘플"
# 화면 글자 → 읽는 소리 (스크립트 2장 읽는 법 표)
TEXT = ("로그인하면 공장 전체가 쓰리디로 나타납니다. 엔진 마운트 브래킷을 만드는, 다섯 공정이 이어진 하나의 라인입니다. "
        "아홉 시 오십칠 분, 브이에프 투 영일 공구 수명 한계, 삼육이 주의 알림이 저절로 떴습니다. "
        "초안은 비서가 쓰고, 승인과 확정은 모두 사람이 합니다.")
VOICES = [("여", "SunHi", "ko-KR-SunHiNeural"), ("남", "InJoon", "ko-KR-InJoonNeural")]
RATES = [("1_느리게-5", "-5%"), ("2_빠르게+15", "+15%"), ("3_빠르게+25", "+25%")]


async def main():
    OUT.mkdir(exist_ok=True)
    for sex, name, voice in VOICES:
        for tag, rate in RATES:
            f = OUT / f"{sex}_{name}_{tag}.mp3"
            await edge_tts.Communicate(TEXT, voice, rate=rate).save(str(f))
            print(f.name, f.stat().st_size // 1024, "KB")


asyncio.run(main())
