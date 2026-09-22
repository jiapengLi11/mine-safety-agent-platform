from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_MODEL_FILES = ("config.json", "tokenizer_config.json")


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Download the Qwen evaluation matrix on the GPU host")
    parser.add_argument("--config", type=Path, default=root / "config" / "qwen-matrix-5090.json")
    parser.add_argument("--model-root", type=Path)
    parser.add_argument("--include", nargs="*", help="Optional model names, for example Qwen3-1.7B")
    parser.add_argument("--max-workers", type=int, default=4)
    return parser.parse_args()


def load_matrix(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("schema_version") != "1.0" or not payload.get("models"):
        raise ValueError(f"Invalid matrix config: {path}")
    return payload


def validate_model_dir(path: Path) -> list[str]:
    missing = [name for name in REQUIRED_MODEL_FILES if not (path / name).is_file()]
    has_weights = any(path.glob("*.safetensors")) or (path / "model.safetensors.index.json").is_file()
    if not has_weights:
        missing.append("*.safetensors")
    return missing


def main() -> int:
    args = parse_args()
    if args.max_workers < 1:
        raise ValueError("--max-workers must be at least 1")
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("Run 01_install_dependencies.bat before downloading models") from exc

    matrix = load_matrix(args.config)
    model_root = (args.model_root or Path(matrix["model_root"])).resolve()
    model_root.mkdir(parents=True, exist_ok=True)
    selected = set(args.include or [])
    models = [
        item
        for item in matrix["models"]
        if item.get("enabled", True) and (not selected or item["name"] in selected)
    ]
    if not models:
        raise ValueError("No enabled models matched --include")

    print(f"Download root: {model_root}")
    for index, item in enumerate(models, start=1):
        local_dir = model_root / item["relative_path"]
        print(f"\n[{index}/{len(models)}] {item['model_id']} -> {local_dir}")
        snapshot_download(
            repo_id=item["model_id"],
            local_dir=local_dir,
            max_workers=args.max_workers,
            ignore_patterns=["*.bin", "*.h5", "*.msgpack", "*.ot", "original/*"],
        )
        missing = validate_model_dir(local_dir)
        if missing:
            raise RuntimeError(f"Incomplete model download at {local_dir}: missing {missing}")
        size_bytes = sum(path.stat().st_size for path in local_dir.rglob("*") if path.is_file())
        print(f"Verified {item['name']}: {size_bytes / (1024 ** 3):.2f} GiB")

    print("\nAll selected models are downloaded and structurally complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
