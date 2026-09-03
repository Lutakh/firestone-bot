"""MapStartState.ini round trip and the MapStart memory helpers."""

from firestone_bot.state import MapState


def test_roundtrip_utf16(tmp_path):
    p = tmp_path / "MapStartState.ini"
    p.write_text("[Memory]\nSessionStart=20260831005153\nClickedPoints=\n", encoding="utf-16")
    s = MapState.load(str(p))
    assert s.session_start == "20260831005153"
    assert not s.was_clicked(384, 1009)
    s.mark_clicked(384, 1009)
    assert p.read_bytes().startswith(b"\xff\xfe")
    s2 = MapState.load(str(p))
    assert s2.was_clicked(384, 1009) and s2.clicked_points == "|384|1009|"
    s2.reset()
    assert MapState.load(str(p)).clicked_points == ""


def test_missing_file(tmp_path):
    s = MapState.load(str(tmp_path / "nope.ini"))
    assert s.session_start == "" and s.clicked_points == ""
