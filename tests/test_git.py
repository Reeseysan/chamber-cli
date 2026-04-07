"""Tests for git module."""
from __future__ import annotations

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from chamber.git import get_git_diff, get_git_pr_diff, is_git_repo, GitError


@patch("chamber.git._run_git")
def test_is_git_repo_true(mock_run):
    mock_run.return_value = "true"
    assert is_git_repo() is True


@patch("chamber.git._run_git")
def test_is_git_repo_false(mock_run):
    mock_run.side_effect = GitError("not a repo")
    assert is_git_repo() is False


@patch("chamber.git.is_git_repo", return_value=True)
@patch("chamber.git._run_git")
def test_get_git_diff_unstaged(mock_run, mock_repo):
    mock_run.return_value = "+added line\n-removed line\n"
    result = get_git_diff(staged=False)
    assert "[DOCUMENT: Git Diff" in result
    assert "Unstaged" in result
    assert "+added line" in result


@patch("chamber.git.is_git_repo", return_value=True)
@patch("chamber.git._run_git")
def test_get_git_diff_staged(mock_run, mock_repo):
    mock_run.return_value = "+staged change\n"
    result = get_git_diff(staged=True)
    assert "Staged" in result
    assert "+staged change" in result


@patch("chamber.git.is_git_repo", return_value=True)
@patch("chamber.git._run_git")
def test_get_git_diff_empty_raises(mock_run, mock_repo):
    mock_run.return_value = ""
    with pytest.raises(GitError, match="No unstaged changes"):
        get_git_diff(staged=False)


@patch("chamber.git.is_git_repo", return_value=False)
def test_get_git_diff_not_repo(mock_repo):
    with pytest.raises(GitError, match="Not inside"):
        get_git_diff()


@patch("chamber.git.is_git_repo", return_value=True)
@patch("chamber.git.shutil.which", return_value=None)
@patch("chamber.git._run_git")
def test_get_git_pr_diff_without_gh(mock_run, mock_which, mock_repo):
    mock_run.side_effect = [
        "feature-branch\n",  # rev-parse
        "+pr diff content\n",  # git diff
    ]
    result = get_git_pr_diff(pr_number=42)
    assert "PR #42" in result
    assert "+pr diff content" in result


@patch("chamber.git.is_git_repo", return_value=True)
@patch("chamber.git._run_git")
def test_get_git_pr_diff_no_number(mock_run, mock_repo):
    mock_run.side_effect = [
        "my-branch\n",
        "+branch diff\n",
    ]
    result = get_git_pr_diff()
    assert "my-branch" in result
