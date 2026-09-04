# PyInstaller spec: one-dir build, no console, no UPX (plan 4.8).
#   pyinstaller firestone-bot.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ["firestone_bot/__main__.py"],
    pathex=["."],
    datas=collect_data_files("customtkinter"),  # theme JSON + fonts under _internal/customtkinter/assets
    hiddenimports=collect_submodules("firestone_bot.features")
    + collect_submodules("firestone_bot.gui")
    + ["pynput.keyboard._win32", "pynput.mouse._win32", "pynput.keyboard._xorg", "pynput.mouse._xorg"]
    + ["customtkinter", "darkdetect"],
    excludes=["cv2", "matplotlib", "PIL", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
# Native splash shown by the bootloader before Python starts (closed by app.py once the window
# is up), so a cold start (antivirus scan of _internal) gives immediate feedback.
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
