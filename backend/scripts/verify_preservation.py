"""Read-only SHA-256 verification; prints paths only for changed originals, never values."""
import hashlib
import json
from pathlib import Path


def main():
    simplified = Path(__file__).resolve().parents[2]
    manifest = json.loads((simplified / "PRESERVATION.json").read_text(encoding="utf-8"))
    original = Path(manifest["original_root"])
    changed = []
    for relative, expected in manifest["sha256"].items():
        path = original / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            changed.append(relative)
    if changed:
        print("Original files differ:", ", ".join(changed))
        return 1
    print(f"PASS: {len(manifest['sha256'])} original files unchanged, including actual .env.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
