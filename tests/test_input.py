"""platform.input: pynput is loaded lazily; every entry point must initialise it first."""

from firestone_bot.platform import input as inp


def test_every_entry_point_initialises_pynput(monkeypatch):
    calls = []

    class FakeKeyboard:
        def tap(self, k):
            calls.append(("tap", k))

        def press(self, k):
            calls.append(("press", k))

        def release(self, k):
            calls.append(("release", k))

    class FakeMouse:
        position = (0, 0)

        def click(self, b):
            calls.append(("click", b))

        def scroll(self, dx, dy):
            calls.append(("scroll", dy))

    class Button:
        left = "L"
        right = "R"

    def fake_ensure():
        inp._keyboard = FakeKeyboard()
        inp._mouse = FakeMouse()
        inp._Button = Button
        inp._KEYS.update({"alt": "ALT", "enter": "ENTER"})

    monkeypatch.setattr(inp, "_keyboard", None)
    monkeypatch.setattr(inp, "_mouse", None)
    monkeypatch.setattr(inp, "_Button", None)
    monkeypatch.setattr(inp, "_ensure", fake_ensure)
    inp.key("m")
    inp.key_down("left")
    inp.key_up("left")
    inp.hotkey("alt", "enter")
    inp.move(1, 2)
    inp.click()
    inp.wheel(-2, interval=0)
    assert ("tap", "m") in calls and ("press", "ALT") in calls and ("release", "ENTER") in calls
    assert ("click", "L") in calls and calls.count(("scroll", -1)) == 2
