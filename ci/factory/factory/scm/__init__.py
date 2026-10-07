"""The platform the factory runs on, chosen by FACTORY_SCM (github by default)."""

import os

from .base import SCM, SCMError
from .github import GitHubAdapter
from .gitlab import GitLabAdapter

__all__ = ["SCM", "SCMError", "GitHubAdapter", "GitLabAdapter", "get_scm"]


def get_scm(env=os.environ) -> SCM:
    kind = (env.get("FACTORY_SCM") or "github").lower()
    if kind == "github":
        return GitHubAdapter(env.get("GITHUB_REPOSITORY") or "")
    if kind == "gitlab":
        return GitLabAdapter(env.get("CI_PROJECT_ID"))
    raise ValueError(f"unknown FACTORY_SCM: {kind}")
