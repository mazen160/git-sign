# git-sign

## Enforce Commit Signing for AI Agents

Re-sign commits on a branch with your GPG or SSH key. Built for stamping PRs created by AI coding agents.

---

# Why?

AI coding agents, including Claude, Cursor, ChatGPT Codex, Gemini, Github Copilot do not support signing git commits as of today (Feb 23, 2026). When AI Agents create pull requests, every commit shows up as "Unverified", and there is no way to supply a GPG or SSH key to sign the agent's PR. If you are trying to ensure commit signing on your organization without affecting developer experience, you'll hit a blocker.

**git-sign** fixes this. Point it at a PR and it squashes the commits into a single signed commit:

It works with GPG and SSH signing. Whatever you have configured in `git config`, git-sign uses it.

---

# Features

- Squashes all branch commits into a single signed commit.
- Auto-detects the base branch from the remote HEAD.
- Refuses to run on main/master to prevent accidental history rewrites.
- Opens your editor for the commit message, or pass `-m` to set it inline.
- `--dry-run` to preview what would happen.
- `--force-push` to push after signing without a separate command.
- `--yes` to skip the confirmation prompt (useful in scripts).
- `--base` to specify a custom base branch.
- `--pr` to sign a GitHub PR by number or URL without cloning manually (requires `gh` CLI).
- `--merge` to merge the PR after signing (used with `--pr`).
- No dependencies beyond Python 3.7+ and git (`gh` CLI required only for `--pr`).

---

# Installation

From PyPI:
```shell
pip install git-sign
```

From source:
```shell
git clone https://github.com/mazen160/git-sign.git
cd git-sign
pip install .
```

Or just run the script directly:
```shell
python git-sign.py
```

---

# Usage

Squash and sign all commits on the current branch (opens editor for commit message):
```shell
git-sign
```

With an inline commit message:
```shell
git-sign -m "Add user authentication"
```

Skip the confirmation prompt:
```shell
git-sign --yes
```

Sign and force push in one step:
```shell
git-sign --yes --force-push -m "Add user authentication"
```

Preview without making changes:
```shell
git-sign --dry-run
```

Use a specific base branch:
```shell
git-sign --base develop
```

---

# PR Workflow

Sign a PR directly by number (when inside the repo):
```shell
git-sign --pr 42
```

Or by full URL (works from any directory):
```shell
git-sign --pr https://github.com/owner/repo/pull/42
```

Sign and merge in one command:
```shell
git-sign --pr https://github.com/owner/repo/pull/42 --merge -y -m "Add user authentication"
```

Preview without making changes:
```shell
git-sign --pr 42 --dry-run
```

The PR workflow:
1. Resolves the PR's source branch, base branch, and repo via `gh pr view`.
2. Shallow-clones the repo into a temp directory.
3. Squashes and signs the commits on the PR branch.
4. Force-pushes the signed branch back.
5. Optionally merges the PR (with `--merge`).
6. Cleans up the temp directory.

This requires the [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated (`gh auth login`).

---

# How it works

git-sign diffs your branch against the remote base, resets to the base, applies the diff, and commits everything as a single signed commit:

```shell
git diff --binary origin/main feature-branch > /tmp/patch
git reset --hard origin/main
git apply /tmp/patch
git add .
git commit -S
```

All your changes end up in one signed commit. You force push the branch, and the PR shows as verified.

This squashes history on purpose. AI agents tend to produce noisy commit logs ("fix lint", "update test", "try again"). One clean signed commit is better.

When using `--pr`, this same process runs inside a temporary clone -- you don't need to be in the repo or on the right branch.

---

# Requirements

- Python 3.7+
- Git
- [GitHub CLI (`gh`)](https://cli.github.com/) — only needed for `--pr` workflow
- A signing key configured in git:
  ```shell
  # GPG
  git config user.signingkey <your-gpg-key-id>

  # SSH
  git config gpg.format ssh
  git config user.signingkey ~/.ssh/id_ed25519.pub
  ```

---

# Contribution

Contributions are welcome. Report issues and open pull requests on GitHub.

---

# License

MIT License. See [LICENSE](LICENSE).

---

# Author

**Mazin Ahmed**

- **Website**: [https://mazinahmed.net](https://mazinahmed.net)
- **Email**: `mazin [at] mazinahmed [dot] net`
- **Twitter**: [https://twitter.com/mazen160](https://twitter.com/mazen160)
- **Linkedin**: [http://linkedin.com/in/infosecmazinahmed](http://linkedin.com/in/infosecmazinahmed)
