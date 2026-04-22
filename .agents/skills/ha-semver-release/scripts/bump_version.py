#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NoReturn

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
PLAIN_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PYPROJECT_VERSION_RE = re.compile(r'(?ms)(^\[project\]\s.*?^version\s*=\s*")([^"]+)(")')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bump the Home Assistant integration version for this repository and optionally "
            "keep pyproject.toml in sync."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--bump", choices=("major", "minor", "patch"))
    group.add_argument("--version")
    parser.add_argument(
        "--manifest",
        default="custom_components/aruba1930/manifest.json",
        help="Path to the Home Assistant integration manifest",
    )
    parser.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Only update the Home Assistant manifest version",
    )
    return parser.parse_args()


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def normalize_version(version: str) -> str:
    normalized = version[1:] if version.startswith("v") else version
    if not SEMVER_RE.fullmatch(normalized):
        fail(f"Invalid semantic version: {version}")
    return normalized


def read_manifest(path: Path) -> tuple[dict[str, object], str]:
    data = json.loads(path.read_text())
    version = data.get("version")
    if not isinstance(version, str):
        fail(f"Missing or invalid version field in {path}")
    normalized = normalize_version(version)
    return data, normalized


def bump_version(current: str, bump: str) -> str:
    match = PLAIN_SEMVER_RE.fullmatch(current)
    if not match:
        fail(
            "Automatic major/minor/patch bumps only support plain X.Y.Z versions; "
            "use --version for prerelease/build versions"
        )
    major, minor, patch = (int(part) for part in match.groups())
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def write_manifest(path: Path, data: dict[str, object], version: str) -> None:
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n")


def update_pyproject(path: Path, current: str, new: str) -> None:
    text = path.read_text()
    match = PYPROJECT_VERSION_RE.search(text)
    if match is None:
        fail(f"Could not find [project].version in {path}")
    pyproject_version = normalize_version(match.group(2))
    if pyproject_version != current:
        fail(
            f"Refusing to update {path}: version {pyproject_version} does not match "
            f"manifest version {current}. Use --manifest-only or align the files first."
        )
    updated = text[: match.start(2)] + new + text[match.end(2) :]
    path.write_text(updated)


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    pyproject_path = Path(args.pyproject)

    if not manifest_path.exists():
        fail(f"Manifest not found: {manifest_path}")
    if not args.manifest_only and not pyproject_path.exists():
        fail(f"pyproject.toml not found: {pyproject_path}")

    manifest_data, current_version = read_manifest(manifest_path)
    new_version = (
        normalize_version(args.version)
        if args.version
        else bump_version(current_version, args.bump)
    )
    if new_version == current_version:
        fail(f"Version is already {current_version}")

    write_manifest(manifest_path, manifest_data, new_version)
    changed_files = [str(manifest_path)]

    if not args.manifest_only:
        update_pyproject(pyproject_path, current_version, new_version)
        changed_files.append(str(pyproject_path))

    print(f"CURRENT_VERSION={current_version}")
    print(f"NEW_VERSION={new_version}")
    print("UPDATED_FILES=")
    for changed_file in changed_files:
        print(changed_file)

    return 0


if __name__ == "__main__":
    sys.exit(main())
