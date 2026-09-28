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


def test_enlightenment_keys_defaults_and_sections(tmp_path):
    """Off by default (it spends a currency), 3 a day once on, no dust cap, no reserve; the
    keys load back only from their own sections, and defaults are not written."""
    s = Settings()
    assert not s.flag("GuardianEnlighten")
    assert (s.MaxEnlighten, s.MaxEnlightenDust, s.EnlightenDustReserve) == ("3", "0", "0")
    assert s.EnlightenDustDaily == "0"
    p = tmp_path / "settings.ini"
    p.write_text(
        "[PythonOptions]\nGuardianEnlighten=1\n[CommonOptions]\nMaxEnlighten=0\n"
        "MaxEnlightenDust=1000\nEnlightenDustReserve=2000\nEnlightenDustDaily=400\n",
        encoding="utf-8-sig",
    )
    s = Settings.load(str(p))
    assert s.flag("GuardianEnlighten") and s.MaxEnlighten == "0"
    assert (s.MaxEnlightenDust, s.EnlightenDustReserve, s.EnlightenDustDaily) == (
        "1000",
        "2000",
        "400",
    )
    s.set("MaxEnlighten", "3")
    s.save()
    text = p.read_text(encoding="utf-8-sig")
    assert "MaxEnlighten=" not in text and "EnlightenDustReserve=2000" in text


def test_missing_file_gives_defaults(tmp_path):
    s = Settings.load(str(tmp_path / "nope.ini"))
    assert s.flag("SellEx")


def test_save_refuses_to_overwrite_a_file_it_did_not_load(tmp_path):
    import pytest

    from firestone_bot.settings import SettingsNotLoaded

    path = str(tmp_path / "settings.ini")
    Settings(path=path).save()  # no file yet: fine
    fresh = Settings(path=path)
    with pytest.raises(SettingsNotLoaded):
        fresh.save()
    fresh.save(force=True)
    Settings.load(path).save()  # loaded: fine
