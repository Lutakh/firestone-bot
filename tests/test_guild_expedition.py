"""Guild expedition: an INFO line for each visit, and the dot gone once the dialog is closed
tells that an expedition started.

The fake guild map: the expeditions dot, the expeditions dialog over it (the dot cannot be
read while it is open) and a Start button that starts an expedition after `starts_needed`
clicks (2, the usual case: the first claims the finished one; 3: a reward pop-up to close
took one more).
"""

import pytest

from firestone_bot.features import guild
from firestone_bot.settings import Settings
from firestone_bot.vision import atlas

GUILD_ICON = object()


class FakeGuildMap:
    def __init__(self, tmp_path, dot=True, starts_needed=2, switch=True):
        self.settings = Settings(path=str(tmp_path / "settings.ini"), loaded=True)
        self.settings.set("GuildExpedition", switch)
        self.dot = dot
        self.starts_needed = starts_needed
        self.flicker = 0  # reads of a gone dot that still see red while the dialog fades
        self.dialog = False
        self.taps = []
        self.clicks = 0
        self.reads = 0
        self.heartbeats = []
        self.lines = []
        self.captures = []

    def found(self, probe):
        assert probe is atlas.GUILD_EXPEDITION_DOT
        assert not self.dialog, "the dot is read under the expeditions dialog"
        self.reads += 1
        if self.flicker and not self.dot:
            self.flicker -= 1
            return True
        return self.dot

    def tap(self, point, settle_ms=1500, expect=None):
        self.taps.append(point)
        if point is atlas.GUILD_EXPEDITIONS:
            self.dialog = True
        elif point is atlas.GUILD_EXPEDITION_START:
            self._start()
        elif point is not GUILD_ICON:
            raise AssertionError(point)

    def _start(self):
        assert self.dialog
        self.starts_needed -= 1
        if self.starts_needed <= 0:
            self.dot = False

    def close(self):
        self.dialog = False

    def click(self):  # where the pointer is: on Start
        self.clicks += 1
        self._start()

    def sleep(self, ms):
        pass

    def wait_still(self, max_ms=1500):
        return True

    def heartbeat(self, msg, is_stop=False, important=False):
        self.heartbeats.append(msg)

    def status(self, text):
        self.lines.append(text)

    def save_diagnostic(self, name):
        self.captures.append(name)


@pytest.fixture
def guild_map(monkeypatch, tmp_path):
    def make(cls=None, **kw):
        g = (cls or FakeGuildMap)(tmp_path, **kw)
        monkeypatch.setattr(guild, "big_close", lambda game: game.close())
        return g

    return make


def _opened(g):
    return g.taps.count(atlas.GUILD_EXPEDITIONS)


def test_a_started_expedition_is_logged(guild_map):
    g = guild_map()
    assert guild.expedition(g) == "started"
    assert _opened(g) == 1 and g.clicks == 1  # the AHK double click on Start
    assert any("claiming the finished one" in s for s in g.lines)
    assert "Guild expedition: started (the dot is gone)" in g.lines
    assert g.heartbeats == ["Guild expedition start"]
    assert g.captures == []


def test_no_dot_logs_one_line_and_clicks_nothing(guild_map):
    g = guild_map(dot=False)
    assert guild.expedition(g) == "none"
    assert g.taps == []
    assert g.lines == ["Guild expedition: no dot, nothing to claim or start"]
    assert g.heartbeats == []


def test_switch_off_reads_nothing_and_logs_nothing(guild_map):
    g = guild_map(switch=False)
    assert guild.expedition(g) == "off"
    assert g.reads == 0 and g.taps == [] and g.lines == []


def test_start_is_clicked_once_more_when_the_dot_stays(guild_map):
    g = guild_map(starts_needed=3)  # claim, reward closed, then the start
    assert guild.expedition(g) == "started"
    assert _opened(g) == 2
    assert g.clicks == 1  # the retry is a single click on Start
    assert "Guild expedition: started on the second try" in g.lines
    assert g.captures == []


def test_a_dot_that_stays_is_reported_with_a_capture(guild_map):
    g = guild_map(starts_needed=99)
    assert guild.expedition(g) == "failed"
    assert _opened(g) == 2
    assert g.captures == ["guild-expedition-not-started.png"]
    assert any("still there after two tries" in s for s in g.lines)


def test_one_frame_of_the_closing_dialog_does_not_decide(guild_map):
    g = guild_map()
    g.flicker = 1  # one frame after the close still shows red where the dot was
    assert guild.expedition(g) == "started"
    assert _opened(g) == 1


class GuildVisit(FakeGuildMap):
    """guild() with every other guild feature off."""

    progress = None
    style = "classic"

    class ms:
        guild_icon = GUILD_ICON

    def focus(self):
        pass

    def locked(self, feature):
        return False


def test_the_guild_visit_runs_the_expedition(guild_map):
    visit = guild_map(cls=GuildVisit)
    for name in ("Awaken", "Chaos", "Crystal", "PTree", "GNotif"):
        visit.settings.set(name, 0)
    visit.settings.set("Pickaxes", 1)  # 1 = skip the pickaxe claim
    guild.guild(visit)
    assert "Guild expedition: started (the dot is gone)" in visit.lines
