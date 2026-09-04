"""Advanced page: cycle, restart, Steam, heartbeat, appearance, counters, files."""

from __future__ import annotations

import os
from tkinter import messagebox

import customtkinter as ctk

from firestone_bot import daily
from firestone_bot.gui.catalog import READ_ONLY_LABELS, format_ahk_stamp
from firestone_bot.gui.context import PageContext
from firestone_bot.gui.widgets import Card, ReadOnlyValue, page_frame, page_title, place_card


def build(parent, ctx: PageContext):
    page, content = page_frame(parent)
    page_title(content, "Advanced", "Rare options, counters and files.")
    s = ctx.settings

    cycle = place_card(Card(content, ctx, "Cycle"))
    cycle.option(
        "Delay",
        unknown_note=(
            "err",
            (
                f"settings.ini has Delay={s.get('Delay')!r}: the bot stops after the first "
                "cycle with this value. Pick one of the choices."
            ),
        ),
    )
    cycle.option("SafetyCap")

    restart = place_card(Card(content, ctx, "Game restart", master="RestartGame"))
    restart.option("RestartGameTime")
    restart.option("RestartGameTest")

    steam = place_card(Card(content, ctx, "Steam"))
    steam.option("DisableWarning")

    hb = place_card(Card(content, ctx, "Heartbeat (opt-in)"))
    enable = hb.option("EnableHeartbeat")
    discord = hb.option("DiscordID", width=260)
    hb.add(
        ReadOnlyValue(
            hb.body,
            ctx,
            "Client ID",
            lambda: s.get("ClientID") or "(generated on the first heartbeat)",
            copy=True,
        )
    )
    hb_banner = hb.banner("warn", "Heartbeats are not sent without a Discord ID.", visible=False)

    def sync_hb(*_):
        hb_banner.set_visible(s.flag("EnableHeartbeat") and not s.get("DiscordID").strip())

    enable.control.var.trace_add("write", sync_hb)
    discord.control.var.trace_add("write", sync_hb)
    sync_hb()

    look = place_card(Card(content, ctx, "Appearance"))
    seg = ctk.CTkSegmentedButton(
        look.body, values=["System", "Light", "Dark"], variable=ctx.extras["appearance_var"]
    )
    look.add(seg, always_enabled=True)
    look.note("Colours only; the bot's screen reading is unaffected. Stored in gui_state.json.")

    counters = place_card(Card(content, ctx, "Daily counters (read-only)"))
    for key in ("TokenCountDaily", "ChaosCountDaily", "ScarabCountDaily", "CrystalCountDaily"):
        counters.add(
            ReadOnlyValue(counters.body, ctx, READ_ONLY_LABELS[key], lambda k=key: s.get(k) or "0")
        )
    counters.add(
        ReadOnlyValue(
            counters.body,
            ctx,
            READ_ONLY_LABELS["ArenaDoneDaily"],
            lambda: "yes" if daily.arena_done(s) else "no",
        )
    )
    for key in ("LastTokenReset", "LastChaosReset"):
        counters.add(
            ReadOnlyValue(
                counters.body, ctx, READ_ONLY_LABELS[key], lambda k=key: format_ahk_stamp(s.get(k))
            )
        )

    def reset_counters():
        if ctx.call("is_running"):
            return
        if messagebox.askyesno(
            "Reset counters",
            "Clear today's token, chaos, scarab and arena counters?",
            parent=ctx.root,
        ):
            try:
                daily.mark_daily_reset(s)
            except OSError as e:
                messagebox.showerror(
                    "Reset failed",
                    f"Counters were cleared in memory but settings.ini could not be written:\n{e}",
                    parent=ctx.root,
                )

    (reset_btn,) = counters.buttons(("Reset counters now…", reset_counters))
    counters.note("Use if the automatic reset was missed.")

    def tick_reset():
        state = "disabled" if ctx.call("is_running") else "normal"
        if reset_btn.cget("state") != state:
            reset_btn.configure(state=state)

    ctx.register_tick(tick_reset)

    files = place_card(Card(content, ctx, "Files"))
    if not ctx.extras.get("settings_existed", True):
        files.banner(
            "info", "settings.ini not found: defaults in use; it is created on first save."
        )
    base = ctx.base_dir
    for name in ("settings.ini", "MapStartState.ini", "firestone-bot.log"):
        files.add(
            ReadOnlyValue(files.body, ctx, name, lambda n=name: os.path.join(base, n), mono=True)
        )
    files.buttons(
        ("Save now", lambda: ctx.call("save_now")),
        ("Reload from disk", lambda: ctx.call("reload")),
        ("Open log file", lambda: ctx.call("open_log")),
        ("Open folder", lambda: ctx.call("open_folder")),
    )
    files.note(f"settings.ini encoding: {s.encoding}")
    return page
