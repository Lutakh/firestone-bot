# PyInstaller spec: one-dir build, no console, no UPX (plan 4.8).
#   pyinstaller firestone-bot.spec
# Windows / Linux: dist/FirestoneBot/ with a bootloader splash. macOS: dist/FirestoneBot.app
# (Splash is not supported on macOS; the app bundle carries the Retina and permission plist
# keys and is ad-hoc signed by PyInstaller, so Screen Recording / Accessibility grants stick
# to the bundle).
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

MAC = sys.platform == "darwin"
# macOS: identity of the self-signed code-signing certificate (tools/mac_codesign.py); empty =
# ad-hoc. A stable identity keeps the Screen Recording / Accessibility grants across updates.
CODESIGN_IDENTITY = os.environ.get("FIRESTONE_CODESIGN_IDENTITY") or None

a = Analysis(
    ["firestone_bot/__main__.py"],
    pathex=["."],
    datas=collect_data_files("customtkinter"),  # theme JSON + fonts under _internal/customtkinter/assets
    hiddenimports=collect_submodules("firestone_bot.features")
    + collect_submodules("firestone_bot.gui")
    + collect_submodules("firestone_bot.platform")
    + ["pynput.keyboard._win32", "pynput.mouse._win32", "pynput.keyboard._xorg", "pynput.mouse._xorg"]
    + ["pynput.keyboard._darwin", "pynput.mouse._darwin"]
    + ["customtkinter", "darkdetect"],
    excludes=["cv2", "matplotlib", "PIL", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
if MAC:
    exe = EXE(
        pyz,
        a.scripts,
        exclude_binaries=True,
        name="FirestoneBot",
        console=False,
        upx=False,
        icon=None,
        codesign_identity=CODESIGN_IDENTITY,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name="FirestoneBot", upx=False)
    app = BUNDLE(
        coll,
        name="FirestoneBot.app",
        icon=None,
        bundle_identifier="com.lutakh.firestone-bot",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "13.0",
            "NSAppleEventsUsageDescription": "Firestone Bot brings the game window to the front.",
            "CFBundleShortVersionString": "0.2.1",
        },
    )
else:
    # Native splash shown by the bootloader before Python starts (closed by app.py once the
    # window is up), so a cold start (antivirus scan of _internal) gives immediate feedback.
    splash = Splash(
        "assets/splash.png",
        binaries=a.binaries,
        datas=a.datas,
        text_pos=(120, 70),
        text_size=13,
        text_color="white",
        text_default="Firestone Bot is starting...",
        minify_script=True,
        always_on_top=False,
    )
    exe = EXE(
        pyz,
        a.scripts,
        splash,
        exclude_binaries=True,
        name="FirestoneBot",
        console=False,
        upx=False,
        icon=None,
    )
    coll = COLLECT(exe, splash.binaries, a.binaries, a.datas, name="FirestoneBot", upx=False)
