"""The purple gem icon that marks a paid button.

The game draws a paid button like the free one, but for its gem icon and its price: the
alchemist's orange Speed up (Qualitas, 2026-09-11), and on 2026-10-22 three users saw map
missions completed with gems the day a game update came (the orange "Complete instantly" of a
research popup and the map's "Refresh Now" carry the same gem). A click the bot believes free
must first find no gem in the button: one wrongly refused costs a few minutes, one wrongly
made costs gems.
"""

from __future__ import annotations

import numpy as np

# Share of a button rect allowed to be gem purple before the button counts as paid. Measured
# on the owner's 1920x1009 client: "Refresh Now" 1089 gem px of 21614 (5 %), "Complete
# instantly" 711 of 28120 (2.5 %), a green Research button 0, 1.1 M px of world map 65.
GEM_SHARE_MAX = 0.002
CONFIRM_MS = 150  # a second read: a gem drawn late never passes for free


def gem_mask(img: np.ndarray) -> np.ndarray:
    """Gem purple pixels of a BGR(A) image: red and blue well above green. The first test
    (r > 150, b > 150, g < 110) had 7 to 9 levels of margin on the measured gem 0x9F009D, less
    than a colour-managed capture shifts (macOS); the hue test keeps about 60, and orange,
    the blue panels, brown and white all fail it."""
    px = img[:, :, :3].astype(np.int16)
    b, gr, r = px[:, :, 0], px[:, :, 1], px[:, :, 2]
    return ((r > 150) & (b > 150) & (gr < 110)) | (
        (r - gr > 60) & (b - gr > 60) & (r > 100) & (b > 100)
    )


def gem_share(img: np.ndarray) -> float:
    if img.size == 0:
        return 0.0
    return float(gem_mask(img).mean())


def shows_gem(g, rect: tuple[int, int, int, int], anchor=None) -> bool:
    """True when the logical `rect` shows a gem icon, read twice (a gem drawn late counts)."""
    if gem_share(g.region_image(rect, anchor)) > GEM_SHARE_MAX:
        return True
    g.sleep(CONFIRM_MS)
    return gem_share(g.region_image(rect, anchor)) > GEM_SHARE_MAX
