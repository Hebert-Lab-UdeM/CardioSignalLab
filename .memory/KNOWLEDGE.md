

## Project structure

<!--a7d3:0--> - Packaging artifacts: `pyproject.toml` (pip, cross-platform), `environment.yml` (conda, cross-platform), PyInstaller `.spec` with `BUNDLE` section for macOS `.app`

---

<!--d941:0--> - Launchers: `CardioSignalLab.bat` (Windows), `CardioSignalLab.sh` (macOS/Linux) — both locate the conda env or venv and invoke the installed console script

## Gotchas

<!--4301:0--> - `main.py` redirects logs to `~/Library/Logs/CardioSignalLab` on macOS (`darwin` branch); `app.py` uses a relative `"cardio_signal_lab.log"` that writes to CWD — the two log paths are inconsistent

---

## Conventions

<!--3ea8:0--> - All runtime deps (PySide6, PyQtGraph, NeuroKit2, etc.) ship macOS wheels for both arm64 and x86_64; `src/` contains no platform-specific code beyond the log-path branch in `main.py`
