#!/usr/bin/env python3
"""Build backend-deploy.zip for Azure App Service (Linux).

Always use this instead of PowerShell's Compress-Archive. Compress-Archive
writes ZIP entries with backslash separators, which Linux extracts as flat
files literally named "app\\main.py" -- there is then no `app` package and
gunicorn fails with ModuleNotFoundError: No module named 'app'.

Usage:  python make-deploy-zip.py
"""
import os
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "backend"
OUT = ROOT / "backend-deploy.zip"

SKIP_DIRS = {"__pycache__", ".pytest_cache", "tests", ".venv", "venv", "antenv", ".git",
             "notebooks", "scripts", "data"}  # research material; the runtime needs models/, not these
SKIP_FILES = {".env", "pytest.ini"}
SKIP_EXT = {".pyc", ".pyo"}

REQUIRED = ["app/main.py", "requirements.txt", "static/index.html",
            "models/revenue_model.joblib"]  # without it the forecast endpoint returns model_unavailable


def main() -> int:
    if not SRC.is_dir():
        sys.exit(f"error: {SRC} not found")
    if not (SRC / "static" / "index.html").is_file():
        sys.exit("error: backend/static/index.html missing -- build the frontend "
                 "and copy frontend/dist into backend/static first")

    added = []
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(SRC):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn in SKIP_FILES or pathlib.Path(fn).suffix in SKIP_EXT:
                    continue
                full = pathlib.Path(dirpath) / fn
                arc = full.relative_to(SRC).as_posix()   # POSIX separators, always
                z.write(full, arc)
                added.append(arc)

    bad = [a for a in added if "\\" in a]
    if bad:
        sys.exit(f"error: {len(bad)} entries have backslash separators")
    missing = [r for r in REQUIRED if r not in added]
    if missing:
        sys.exit(f"error: missing required entries: {missing}")

    print(f"{OUT.name}: {len(added)} entries, {OUT.stat().st_size:,} bytes")
    print("verified: POSIX separators, required entries present")
    print("\nDeploy with:")
    print("  az webapp deployment source config-zip \\")
    print("    -n app-ai26s-teamb-api-dev -g AI26s-Team-B --src backend-deploy.zip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
