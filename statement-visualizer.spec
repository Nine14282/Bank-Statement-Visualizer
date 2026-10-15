# PyInstaller build of Statement Visualizer: dist/StatementVisualizer/ = StatementVisualizer.exe + _internal/, which
# runs with no Python installed. Build it on the OS you ship for (PyInstaller doesn't cross-compile): Windows for the
# .exe. From the project folder (uv installs into its own .venv, so use a separate one, not the app-mode .venv), e.g.
# on Windows:
#   set UV_PROJECT_ENVIRONMENT=build-venv
#   uv sync --locked --no-dev --group build
#   uv run --no-sync pyinstaller --clean --noconfirm statement-visualizer.spec
# .github/workflows/windows-build.yml does the same on GitHub's Windows machines and runs a smoke check (--smoke) and a
# fresh install on the result.
#
# One folder, not one file: a one-file .exe unpacks itself into a temp folder on every start, which is slower and is
# what antivirus heuristics flag. No UPX either (packed executables get flagged too). The entry point is
# workspace/launcher.py (double-click = run); the other scripts run as the .exe again (--script, config.SCRIPTS). Your
# data goes next to the .exe; the build itself is read-only.
import glob
import os
import sys

from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.abspath(SPECPATH)
WORKSPACE = os.path.join(ROOT, "workspace")
WIN = sys.platform == "win32"

# Every workspace script, so --script can run any of them; launcher.py's analysis doesn't import them itself.
scripts = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(WORKSPACE, "*.py")))

a = Analysis(
    [os.path.join(WORKSPACE, "launcher.py")],
    pathex=[WORKSPACE],
    hiddenimports=[s for s in scripts if s != "launcher"],
    # pywebview reads its own JS files at run time; PyInstaller's webview hook only collects its lib/ DLLs.
    datas=[
        (os.path.join(ROOT, "web", "prebuilt", "index.html"), os.path.join("web", "prebuilt")),
        (os.path.join(ROOT, ".env.example"), "."),
    ] + (collect_data_files("webview", subdir="js") if WIN else []),
    # The app window is Windows' own web view (WebView2, through pywebview and pythonnet; the build group in
    # pyproject.toml). Qt stays out everywhere: a developer's app-mode .venv would pull ~500 MB of it in. Elsewhere the
    # build opens the pages in the browser, so no pywebview there either.
    excludes=["PyQt6", "qtpy", "tkinter"] + ([] if WIN else ["webview"]),
    optimize=0,   # keep asserts: -O would strip any assert statement in the code
)

# The .exe's version info (Properties > Details): antivirus heuristics count an unnamed, unversioned .exe against it.
# CI sets SV_VERSION from the release tag (text, e.g. 1.0.0-beta) and SV_FILE_VERSION (its numbers only).
version = None
if WIN:
    from PyInstaller.utils.win32 import versioninfo as vi
    text = os.environ.get("SV_VERSION", "0.0.0")
    nums = (tuple(int(n) for n in os.environ.get("SV_FILE_VERSION", "0.0.0").split(".")) + (0, 0, 0, 0))[:4]
    strings = {"CompanyName": "Statement Visualizer", "FileDescription": "Statement Visualizer", "FileVersion": text,
               "InternalName": "StatementVisualizer", "OriginalFilename": "StatementVisualizer.exe",
               "ProductName": "Statement Visualizer", "ProductVersion": text}
    version = vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(filevers=nums, prodvers=nums),
        kids=[vi.StringFileInfo([vi.StringTable("040904B0", [vi.StringStruct(k, v) for k, v in strings.items()])]),
              vi.VarFileInfo([vi.VarStruct("Translation", [1033, 1200])])])   # English (US), Unicode

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    # The frozen Python ignores PYTHONUTF8 (PyInstaller docs, "Specifying Python Interpreter Options"): UTF-8 mode here,
    # so Thai text prints on a Windows console and files open as UTF-8, as launcher.py arranges from source.
    [("X utf8", None, "OPTION")],
    exclude_binaries=True,
    name="StatementVisualizer",
    # Progress, the page's link and password prompts are in the console window. A double-click opens the app window
    # and app.py hides the console then (launcher.py); not hide_console here, which would hide it before an error.
    console=True,
    upx=False,
    version=version,
)
coll = COLLECT(exe, a.binaries, a.datas, name="StatementVisualizer", upx=False)
