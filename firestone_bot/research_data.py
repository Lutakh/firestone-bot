"""Research tree layouts (vision/research_trees.json) and the research names users pick from.

Owner request 2026-09-28: users choose the firestone and meteorite researches the bot works
on first, wherever they sit in the tree. The layouts come from the Firestone Idle RPG Wiki
(fandom, CC-BY-SA), retrieved 2026-09-28, with the corrections seen in game (see the file's
"about"). Firestone trees are columns of 1 to 3 researches, left to right; meteorite trees a
start node and three branches of four layers. Trees 1..21 are fixed, then A, B and C repeat.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

PATH = os.path.join(os.path.dirname(__file__), "vision", "research_trees.json")
# the unlock node of the very first meteorite tree: one level, nothing to prioritise
NOT_A_CHOICE = {"Meteorite Research"}


@lru_cache(maxsize=1)
def load() -> dict:
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def tree_key(number: int) -> str:
    """Key of tree `number` (1-based) in the data: "1".."21", then "A", "B", "C" in turn."""
    if number <= 21:
        return str(number)
    return "ABC"[(number - 22) % 3]


def firestone_columns(tree: str) -> list[list[tuple[str, int | None]]]:
    """Columns of firestone tree `tree`, left to right: (name, max level) top to bottom."""
    return [[(n, m) for n, m in col] for col in load()["firestone"][tree]["columns"]]


def meteorite_tree(tree: str) -> dict:
    return load()["meteorite"][tree]


def meteorite_names_of(tree: str) -> set[str]:
    t = meteorite_tree(tree)
    return {t["start"][0]} | {n for b in t["branches"].values() for n, _, _ in b}


@lru_cache(maxsize=1)
def firestone_names() -> tuple[str, ...]:
    trees = load()["firestone"].values()
    return tuple(sorted({n for t in trees for col in t["columns"] for n, _ in col}))


@lru_cache(maxsize=1)
def meteorite_names() -> tuple[str, ...]:
    return tuple(sorted({n for t in load()["meteorite"] for n in meteorite_names_of(t)}))


def meteorite_choices() -> tuple[str, ...]:
    return tuple(n for n in meteorite_names() if n not in NOT_A_CHOICE)
