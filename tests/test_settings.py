"""settings.ini round trip (UTF-16 with BOM and UTF-8), defaults, unknown keys preserved."""

from firestone_bot.settings import Settings

SAMPLE = (
    "[CommonOptions]\nToken=1\nMail=0\nGearChestExclude=Epic and Higher\nLastCrystalReset=20260502115838\n"
    "[QoL/RareOptions]\nBeer=1\n[SettingsNoGui]\nEnableHeartbeat=0\n"
)


def test_defaults():
    s = Settings()
    assert s.get("Mail") == "1"
    assert s.flag("Mail") is True
    assert s.flag("Token") is False
    assert s.UpgradeWM == "Don't Upgrade WM's"


def _roundtrip(tmp_path, encoding):
    p = tmp_path / "settings.ini"
    p.write_text(SAMPLE, encoding=encoding)
    s = Settings.load(str(p))
    assert s.encoding == encoding
    assert s.flag("Token") and not s.flag("Mail") and s.flag("Beer")
    assert s.GearChestExclude == "Epic and Higher"
    assert s.extra["CommonOptions"]["LastCrystalReset"] == "20260502115838"
    s.set("Mail", True)
    s.save()
    raw = p.read_bytes()
    s2 = Settings.load(str(p))
    assert s2.flag("Mail") and s2.flag("Token")
    assert s2.extra["CommonOptions"]["LastCrystalReset"] == "20260502115838"
    return raw


def test_roundtrip_utf16(tmp_path):
    raw = _roundtrip(tmp_path, "utf-16")
    assert raw.startswith(b"\xff\xfe")


def test_roundtrip_utf8(tmp_path):
    raw = _roundtrip(tmp_path, "utf-8-sig")
    assert raw.startswith(b"\xef\xbb\xbf[CommonOptions]")


def test_missing_file_gives_defaults(tmp_path):
    s = Settings.load(str(tmp_path / "nope.ini"))
    assert s.flag("SellEx")
