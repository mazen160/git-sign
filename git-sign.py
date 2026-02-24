#!/usr/bin/env python3
"""
git-sign: Re-sign commits on a branch with your GPG/SSH key.

Built for stamping PRs created by AI agents that can't sign commits.
"""

import argparse
import os
import subprocess
import sys
import tempfile

__version__ = "0.1.0"

PROTECTED_BRANCHES = ("main", "master")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def check_git_repo():
    result = run(["git", "rev-parse", "--is-inside-work-tree"])
    if result.returncode != 0:
        print("Error: not inside a git repository.", file=sys.stderr)
        sys.exit(1)


def current_branch():
    result = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = result.stdout.strip()
    if branch == "HEAD":
        print("Error: HEAD is detached. Check out a branch first.", file=sys.stderr)
        sys.exit(1)
    return branch


def validate_branch(branch):
    if branch in PROTECTED_BRANCHES:
        print(f"Error: refusing to rewrite history on {branch}.", file=sys.stderr)
        sys.exit(1)


def validate_signing_key():
    key = run(["git", "config", "user.signingkey"]).stdout.strip()
    if not key:
        print("Error: no signing key configured.", file=sys.stderr)
        print("Set one with: git config user.signingkey <key-id>", file=sys.stderr)
        sys.exit(1)


def get_primary_remote():
    result = run(["git", "remote"])
    remotes = result.stdout.strip().splitlines()
    return remotes[0] if remotes else "origin"


def get_base_branch(remote, override=None):
    if override:
        return override

    result = run(["git", "symbolic-ref", f"refs/remotes/{remote}/HEAD"])
    ref = result.stdout.strip()
    if ref:
        return ref.replace(f"refs/remotes/{remote}/", "")
    return "main"


def confirm_proceed(branch):
    print(f"Re-signing commits on branch: {branch}")
    print("This squashes all commits into one signed commit and rewrites history.")
    try:
        answer = input("Proceed? (y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    if answer != "y":
        sys.exit(1)


def sign_commits(
    branch, remote, remote_base, dry_run=False, force_push=False, message=None
):
    if dry_run:
        print(f"Dry run -- would squash and sign commits on {branch}:")
        print(f"  git diff --binary {remote_base} {branch} > <tmpfile>")
        print(f"  git reset --hard {remote_base}")
        print("  git apply <tmpfile>")
        print("  git add .")
        print("  git commit -S")
        if force_push:
            print(f"  git push --force {remote} {branch}")
        return

    print(f"Generating diff from {remote_base}...")

    fd, diff_path = tempfile.mkstemp(prefix="git-sign-diff-")
    os.close(fd)

    try:
        with open(diff_path, "wb") as f:
            subprocess.run(
                ["git", "diff", "--binary", remote_base, branch],
                stdout=f,
            )

        if os.path.getsize(diff_path) == 0:
            print(
                f"No changes found between {remote_base} and {branch}.", file=sys.stderr
            )
            sys.exit(1)

        print(f"Resetting branch to {remote_base}...")
        result = subprocess.run(["git", "reset", "--hard", remote_base], text=True)
        if result.returncode != 0:
            print("Failed to reset branch.", file=sys.stderr)
            sys.exit(1)

        print("Applying diff...")
        result = subprocess.run(["git", "apply", diff_path], text=True)
        if result.returncode != 0:
            print("Failed to apply diff.", file=sys.stderr)
            print("You may need to manually recover the branch.", file=sys.stderr)
            sys.exit(1)

    finally:
        os.unlink(diff_path)

    subprocess.run(["git", "add", "."], text=True)

    print("Committing signed changes...")
    commit_cmd = ["git", "commit", "-S"]
    if message:
        commit_cmd += ["-m", message]

    result = subprocess.run(commit_cmd, text=True)
    if result.returncode != 0:
        print("Commit failed.", file=sys.stderr)
        sys.exit(1)

    print("Done.")

    if force_push:
        print(f"Force pushing to {remote}/{branch}...")
        push_result = subprocess.run(
            ["git", "push", "--force", remote, branch],
            text=True,
        )
        if push_result.returncode != 0:
            print("Force push failed.", file=sys.stderr)
            sys.exit(1)
        print("Pushed.")
    else:
        print("You likely need to force push:")
        print(f"  git push --force {remote} {branch}")


def banner():
    print(
        r"""
          _ _          _
     __ _(_) |_ ___  _(_) __ _ _ __
    / _` | | __|___| / __| |/ _` | '_ \
   | (_| | | |_     \__ \ | (_| | | | |
    \__, |_|\__|    |___/_|\__, |_| |_|
    |___/                  |___/
    squash & sign commits. stamp your PRs.
"""
    )


def main():
    banner()
    parser = argparse.ArgumentParser(
        prog="git-sign",
        description="Re-sign commits on a branch with your GPG/SSH key.",
    )
    parser.add_argument(
        "--base",
        metavar="BRANCH",
        help="base branch to compare against (default: auto-detect from remote HEAD)",
    )
    parser.add_argument(
        "--force-push",
        action="store_true",
        help="force push after signing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would happen without making changes",
    )
    parser.add_argument(
        "-m",
        "--message",
        metavar="MSG",
        help="commit message (default: opens editor)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="skip confirmation prompt",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()

    check_git_repo()

    branch = current_branch()
    validate_branch(branch)
    validate_signing_key()

    remote = get_primary_remote()
    base_branch = get_base_branch(remote, override=args.base)
    remote_base = f"{remote}/{base_branch}"

    if not args.yes and not args.dry_run:
        confirm_proceed(branch)

    sign_commits(
        branch,
        remote,
        remote_base,
        dry_run=args.dry_run,
        force_push=args.force_push,
        message=args.message,
    )


if __name__ == "__main__":
    main()
