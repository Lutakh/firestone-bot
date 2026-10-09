"""Research priorities (owner request 2026-09-28): the scan's geometry, the tree layouts and the
choice of a research, on synthetic scans (no game, no image)."""

import re

import pytest

from firestone_bot.features import research
from firestone_bot.features.research import Box, Chooser, Seen
from firestone_bot.settings import Settings
from firestone_bot.vision import blobs


def _is_start(line: str) -> bool:
    """The owner's log watcher: a start line has "started" and none of no / not / nothing."""
    return bool(re.search(r"\bstarted\b", line)) and not re.search(r"\b(no|not|nothing)\b", line)


def xiii(**states):
    """Tree XIII as the owner had it on 2026-09-28 (column 1 Rage Heroes ... column 8), every
    box's state overridable by name; state "hidden" leaves the box out (a locked column)."""
    base = {
        "Rage Heroes": (1, 2, "available"),
        "Energy Heroes": (2, 1, "available"),
        "Mana Heroes": (2, 3, "available"),
        "Attribute Health": (3, 0, "maxed"),
        "Attribute Armor": (3, 2, "maxed"),
        "Attribute Damage": (3, 4, "running"),
        "Guardian Power": (4, 2, "running"),
        "Expose Weakness": (5, 1, "maxed"),
        "Powerless Boss": (5, 3, "maxed"),
        "Weaklings": (6, 1, "maxed"),
        "Powerless Enemy": (6, 3, "maxed"),
        "Leadership": (7, 1, "maxed"),
        "Team Bonus": (7, 3, "maxed"),
        "Raining Gold": (8, 0, "maxed"),
        "Firestone Effect": (8, 2, "maxed"),
        "All Main Attributes": (8, 4, "maxed"),
    }
    out = []
    for name, (col, row, state) in base.items():
        state = states.get(name, state)
        if state != "hidden":
            out.append(Box(col, row, name, state))
    return out


class Run:
    """A Chooser over synthetic boxes; `outcomes` = what a tap on each box gives (default
    "started")."""

    def __init__(
        self,
        boxes,
        priorities,
        any_other=True,
        outcomes=None,
        reach=None,
        cands=None,
        started=None,
    ):
        self.tapped = []
        self.said = []
        self.outcomes = outcomes or {}
        self.boxes = boxes
        cands = research.matching_layouts(boxes) if cands is None else cands
        prios = [(i, n) for i, n in enumerate(priorities, start=1) if n]
        self.chooser = Chooser(
            boxes, cands, prios, any_other, self.attempt, self.say, reach, started
        )

    def attempt(self, box):
        self.tapped.append(box.name or (box.col, box.row))
        return self.outcomes.get(box.name or (box.col, box.row), "started")

    def say(self, key, text):
        self.said.append(text)

    def choose(self):
        return self.chooser.choose()


# --- layouts ----------------------------------------------------------------------------------


def test_trees_of_the_same_content_are_one_layout():
    by_tree = {t: lay for lay in research.layouts() for t in lay.trees}
    assert len(research.layouts()) == 10
    assert by_tree["10"] is by_tree["13"] is by_tree["16"] is by_tree["19"] is by_tree["A"]
    assert by_tree["8"] is by_tree["11"] is by_tree["17"] is by_tree["20"] is by_tree["B"]
    assert by_tree["9"] is by_tree["21"] is by_tree["C"]
    assert by_tree["10"].label == "X/XIII/XVI/XIX/..."
    assert by_tree["1"].label == "I"


def test_the_owners_tree_is_found_from_what_the_scan_saw():
    cands = research.matching_layouts(xiii())
    assert len(cands) == 1 and "13" in cands[0].trees
    line = research.summary(xiii(), cands)
    assert line == (
        "Research: tree like X/XIII/XVI/XIX/..., 16 boxes (3 available, 2 running, 11 maxed)"
    )


def test_a_box_out_of_its_layout_place_rules_the_layout_out():
    boxes = xiii()
    boxes[0] = Box(1, 0, "Rage Heroes", "available")  # top of a 3-box column: no such tree
    assert research.matching_layouts(boxes) == []
    assert research.summary(boxes, []).startswith("Research: tree layout unknown, 16 boxes")


def test_unidentified_boxes_still_count_by_their_place():
    """A box of unknown name at the top of column 1: only the trees whose first column has
    three boxes remain."""
    labels = {lay.label for lay in research.matching_layouts([Box(1, 0, None, "maxed")])}
    assert labels == {"II", "V", "VIII/XI/XIV/XVII/XX/..."}


def test_what_ambiguous_layouts_agree_on():
    """Column 1 = Armor / Health / Damage: trees V and VIII (and its repeats)."""
    boxes = [
        Box(1, 0, "Attribute Armor", "maxed"),
        Box(1, 2, "Attribute Health", "maxed"),
        Box(1, 4, "Attribute Damage", "maxed"),
    ]
    cands = research.matching_layouts(boxes)
    assert {c.label for c in cands} == {"V", "VIII/XI/XIV/XVII/XX/..."}
    assert research.place_in(cands, "Skip Stage") == ("absent", None, None)
    assert research.place_in(cands, "Leadership") == ("unclear", None, None)  # V has none
    assert research.place_in(cands, "Guardian Power") == ("column", 4, None)  # V: 6, VIII: 4
    assert research.place_in(cands, "Raining Gold") == ("column", 8, (8, 0))


# --- geometry -----------------------------------------------------------------------------------


def test_rows_and_columns():
    assert [research.row_of(y) for y in (224, 345, 467, 588, 709, 710)] == [0, 1, 2, 3, 4, 4]
    assert research.row_of(290) is None
    assert research.column_of(225, 225) == 1
    assert research.column_of(718 + 1344, 225) == 5  # seen at x 718 two stops on (1344 px)
    assert research.column_of(677, 225) == 2  # the trees whose column 2 is 8 px off
    assert research.column_of(225 + 200, 225) is None  # the right part of a split box


def _seen(x, y, name, state="maxed"):
    return Seen(blobs.Blob(int(x), int(y), int(x) + 383, int(y) + 101, 1), x, y, name, state)


def test_boxes_seen_at_several_stops_count_once():
    stop0 = [
        _seen(225, 467, "Rage Heroes", "available"),
        _seen(685, 345, "Energy Heroes", "available"),
        _seen(685, 588, None, "available"),  # a sparkle: Mana Heroes, unidentified here
        _seen(1144, 224, "Attribute Health"),
    ]
    stop1 = [  # 672 px further: columns 1 and 2 are cut (left out), column 3 again
        _seen(472, 224, "Attribute Health"),
        _seen(931, 467, "Guardian Power", "running"),
    ]
    boxes = research.merge([stop0, stop1], [0.0, 672.0])
    assert [(b.col, b.row, b.name) for b in boxes] == [
        (1, 2, "Rage Heroes"),
        (2, 1, "Energy Heroes"),
        (2, 3, None),
        (3, 0, "Attribute Health"),
        (4, 2, "Guardian Power"),
    ]
    assert boxes[3].stops == [0, 1]
    # a later sighting (the icon grabbed again at the same place) names the unidentified box
    boxes = research.merge([stop0, [_seen(685, 588, "Mana Heroes", "available")]], [0.0, 0.0])
    assert boxes[2].name == "Mana Heroes" and boxes[2].stops == [0, 1]


def test_the_view_move_from_boxes_seen_at_both_stops():
    before = [_seen(1144, 224, "Attribute Health"), _seen(1144, 467, None)]
    after = [_seen(472, 224, "Attribute Health"), _seen(931, 467, "Guardian Power")]
    assert research._moved_by_boxes(before, after) == 672
    assert research._moved_by_boxes(before, [_seen(931, 467, "Guardian Power")]) is None


# --- the choice -------------------------------------------------------------------------------


def test_an_available_priority_is_started():
    run = Run(xiii(), ["Mana Heroes"])
    choice = run.choose()
    assert choice.box.name == "Mana Heroes"
    assert choice.line == "Research: Mana Heroes started (priority 1)"
    assert run.tapped == ["Mana Heroes"]


def test_maxed_and_running_priorities_are_passed_over():
    run = Run(xiii(), ["Guardian Power", "Leadership", "", "Energy Heroes"])
    choice = run.choose()
    assert choice.line == "Research: Energy Heroes started (priority 4)"
    assert run.tapped == ["Energy Heroes"]


def test_an_unseen_priority_gets_what_unlocks_it():
    """Columns 4 to 8 locked (unseen): Leadership (column 7) needs column 3, the nearest
    seen column before it; its priority box goes first."""
    hidden = {
        n: "hidden"
        for n in (
            "Guardian Power",
            "Expose Weakness",
            "Powerless Boss",
            "Weaklings",
            "Powerless Enemy",
            "Leadership",
            "Team Bonus",
            "Raining Gold",
            "Firestone Effect",
            "All Main Attributes",
        )
    }
    col3 = {n: "available" for n in ("Attribute Health", "Attribute Armor", "Attribute Damage")}
    run = Run(xiii(**hidden, **col3), ["Leadership", "Attribute Damage"])
    choice = run.choose()
    assert choice.line == "Research: Attribute Damage started to unlock Leadership (priority 1)"
    assert run.tapped == ["Attribute Damage"]
    # without a priority in that column: its top box
    run = Run(xiii(**hidden, **col3), ["Leadership"])
    assert run.choose().box.name == "Attribute Health"


def test_a_priority_whose_popup_has_no_research_button_is_unlocked():
    run = Run(xiii(), ["Energy Heroes"], outcomes={"Energy Heroes": "locked"})
    choice = run.choose()
    assert choice.line == "Research: Rage Heroes started to unlock Energy Heroes (priority 1)"
    assert run.tapped == ["Energy Heroes", "Rage Heroes"]


def test_a_locked_column_before_sends_the_unlock_one_column_further_back():
    """Guardian Power (column 4) unseen; the available boxes of column 3 offer no Research
    button either: column 2 unlocks them."""
    boxes = xiii(
        **{
            "Guardian Power": "hidden",
            "Attribute Health": "available",
            "Attribute Armor": "available",
        }
    )
    outcomes = {"Attribute Health": "locked", "Attribute Armor": "locked"}
    run = Run(boxes, ["Guardian Power"], outcomes=outcomes)
    choice = run.choose()
    assert run.tapped == ["Attribute Health", "Attribute Armor", "Energy Heroes"]
    assert choice.line == "Research: Energy Heroes started to unlock Guardian Power (priority 1)"


def test_an_unlock_column_with_nothing_to_start_moves_to_the_next_priority():
    """Column 2 all maxed or running: Attribute Health (column 3) cannot be unlocked now."""
    boxes = xiii(
        **{
            "Energy Heroes": "maxed",
            "Mana Heroes": "running",
            "Attribute Health": "hidden",
            "Attribute Armor": "hidden",
            "Attribute Damage": "hidden",
        }
    )
    run = Run(boxes, ["Attribute Health", "Rage Heroes"])
    choice = run.choose()
    assert choice.line == "Research: Rage Heroes started (priority 2)"
    assert run.tapped == ["Rage Heroes"]


def test_a_priority_missed_in_a_column_that_shows_is_not_unlocked():
    """Leadership unseen while Team Bonus, below it, shows: its column is open (columns
    unlock as a whole), so nothing is started to unlock it."""
    run = Run(xiii(Leadership="hidden"), ["Leadership"], any_other=False)
    choice = run.choose()
    assert choice.box is None and run.tapped == []
    assert "Leadership unseen" in choice.line


def test_a_priority_absent_from_the_tree_is_said_and_passed_over():
    run = Run(xiii(), ["Skip Stage", "Rage Heroes"])
    choice = run.choose()
    assert choice.line == "Research: Rage Heroes started (priority 2)"
    assert run.said == [
        (
            "Research: Skip Stage is absent from this tree (tree like X/XIII/XVI/XIX/...), "
            "priority 1 skipped"
        )
    ]


def test_an_unidentified_box_where_every_layout_has_the_priority_is_that_priority():
    boxes = xiii()
    boxes[6] = Box(4, 2, None, "available")  # Guardian Power, a sparkle over its icon
    run = Run(boxes, ["Guardian Power"])
    choice = run.choose()
    assert choice.line == "Research: Guardian Power started (priority 1)"
    assert run.tapped == [(4, 2)]


def test_ambiguous_layouts_use_only_what_they_agree_on():
    """Trees V and VIII fit: Leadership (absent from V) is skipped, Guardian Power (column 6
    in V, 4 in VIII) is unlocked from before column 4."""
    boxes = [
        Box(1, 0, "Attribute Armor", "maxed"),
        Box(1, 2, "Attribute Health", "maxed"),
        Box(1, 4, "Attribute Damage", "maxed"),
        Box(2, 1, None, "available"),
        Box(2, 3, None, "available"),
    ]
    run = Run(boxes, ["Leadership", "Guardian Power"])
    choice = run.choose()
    assert run.tapped == [(2, 1)]
    assert choice.line == (
        "Research: the column 2 research started to unlock Guardian Power (priority 2)"
    )
    assert len(run.said) == 1 and run.said[0].startswith("Research: Leadership is unseen")


@pytest.mark.parametrize("name", ["Guardian Power", "Attribute Health"])
def test_unidentified_boxes_of_several_layouts_start_nothing_before_a_column_that_shows(name):
    """Review of 2026-09-29: tree XIII wholly open, no icon identified (the Mac's colours):
    four layouts fit, Guardian Power lies in column 3 of one of them and 4 or 8 of the
    others. Column 3 shows, so none of them needs column 2: nothing is tapped (it started
    the column 2 research "to unlock" Guardian Power)."""
    boxes = [Box(b.col, b.row, None, "available") for b in xiii()]
    assert len(research.matching_layouts(boxes)) > 1
    run = Run(boxes, [name], any_other=False)
    choice = run.choose()
    assert run.tapped == [] and choice.box is None
    assert f"{name} unseen" in choice.line


def test_a_tree_no_layout_holds_is_said_so():
    """Review of 2026-09-29: with no layout left, "its place differs between the possible
    trees" was said though there were none."""
    run = Run([], ["Leadership"], any_other=False, cands=[])
    choice = run.choose()
    assert choice.box is None and run.tapped == []
    assert run.said == [
        "Research: the tree could not be recognised, Leadership (unseen, priority 1) skipped"
    ]
    assert "Leadership unseen in an unrecognised tree" in choice.line


def _scanned_to_column_5():
    """What a scan that stopped at column 5 saw of tree XIII (Expose Weakness available)."""
    return [b for b in xiii(**{"Expose Weakness": "available"}) if b.col <= 5]


def test_a_priority_beyond_the_scans_reach_is_passed_over():
    """Leadership (column 7) with the scan stopped at column 5: column 6 was never seen, it
    is unknown, not locked, and Expose Weakness is not started "to unlock" Leadership."""
    run = Run(_scanned_to_column_5(), ["Leadership"], any_other=False, reach=5)
    choice = run.choose()
    assert run.tapped == [] and choice.box is None
    assert "Leadership unseen beyond the scan's reach" in choice.line
    # with Research something else on, the other research says why
    run = Run(_scanned_to_column_5(), ["Leadership"], reach=5)
    choice = run.choose()
    assert choice.line == (
        "Research: Expose Weakness started (other research, priorities: Leadership unseen "
        "beyond the scan's reach)"
    )
    assert _is_start(choice.line)


def test_an_unlock_never_walks_over_a_column_beyond_the_reach():
    boxes = _scanned_to_column_5()
    cands = research.matching_layouts(xiii())
    run = Run(boxes, [], cands=cands, reach=5)
    assert run.chooser.unlock(7) is None and run.tapped == []  # column 6: unknown
    run = Run(boxes, [], cands=cands)  # a whole tree whose columns 6 to 8 are locked
    assert run.chooser.unlock(7).name == "Expose Weakness"


def test_other_research_right_most_first_when_the_priorities_cannot_be_used():
    run = Run(xiii(), ["Guardian Power", "Attribute Damage"], outcomes={"Energy Heroes": "locked"})
    choice = run.choose()
    assert run.tapped == ["Energy Heroes", "Mana Heroes"]
    assert choice.line == (
        "Research: Mana Heroes started (other research, the priorities are maxed or running)"
    )


def test_other_research_says_why_the_priorities_were_passed_over():
    run = Run(xiii(), ["Skip Stage", "Leadership"], outcomes={"Rage Heroes": "failed"})
    choice = run.choose()
    assert choice.line == (
        "Research: Energy Heroes started (other research, priorities: Skip Stage absent from "
        "this tree, Leadership maxed)"
    )


def test_without_priorities_the_right_most_box_as_before():
    run = Run(xiii(), [])
    assert run.choose().line == (
        "Research: Energy Heroes started (any research, the priority list is empty)"
    )


def test_with_research_something_else_off_the_slot_stays_free():
    run = Run(xiii(), ["Guardian Power", "Skip Stage"], any_other=False)
    choice = run.choose()
    assert choice.box is None and run.tapped == []
    assert choice.line == (
        "Research: slot left free (priorities: Guardian Power running, Skip Stage absent from "
        "this tree; Research something else is off), next search in 15 min"
    )


def test_nothing_startable_at_all():
    boxes = xiii(**{"Rage Heroes": "maxed", "Energy Heroes": "maxed", "Mana Heroes": "maxed"})
    choice = Run(boxes, ["Guardian Power"]).choose()
    assert choice.box is None and choice.line == ""


def test_each_box_is_tapped_once_per_decision():
    outcomes = {"Energy Heroes": "locked", "Mana Heroes": "locked", "Rage Heroes": "locked"}
    run = Run(xiii(), ["Energy Heroes", "Mana Heroes"], outcomes=outcomes)
    assert run.choose().box is None
    assert sorted(run.tapped) == ["Energy Heroes", "Mana Heroes", "Rage Heroes"]


@pytest.mark.parametrize(
    "priorities, outcomes",
    [
        (["Mana Heroes"], {}),
        (["Energy Heroes"], {"Energy Heroes": "locked"}),
        (["Skip Stage", "Leadership", "Guardian Power"], {}),
        (["Medal of Honor"], {}),
        ([], {}),
    ],
)
def test_start_lines_count_as_starts_for_the_log_watcher(priorities, outcomes):
    choice = Run(xiii(), priorities, outcomes=outcomes).choose()
    assert choice.box is not None and _is_start(choice.line), choice.line


def test_failure_lines_are_not_starts():
    free = Run(xiii(), ["Guardian Power"], any_other=False).choose().line
    assert not _is_start(free)
    assert not _is_start(
        "Research: a slot is free but no research could start, next search in 15 min"
    )


class _G:
    def __init__(self, **values):
        self.settings = Settings()
        for k, v in values.items():
            self.settings.set(k, v)
        self.vars = {}
        self.statuses = []

    def status(self, s):
        self.statuses.append(s)


def test_priorities_from_the_settings():
    g = _G(
        ResearchPriority1="",
        ResearchPriority2="guardian power",
        ResearchPriority3="Guardian Power",
        ResearchPriority4="Nonsense",
        ResearchPriority5="Mana Heroes",
    )
    assert research.priorities(g) == [(2, "Guardian Power"), (5, "Mana Heroes")]
    assert g.statuses == ["Research: priority 4 (Nonsense) is an unknown name"]
    research.priorities(g)
    assert len(g.statuses) == 1  # once a game day
    g.settings.set("LastTokenReset", "20260929000000")
    research.priorities(g)
    assert len(g.statuses) == 2


# --- taking turns within a column (tree XIV, 2026-10-09) ---------------------------------------


def xiv_column_1(armor="available", health="available", damage="available"):
    """Tree XIV on 2026-10-09: column 1 open (Armor and Health at 13/60, Damage at 0/60),
    column 2 "Locked" (Healer / Tank specialization need all three at level 6): the scan
    sees only column 1."""
    return [
        Box(1, 0, "Attribute Armor", armor),
        Box(1, 2, "Attribute Health", health),
        Box(1, 4, "Attribute Damage", damage),
    ]


def test_without_starts_known_the_top_box_as_before():
    run = Run(xiv_column_1(), [])
    assert run.choose().box.name == "Attribute Armor"


def test_the_research_never_started_goes_before_the_ones_started_already():
    """Armor and Health were started at every turn and Damage never: column 2 stayed locked
    for a day and a half."""
    started = {"attribute armor": 100.0, "attribute health": 101.0}
    run = Run(xiv_column_1(), [], started=started)
    choice = run.choose()
    assert choice.box.name == "Attribute Damage"
    assert choice.line == (
        "Research: Attribute Damage started (any research, the priority list is empty)"
    )


def test_then_the_one_started_longest_ago():
    started = {"attribute armor": 100.0, "attribute health": 101.0, "attribute damage": 200.0}
    run = Run(xiv_column_1(damage="running"), [], started=started)
    assert run.choose().box.name == "Attribute Armor"
    started["attribute armor"] = 300.0
    run = Run(xiv_column_1(damage="running"), [], started=started)
    assert run.choose().box.name == "Attribute Health"


def test_the_right_most_column_still_comes_first():
    started = {"rage heroes": 1.0}
    run = Run(xiii(), [], started=started)
    # column 2: Energy Heroes and Mana Heroes never started, the top one of them
    assert run.choose().box.name == "Energy Heroes"


def test_an_unlock_takes_turns_too():
    """A priority in the locked column 2: what unlocks it is the column 1 research started
    longest ago, not the top one again."""
    started = {"attribute armor": 100.0, "attribute health": 101.0}
    run = Run(xiv_column_1(), ["Healer Specialization"], started=started)
    choice = run.choose()
    assert choice.box.name == "Attribute Damage"
    assert choice.line == (
        "Research: Attribute Damage started to unlock Healer Specialization (priority 1)"
    )


def test_a_priority_still_goes_before_a_box_started_longer_ago():
    started = {"attribute armor": 100.0, "attribute health": 101.0}
    run = Run(xiv_column_1(), ["Attribute Health"], started=started)
    assert run.choose().box.name == "Attribute Health"


def test_unidentified_boxes_take_turns_by_their_place():
    boxes = [Box(1, 0, None, "available"), Box(1, 2, None, "available")]
    started = {research.started_key(boxes[0]): 5.0}
    assert research.started_key(boxes[1]) == "column 1 row 2"
    run = Run(boxes, [], started=started, cands=[])
    assert run.choose().box is boxes[1]
