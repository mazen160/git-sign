#!/usr/bin/env python3
"""
git-sign: Re-sign commits on a branch with your GPG/SSH key.

Built for stamping PRs created by AI agents that can't sign commits.
Author: Mazin Ahmed - mazin[at]mazinahmed[dot]net | 2026
"""

import argparse
import json
import os
import re
import shutil
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
    branch, remote, remote_base, dry_run=False, force_push=False, message=None,
    cwd=None,
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
                stdout=f, cwd=cwd,
            )

        if os.path.getsize(diff_path) == 0:
            print(
                f"No changes found between {remote_base} and {branch}.", file=sys.stderr
            )
            sys.exit(1)

        print(f"Resetting branch to {remote_base}...")
        result = subprocess.run(
            ["git", "reset", "--hard", remote_base], text=True, cwd=cwd,
        )
        if result.returncode != 0:
            print("Failed to reset branch.", file=sys.stderr)
            sys.exit(1)

        print("Applying diff...")
        result = subprocess.run(
            ["git", "apply", diff_path], text=True, cwd=cwd,
        )
        if result.returncode != 0:
            print("Failed to apply diff.", file=sys.stderr)
            print("You may need to manually recover the branch.", file=sys.stderr)
            sys.exit(1)

    finally:
        os.unlink(diff_path)

    subprocess.run(["git", "add", "."], text=True, cwd=cwd)

    print("Committing signed changes...")
    commit_cmd = ["git", "commit", "-S"]
    if message:
        commit_cmd += ["-m", message]

    result = subprocess.run(commit_cmd, text=True, cwd=cwd)
    if result.returncode != 0:
        print("Commit failed.", file=sys.stderr)
        sys.exit(1)

    print("Done.")

    if force_push:
        print(f"Force pushing to {remote}/{branch}...")
        push_result = subprocess.run(
            ["git", "push", "--force", remote, branch],
            text=True, cwd=cwd,
        )
        if push_result.returncode != 0:
            print("Force push failed.", file=sys.stderr)
            sys.exit(1)
        print("Pushed.")
    else:
        print("You likely need to force push:")
        print(f"  git push --force {remote} {branch}")


def check_gh_cli():
    """Verify gh CLI is installed and authenticated."""
    result = run(["gh", "auth", "status"])
    if result.returncode != 0:
        print("Error: gh CLI is not installed or not authenticated.", file=sys.stderr)
        print("Install: https://cli.github.com/", file=sys.stderr)
        print("Auth:    gh auth login", file=sys.stderr)
        sys.exit(1)


def resolve_pr(pr_arg):
    """Parse a PR number or URL into (owner, repo, number)."""
    if pr_arg.isdigit():
        # PR number — need to infer owner/repo from gh context or current repo
        result = run(["gh", "repo", "view", "--json", "owner,name"])
        if result.returncode != 0:
            print("Error: could not determine repo. Use a full PR URL instead.",
                  file=sys.stderr)
            sys.exit(1)
        data = json.loads(result.stdout)
        return data["owner"]["login"], data["name"], int(pr_arg)

    # Try to parse as URL: https://github.com/owner/repo/pull/123
    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_arg
    )
    if match:
        return match.group(1), match.group(2), int(match.group(3))

    print(f"Error: could not parse PR argument: {pr_arg}", file=sys.stderr)
    print("Use a PR number (e.g. 42) or URL (e.g. https://github.com/owner/repo/pull/42)",
          file=sys.stderr)
    sys.exit(1)


def fetch_pr_metadata(owner, repo, number):
    """Fetch PR metadata via gh CLI."""
    result = run([
        "gh", "pr", "view", str(number),
        "-R", f"{owner}/{repo}",
        "--json", "headRefName,baseRefName,headRepository,headRepositoryOwner,state,title,url",
    ])
    if result.returncode != 0:
        print(f"Error: could not fetch PR #{number} from {owner}/{repo}.",
              file=sys.stderr)
        print(result.stderr.strip(), file=sys.stderr)
        sys.exit(1)

    data = json.loads(result.stdout)

    if data["state"] != "OPEN":
        print(f"Error: PR #{number} is {data['state'].lower()}, not open.",
              file=sys.stderr)
        sys.exit(1)

    head_repo = data["headRepository"]
    head_owner = data["headRepositoryOwner"]
    clone_url = f"https://github.com/{head_owner['login']}/{head_repo['name']}.git"

    return {
        "headRefName": data["headRefName"],
        "baseRefName": data["baseRefName"],
        "clone_url": clone_url,
        "state": data["state"],
        "title": data["title"],
        "url": data["url"],
    }


def clone_pr_repo(clone_url, branch, base_branch):
    """Shallow-clone a repo into a temp directory and check out the PR branch."""
    tmpdir = tempfile.mkdtemp(prefix="git-sign-pr-")
    print(f"Cloning {clone_url} into {tmpdir}...")

    result = subprocess.run(
        ["git", "clone", "--depth=1", f"--branch={base_branch}", clone_url, tmpdir],
        text=True,
    )
    if result.returncode != 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print("Error: clone failed.", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching branch {branch}...")
    result = subprocess.run(
        ["git", "fetch", "origin", f"{branch}:{branch}", "--depth=50"],
        cwd=tmpdir, text=True,
    )
    if result.returncode != 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"Error: could not fetch branch {branch}.", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        ["git", "checkout", branch],
        cwd=tmpdir, text=True,
    )
    if result.returncode != 0:
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"Error: could not checkout branch {branch}.", file=sys.stderr)
        sys.exit(1)

    # Ensure we have the base branch ref for diffing
    subprocess.run(
        ["git", "fetch", "origin", base_branch, "--depth=50"],
        cwd=tmpdir, text=True,
    )

    return tmpdir


def merge_pr(owner, repo, number):
    """Merge a PR via gh CLI."""
    print(f"Merging PR #{number}...")
    result = run(["gh", "pr", "merge", str(number), "-R", f"{owner}/{repo}", "--merge"])
    if result.returncode != 0:
        print("Error: merge failed.", file=sys.stderr)
        print(result.stderr.strip(), file=sys.stderr)
        sys.exit(1)
    print(f"PR #{number} merged.")


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


def handle_pr(args):
    """Handle the --pr workflow: resolve PR, clone, sign, push, optionally merge."""
    # Phase 1: Check prerequisites
    check_gh_cli()
    validate_signing_key()

    # Phase 2: Resolve PR metadata
    owner, repo, number = resolve_pr(args.pr)
    meta = fetch_pr_metadata(owner, repo, number)

    pr_branch = meta["headRefName"]
    base_branch = meta["baseRefName"]
    clone_url = meta["clone_url"]
    pr_title = meta["title"]
    pr_url = meta["url"]

    if not args.yes and not args.dry_run:
        print(f"PR: {pr_url}")
        print(f"  Title:  {pr_title}")
        print(f"  Branch: {pr_branch} -> {base_branch}")
        print(f"  Repo:   {clone_url}")
        print()
        print("This will shallow-clone the repo, squash & sign commits, and force push.")
        if args.merge:
            print("After signing, the PR will be merged.")
        try:
            answer = input("Proceed? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(1)
        if answer != "y":
            sys.exit(1)

    if args.dry_run:
        print(f"Dry run -- would sign PR {pr_url}:")
        print(f"  Clone:    git clone --depth=1 --branch {base_branch} {clone_url} <tmpdir>")
        print(f"  Fetch:    git fetch origin {pr_branch} --depth=50")
        print(f"  Checkout: git checkout {pr_branch}")
        print(f"  Diff:     git diff --binary origin/{base_branch} {pr_branch}")
        print(f"  Reset:    git reset --hard origin/{base_branch}")
        print(f"  Apply:    git apply <diff>")
        print(f"  Commit:   git commit -S -m \"{args.message or pr_title}\"")
        print(f"  Push:     git push --force origin {pr_branch}")
        if args.merge:
            print(f"  Merge:    gh pr merge {number} -R {owner}/{repo}")
        return

    # Phase 3: Clone into temp dir
    tmpdir = clone_pr_repo(clone_url, pr_branch, base_branch)
    try:
        # Phase 4: Sign commits in temp clone
        message = args.message or pr_title
        remote_base = f"origin/{base_branch}"
        sign_commits(
            pr_branch, "origin", remote_base,
            force_push=True, message=message, cwd=tmpdir,
        )

        # Phase 5: Merge if requested
        if args.merge:
            merge_pr(owner, repo, number)
    finally:
        print(f"Cleaning up {tmpdir}...")
        shutil.rmtree(tmpdir, ignore_errors=True)


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
        "--pr",
        metavar="PR",
        help="GitHub PR number or URL to sign (requires gh CLI)",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="merge the PR after signing (requires --pr)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()

    if args.merge and not args.pr:
        parser.error("--merge requires --pr")

    if args.pr:
        handle_pr(args)
    else:
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
