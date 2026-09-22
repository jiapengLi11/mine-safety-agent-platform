from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "mineguard-qwen-matrix-5090"
RELEASE_ROOT = ROOT / "release"
STAGING = RELEASE_ROOT / PACKAGE_NAME
SOURCE_SCRIPTS = ROOT / "evals" / "5090-package"


def ignore_eval_files(_directory: str, names: list[str]) -> set[str]:
    ignored = {"reports", "__pycache__", "5090-package"}
    return {name for name in names if name in ignored or name.endswith(".pyc")}


def main() -> int:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    shutil.copytree(ROOT / "evals", STAGING / "evals", ignore=ignore_eval_files)
    for source in SOURCE_SCRIPTS.iterdir():
        if source.is_file():
            shutil.copy2(source, STAGING / source.name)

    archive = RELEASE_ROOT / f"{PACKAGE_NAME}.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for path in sorted(STAGING.rglob("*")):
            if path.is_file():
                handle.write(path, path.relative_to(RELEASE_ROOT))
    file_count = sum(1 for path in STAGING.rglob("*") if path.is_file())
    print(f"Built: {archive}")
    print(f"Files: {file_count}; zip size: {archive.stat().st_size / 1024:.1f} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
