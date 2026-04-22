#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import NoReturn


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str


SECTION_ORDER = [
    ("Features", {"feat"}),
    ("Fixes", {"fix"}),
    ("Documentation", {"docs"}),
    ("Refactoring", {"refactor"}),
    ("Tests", {"test"}),
    ("Chores", {"chore", "build", "ci", "perf", "style"}),
]

CONVENTIONAL_PREFIX_RE = re.compile(r"^(?P<type>[A-Za-z]+)(?:\([^)]*\))?!?:\s*(?P<body>.+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a changelog entry from git history since the previous tag and prepend it "
            "to CHANGELOG.md."
        )
    )
    parser.add_argument(
        "--version", required=True, help="Release version, with or without a leading v"
    )
    parser.add_argument("--repo", default=".", help="Path to the git repository")
    parser.add_argument("--output", default="CHANGELOG.md", help="Tracked changelog file to update")
    parser.add_argument(
        "--previous-ref",
        help="Explicit starting ref for the changelog range; defaults to the latest reachable tag",
    )
    parser.add_argument(
        "--notes-file",
        help="Optional file to receive just the generated release notes section",
    )
    return parser.parse_args()


def fail(message: str) -> NoReturn:
    raise SystemExit(message)


def normalize_version(version: str) -> str:
    return version[1:] if version.startswith("v") else version


def git_executable() -> str:
    executable = shutil.which("git")
    if executable is None:
        fail("git executable not found in PATH")
    return executable


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [git_executable(), "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def ensure_repo(repo: Path) -> None:
    try:
        git(repo, "rev-parse", "--show-toplevel")
    except subprocess.CalledProcessError as exc:
        fail(exc.stderr.strip() or f"Not a git repository: {repo}")


def latest_tag(repo: Path) -> str | None:
    result = git(repo, "describe", "--tags", "--abbrev=0", check=False)
    if result.returncode != 0:
        return None
    tag = result.stdout.strip()
    return tag or None


def collect_commits(repo: Path, previous_ref: str | None) -> list[Commit]:
    args = ["log", "--no-merges", "--reverse", "--pretty=format:%H%x09%s"]
    if previous_ref:
        args.append(f"{previous_ref}..HEAD")
    result = git(repo, *args)
    commits: list[Commit] = []
    for line in result.stdout.splitlines():
        sha, _, subject = line.partition("\t")
        if sha and subject:
            commits.append(Commit(sha=sha, subject=subject))
    return commits


def format_subject(subject: str) -> tuple[str, str]:
    match = CONVENTIONAL_PREFIX_RE.match(subject)
    if not match:
        return "Other Changes", subject

    commit_type = match.group("type").lower()
    body = match.group("body")
    for section_name, types in SECTION_ORDER:
        if commit_type in types:
            return section_name, body
    return "Other Changes", subject


def render_section(version: str, previous_ref: str | None, commits: list[Commit]) -> str:
    heading = f"## v{version} - {date.today().isoformat()}"
    lines = [heading, ""]
    if previous_ref:
        lines.append(f"Changes since `{previous_ref}`:")
    else:
        lines.append("Initial release notes:")
    lines.append("")
    if commits:
        grouped: dict[str, list[str]] = {name: [] for name, _ in SECTION_ORDER}
        other_changes: list[str] = []
        for commit in commits:
            section_name, display_subject = format_subject(commit.subject)
            entry = f"- {display_subject} ({commit.sha[:7]})"
            if section_name == "Other Changes":
                other_changes.append(entry)
            else:
                grouped[section_name].append(entry)

        for section_name, _ in SECTION_ORDER:
            entries = grouped[section_name]
            if entries:
                lines.append(f"{section_name}:")
                lines.extend(entries)
                lines.append("")

        if other_changes:
            lines.append("Other Changes:")
            lines.extend(other_changes)
    else:
        lines.append("- No user-facing changes recorded in git history.")
    return "\n".join(lines).rstrip() + "\n"


def update_changelog(output_path: Path, section: str, version: str) -> None:
    marker = f"## v{version}"
    if output_path.exists():
        existing = output_path.read_text()
        if marker in existing:
            fail(f"Changelog already contains an entry for v{version}: {output_path}")
        header = "# Changelog\n"
        if existing.startswith(header):
            rest = existing[len(header) :].lstrip("\n")
            updated = header + "\n" + section + ("\n" + rest if rest else "")
        else:
            updated = section + "\n" + existing
    else:
        updated = f"# Changelog\n\n{section}"
    output_path.write_text(updated.rstrip() + "\n")


def main() -> int:
    args = parse_args()
    repo = Path(args.repo).resolve()
    ensure_repo(repo)

    version = normalize_version(args.version)
    output_path = (repo / args.output).resolve()
    previous_ref = args.previous_ref or latest_tag(repo)
    commits = collect_commits(repo, previous_ref)
    section = render_section(version, previous_ref, commits)

    update_changelog(output_path, section, version)

    if args.notes_file:
        notes_path = (repo / args.notes_file).resolve()
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        notes_path.write_text(section)

    print(f"VERSION={version}")
    print(f"CHANGELOG={output_path}")
    print(f"PREVIOUS_REF={previous_ref or ''}")
    print(f"COMMITS={len(commits)}")
    if args.notes_file:
        print(f"NOTES_FILE={(repo / args.notes_file).resolve()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
