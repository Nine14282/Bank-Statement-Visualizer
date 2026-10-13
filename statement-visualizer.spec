# PyInstaller build of Statement Visualizer: dist/StatementVisualizer/ = StatementVisualizer.exe + _internal/, which
# runs with no Python installed. Build it on the OS you ship for (PyInstaller doesn't cross-compile): Windows for the
# .exe. From the project folder, in a fresh venv (not an app-mode .venv), e.g. on Windows:
#   py -m venv build-venv
#   build-venv\Scripts\pip install --require-hashes -r requirements-build.lock
#   build-venv\Scripts\pyinstaller --clean --noconfirm statement-visualizer.spec
# .github/workflows/windows-build.yml does the same on GitHub's Windows machines and runs the self-checks on the result.
#
# One folder, not one file: a one-file .exe unpacks itself into a temp folder on every start, which is slower and is
# what antivirus heuristics flag. No UPX either (packed executables get flagged too). The entry point is
# workspace/launcher.py (double-click = run); the other scripts run as the .exe again (--script, config.SCRIPTS). Your
# data goes next to the .exe; the build itself is read-only.
import glob
import os

ROOT = os.path.abspath(SPECPATH)
WORKSPACE = os.path.join(ROOT, "workspace")

# Every workspace script, so --script can run any of them; launcher.py's analysis doesn't import them itself.
scripts = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(WORKSPACE, "*.py")))

a = Analysis(
    [os.path.join(WORKSPACE, "launcher.py")],
    pathex=[WORKSPACE],
    hiddenimports=[s for s in scripts if s != "launcher"],
    datas=[
        (os.path.join(ROOT, "web", "prebuilt", "index.html"), os.path.join("web", "prebuilt")),
        (os.path.join(ROOT, ".env.example"), "."),
    ],
    # The app window (pywebview, Qt) isn't part of this build yet: it opens the pages in the browser. Leaving them out
    # keeps a developer's app-mode .venv from pulling ~500 MB of Qt in.
    excludes=["webview", "PyQt6", "qtpy", "tkinter"],
    optimize=0,   # the self-checks are asserts: -O would strip them
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    # The frozen Python ignores PYTHONUTF8 (PyInstaller docs, "Specifying Python Interpreter Options"): UTF-8 mode here,
    # so Thai text prints on a Windows console and files open as UTF-8, as launcher.py arranges from source.
    [("X utf8", None, "OPTION")],
    exclude_binaries=True,
    name="StatementVisualizer",
    console=True,   # progress, the page's link and password prompts are in the console window
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="StatementVisualizer", upx=False)
