from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from PyQt6.QtGui import QImageReader
except ImportError as exc:
    print("PyQt6 is required. Install dependencies with: python -m pip install -r requirements.txt")
    raise SystemExit(2) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSET_ROOT = PROJECT_ROOT / "assets" / "monkey"
EXPECTED_SIZE = (64, 64)
_NATURAL_PARTS = re.compile(r"(\d+)")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def natural_key(path: Path) -> list[int | str]:
    parts: list[int | str] = []
    for part in _NATURAL_PARTS.split(path.as_posix().lower()):
        if part.isdigit():
            parts.append(int(part))
        elif part:
            parts.append(part)
    return parts


def validate_png(path: Path, asset_root: Path) -> tuple[bool, list[str]]:
    issues: list[str] = []

    try:
        resolved_path = path.resolve()
    except OSError as exc:
        issues.append(f"file path could not be resolved: {exc}")
        return False, issues

    if not is_relative_to(resolved_path, asset_root):
        issues.append("file resolves outside the validation root")
        return False, issues

    if not path.name.strip():
        issues.append("filename is empty or whitespace")

    try:
        with path.open("rb") as handle:
            handle.read(1)
    except OSError as exc:
        issues.append(f"file is not readable: {exc}")
        return False, issues

    reader = QImageReader(str(path))
    if not reader.canRead():
        issues.append("file could not be decoded as PNG")
        return False, issues

    image = reader.read()
    if image.isNull():
        issues.append("file could not be decoded as PNG")
        return False, issues

    if (image.width(), image.height()) != EXPECTED_SIZE:
        issues.append(f"expected 64x64, got {image.width()}x{image.height()}")

    if not image.hasAlphaChannel():
        issues.append("image mode does not support transparency")

    return not issues, issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate chaos desktop pet monkey PNG assets.")
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ASSET_ROOT,
        help="asset root to scan, defaults to assets/monkey",
    )
    args = parser.parse_args(argv)

    asset_root = args.root.resolve()
    print(f"Asset validation root: {asset_root}")

    if not asset_root.exists():
        print("INVALID: asset root does not exist")
        return 1

    pngs = sorted(asset_root.rglob("*.png"), key=natural_key)
    if not pngs:
        print("INVALID: no PNG files found")
        return 1

    valid_count = 0
    invalid_count = 0

    for path in pngs:
        is_valid, issues = validate_png(path, asset_root)
        rel_path = path.relative_to(asset_root)
        if is_valid:
            valid_count += 1
            print(f"[OK]      {rel_path}")
        else:
            invalid_count += 1
            print(f"[INVALID] {rel_path} - {'; '.join(issues)}")

    # 'idle' is the mandatory fallback state; everything else is optional.
    idle_dir = asset_root / "idle"
    idle_pngs = sorted(idle_dir.glob("*.png")) if idle_dir.is_dir() else []
    idle_ok = bool(idle_pngs)

    print()
    print(f"Summary: {valid_count} valid, {invalid_count} invalid, {len(pngs)} total")
    if not idle_ok:
        print("INVALID: required 'idle' state has no PNG frames (idle is mandatory).")
    else:
        print(f"Required 'idle' state: OK ({len(idle_pngs)} frame(s)).")
    return 0 if (invalid_count == 0 and idle_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
