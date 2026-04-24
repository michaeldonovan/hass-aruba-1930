---
name: ha-semver-release
description: Bump this repository's Home Assistant integration version with semantic versioning, generate a changelog entry, keep matching project metadata in sync, commit the release, create an annotated tag, and push the branch and tag. Use when preparing a release for this HACS-compatible project.
---

# HA SemVer Release

This skill is local to this repository and uses the agent-compatible `.agents/skills` layout supported by OpenCode.

## Repository Facts

- The release version for the Home Assistant integration lives in `custom_components/aruba1930/manifest.json` under `version`.
- `hacs.json` does **not** store the integration version. Its `hacs` field is the minimum supported HACS version and should not be changed for semantic version bumps.
- `pyproject.toml` currently mirrors the integration version and should usually stay in sync unless the user explicitly asks for manifest-only changes.
- `uv.lock` should be refreshed with `uv lock` after updating `pyproject.toml` and included in normal release commits.
- Release notes can be generated into `CHANGELOG.md` from git history since the previous tag, grouped by conventional-commit-ish types.

## When to Use

- The user asks to cut a patch, minor, or major release
- The user gives an explicit semantic version like `1.2.3`
- The task includes bumping the version, committing it, tagging it, and pushing it

## Inputs To Collect

Ask for the smallest missing detail before changing anything:

1. Release type: `major`, `minor`, `patch`, or explicit version `X.Y.Z`
2. Scope: default to syncing both:
   - `custom_components/aruba1930/manifest.json`
   - `pyproject.toml`
   - `uv.lock` via `uv lock`
3. Changelog: default to updating `CHANGELOG.md`

If the user says "bump the HACS manifest", interpret that as `custom_components/aruba1930/manifest.json`, not `hacs.json`.

## Workflow

### 1. Check git state

- Run `git status --short --branch`
- If there are unrelated changes, ask whether to proceed before committing/tagging/pushing

### 2. Read the current version

- Read `custom_components/aruba1930/manifest.json`
- Use the bundled helper to compute and write the new version

### 3. Bump the version

Patch/minor/major:

```bash
python .agents/skills/ha-semver-release/scripts/bump_version.py --bump patch
```

Explicit version:

```bash
python .agents/skills/ha-semver-release/scripts/bump_version.py --version 1.2.3
```

Manifest only:

```bash
python .agents/skills/ha-semver-release/scripts/bump_version.py --bump patch --manifest-only
```

The helper:

- updates `custom_components/aruba1930/manifest.json`
- updates `pyproject.toml` unless `--manifest-only` is supplied
- prints the previous version, new version, and touched files

### 4. Refresh the lockfile

If `pyproject.toml` was updated, refresh the lockfile before generating the changelog:

```bash
uv lock
```

Skip this step for `--manifest-only` releases.

### 5. Generate the changelog

Create or update `CHANGELOG.md` from commits since the previous tag:

```bash
python .agents/skills/ha-semver-release/scripts/generate_changelog.py --version X.Y.Z
```

If you also want a separate notes file for `gh release create`:

```bash
python .agents/skills/ha-semver-release/scripts/generate_changelog.py --version X.Y.Z --notes-file .git/RELEASE_NOTES.md
```

The helper:

- finds the previous tag automatically when possible
- falls back to the full repo history when no prior tag exists
- prepends a new `vX.Y.Z` section to `CHANGELOG.md`
- can emit the same section to a notes file for GitHub Releases
- groups entries into `Features`, `Fixes`, `Documentation`, `Refactoring`, `Tests`, `Chores`, and `Other Changes`

### 6. Review the diff

- Run `git diff -- custom_components/aruba1930/manifest.json pyproject.toml uv.lock CHANGELOG.md`
- If manifest-only was requested, review the manifest and changelog diff

### 7. Commit the release

Default sync:

```bash
git add custom_components/aruba1930/manifest.json pyproject.toml uv.lock CHANGELOG.md && git commit -m "release: vX.Y.Z"
```

Manifest only:

```bash
git add custom_components/aruba1930/manifest.json CHANGELOG.md && git commit -m "release: vX.Y.Z"
```

Replace `X.Y.Z` with the new version reported by the helper.

### 8. Create the tag

```bash
git tag -a "vX.Y.Z" -m "Release vX.Y.Z"
```

### 9. Push branch and tag

- If the current branch already tracks a remote branch:

```bash
git push && git push origin "vX.Y.Z"
```

- If it does not:

```bash
git push -u origin HEAD && git push origin "vX.Y.Z"
```

## Safety Rules

- Never change `hacs.json` for semantic version bumps unless the user explicitly wants to change the minimum HACS version
- Do not overwrite an existing changelog entry for the same version
- Do not commit, tag, or push unrelated changes without confirmation
- Do not force push
- Do not amend unless the user explicitly asks and it is safe
- Never create a GitHub Release from this skill; repository GitHub Actions create releases automatically for tags that pass CI
- If the user asked only for the version bump, stop before git operations

## Expected Result

Report:

- previous version
- new version
- files changed
- changelog location
- commit SHA
- tag name
- push result
- note that no GitHub Release was created because GitHub Actions handles releases after CI passes
