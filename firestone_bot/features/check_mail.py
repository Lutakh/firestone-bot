"""Port of Functions/CheckMail.ahk: claim all mail attachments, delete read mail."""

from __future__ import annotations

from firestone_bot import daily
from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas, bells

MAX_DELETES = 20  # safety: mails deleted in one visit


def check_mail(g: Game) -> None:
    """Claim the attachments and, when MailDelete is on, delete the mail already read.

    The bell on the icon only means unclaimed mail: mail that was read (by the bot when it
    claimed, or by the player) leaves no bell, so gating the whole visit on the bell left it
    in the box forever (owner, 2026-09-09). The visit happens on the bell and, when deleting
    is on, once per game day so the box is swept.
    """
    g.focus()
    bell = g.style != "new" or bells.has_bell(g, atlas.NS_MAIL_BELL)
    sweep = g.settings.flag("MailDelete") and not daily.mail_swept(g.settings)
    if not bell and not sweep:
        g.status("Mail: no bell on the mail icon, nothing to claim")
        return
    g.status("Mail: opening the mailbox" if bell else "Mail: daily sweep of the read mail")
    g.require_screen(g.ms.mail_icon, atlas.MAIL_CLOSE_X, 1000)
    done = []
    if g.found(atlas.MAIL_CLAIM_ALL):
        if not bell:
            # a claim with no bell seen: the bell rect does not fit this client
            g.status("Mail: attachments were waiting although no bell showed")
        g.status("Mail: claiming the attachments")
        g.tap(atlas.MAIL_CLAIM_BUTTON, 1000)
        # click ok if mail had attachment, otherwise it is an empty click in the mail area
        g.tap(atlas.MAIL_REWARD_OK, 1000)
        done.append("claimed")
    if g.settings.flag("MailDelete"):
        # one click deletes one mail (measured 2026-09-09): repeat while the bin stays
        # active, the AHK single click left every other read mail in the box
        deleted = 0
        while deleted < MAX_DELETES and g.found(atlas.MAIL_DELETE_READY):
            g.tap(atlas.MAIL_DELETE_BUTTON, 1000)
            g.wait_still()
            deleted += 1
        if deleted:
            g.status(f"Mail: {deleted} read mail deleted")
            done.append("deleted")
        daily.note_mail_swept(g.settings)
    if not done:
        g.status("Mail: nothing to claim or delete")
    big_close(g)
