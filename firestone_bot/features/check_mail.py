"""Port of Functions/CheckMail.ahk: claim all mail attachments, delete read mail."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas, bells


def check_mail(g: Game) -> None:
    g.focus()
    if g.style == "new" and not bells.has_bell(g, atlas.NS_MAIL_BELL):
        g.status("Mail: no bell on the mail icon, nothing to claim")
        return
    g.status("Mail: opening the mailbox")
    g.require_screen(g.ms.mail_icon, atlas.MAIL_CLOSE_X, 1000)
    done = []
    if g.found(atlas.MAIL_CLAIM_ALL):
        g.status("Mail: claiming the attachments")
        g.tap(atlas.MAIL_CLAIM_BUTTON, 1000)
        # click ok if mail had attachment, otherwise it is an empty click in the mail area
        g.tap(atlas.MAIL_REWARD_OK, 1000)
        done.append("claimed")
    if g.settings.flag("MailDelete") and g.found(atlas.MAIL_DELETE_READY):
        g.status("Mail: deleting the read mail")
        g.tap(atlas.MAIL_DELETE_BUTTON, 1000)
        done.append("deleted")
    if not done:
        g.status("Mail: nothing to claim or delete")
    big_close(g)
