#!/usr/bin/env python3
"""The platform the factory runs on, chosen by FACTORY_SCM (github, the only adapter)."""

import os

from .base import SCM, SCMError
from .github import GitHubAdapter

__all__ = ["SCM", "SCMError", "GitHubAdapter", "get_scm"]


def get_scm(env=os.environ) -> SCM:
    kind = (env.get("FACTORY_SCM") or "github").lower()
    if kind == "github":
        return GitHubAdapter(env.get("GITHUB_REPOSITORY") or "")
    raise ValueError(f"unknown FACTORY_SCM: {kind}")
