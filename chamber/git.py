from __future__ import annotations

import subprocess
import shutil


class GitError(Exception):
    """Raised for git-related errors."""
    pass


def _run_git(*args: str) -> str:
    """Run a git command and return stdout."""
    git_bin = shutil.which("git")
    if not git_bin:
        raise GitError("git is not installed or not in PATH.")

    try:
        result = subprocess.run(
            [git_bin, *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise GitError("git command timed out.")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise GitError(f"git {' '.join(args)} failed: {stderr}")

    return result.stdout


def is_git_repo() -> bool:
    """Check if the current directory is inside a git repository."""
    try:
        _run_git("rev-parse", "--is-inside-work-tree")
        return True
    except GitError:
        return False


def get_git_diff(staged: bool = False) -> str:
    """Get the current git diff.
    
    Args:
        staged: If True, get staged changes (--staged). Otherwise, unstaged changes.
    
    Returns:
        Formatted diff text suitable for document_context.
    """
    if not is_git_repo():
        raise GitError("Not inside a git repository.")

    args = ["diff"]
    if staged:
        args.append("--staged")

    diff = _run_git(*args)
    if not diff.strip():
        label = "staged" if staged else "unstaged"
        raise GitError(f"No {label} changes found.")

    label = "Staged Changes" if staged else "Unstaged Changes"
    return f"[DOCUMENT: Git Diff — {label}]\n\n```diff\n{diff}\n```"


def get_git_pr_diff(pr_number: int | None = None, base_branch: str = "main") -> str:
    """Get the diff for the current branch against a base branch.
    
    This compares the current HEAD against the base branch (default: main).
    If gh CLI is available and pr_number is given, it fetches the PR diff directly.
    
    Args:
        pr_number: Optional PR number (uses gh CLI if available).
        base_branch: Base branch to diff against (default: "main").
    
    Returns:
        Formatted diff text.
    """
    if not is_git_repo():
        raise GitError("Not inside a git repository.")

    # Try gh CLI first if we have a PR number
    if pr_number is not None and shutil.which("gh"):
        try:
            result = subprocess.run(
                ["gh", "pr", "diff", str(pr_number)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return f"[DOCUMENT: Git PR #{pr_number} Diff]\n\n```diff\n{result.stdout}\n```"
        except subprocess.TimeoutExpired:
            pass  # Fall through to git diff

    # Fallback: diff current branch against base
    try:
        current = _run_git("rev-parse", "--abbrev-ref", "HEAD").strip()
    except GitError:
        raise GitError("Could not determine current branch.")

    diff = _run_git("diff", f"{base_branch}...{current}")
    if not diff.strip():
        raise GitError(f"No differences between {base_branch} and {current}.")

    label = f"PR #{pr_number}" if pr_number else f"{current} vs {base_branch}"
    return f"[DOCUMENT: Git Diff — {label}]\n\n```diff\n{diff}\n```"
