"""macOS notification banners: close them while the bot runs (owner request 2026-09-06).

A banner (Calendar, Messages...) sits at the top right of the screen, exactly where the
dialogs' close button and the settings gear are: the bot clicked banners by mistake. The
Notification Center process exposes each banner as a group with a "Close" action (localised:
"Close", "Fermer"...), performed through the Accessibility API the bot already has.
"""

from __future__ import annotations

import logging

log = logging.getLogger("firestone_bot.mac.notifications")

CLOSE_WORDS = ("close", "fermer", "cerrar", "schließen", "chiudere", "sluiten", "clear")


def _ax_children(element):
    from ApplicationServices import AXUIElementCopyAttributeValue

    err, value = AXUIElementCopyAttributeValue(element, "AXChildren", None)
    return list(value) if err == 0 and value else []


def _close_action(element) -> str | None:
    from ApplicationServices import AXUIElementCopyActionDescription, AXUIElementCopyActionNames

    err, names = AXUIElementCopyActionNames(element, None)
    if err != 0 or not names:
        return None
    for name in names:
        err, desc = AXUIElementCopyActionDescription(element, name, None)
        text = f"{name} {desc or ''}".lower()
        if any(w in text for w in CLOSE_WORDS):
            return name
    return None


def close_banners() -> int:
    """Perform the close action of every banner shown by Notification Center. Returns the
    number of banners closed (0 when none, or when the API is unavailable)."""
    try:
        from AppKit import NSWorkspace
        from ApplicationServices import AXUIElementCreateApplication, AXUIElementPerformAction
    except ImportError:
        return 0
    closed = 0
    for app in NSWorkspace.sharedWorkspace().runningApplications():
        if app.bundleIdentifier() != "com.apple.notificationcenterui":
            continue
        root = AXUIElementCreateApplication(app.processIdentifier())
        stack = _ax_children(root)
        seen = 0
        while stack and seen < 400:
            el = stack.pop()
            seen += 1
            action = _close_action(el)
            if action is not None:
                if AXUIElementPerformAction(el, action) == 0:
                    closed += 1
                continue
            stack.extend(_ax_children(el))
    if closed:
        log.info("closed %d notification banner(s)", closed)
    return closed
