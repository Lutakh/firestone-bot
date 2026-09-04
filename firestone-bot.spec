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
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="FirestoneBot",
    console=False,
    upx=False,
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="FirestoneBot", upx=False)
