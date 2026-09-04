"""Port of Functions/CheckMail.ahk: claim all mail attachments, delete read mail."""

from __future__ import annotations

from firestone_bot.features.big_close import big_close
from firestone_bot.game import Game
from firestone_bot.vision import atlas


def check_mail(g: Game) -> None:
    g.focus()
    # open mail
    g.move_to(atlas.MAIL_ICON)
    g.sleep(1000)
    g.click()
    g.sleep(1000)
    # attempt to click claim
    if g.found(atlas.MAIL_CLAIM_ALL):
        g.move_to(atlas.MAIL_CLAIM_BUTTON)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
        # click ok if mail had attachment, otherwise it is an empty click in the mail area
        g.move_to(atlas.MAIL_REWARD_OK)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
    # delete mail if any there
    if g.settings.flag("MailDelete") and g.found(atlas.MAIL_DELETE_READY):
        g.move_to(atlas.MAIL_DELETE_BUTTON)
        g.sleep(1000)
        g.click()
        g.sleep(1000)
    big_close(g)
