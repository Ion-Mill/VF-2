"""화면 정보판 글자는 비서로는 넘기고, 채팅 기록·접근 기록 본문에는 넣지 않는다."""
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "app" / "routers" / "assistant.py"


def test_screen_text_goes_to_assistant_not_the_log():
    text = SRC.read_text(encoding="utf-8")
    insert_args = text.split('db.scalar("assistant.chat_insert"', 1)[1].split(")", 1)[0]
    assert 'payload["screen_text"] = body.screen_text' in text
    assert "screen_text" not in insert_args
    assert 'access["screen_text_chars"] = len(body.screen_text)' in text
    assert "screen_context=body.screen_text" not in text
