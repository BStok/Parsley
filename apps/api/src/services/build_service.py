from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

BUILD_ENGINE_SRC = Path(__file__).resolve().parents[3] / "build_engine" / "src"

if str(BUILD_ENGINE_SRC) not in sys.path:
    sys.path.insert(0, str(BUILD_ENGINE_SRC))

from index import run_pipeline  # noqa: E402


def trigger_build(project: Any) -> dict[str, Any]:
    project_id = getattr(project, "project_id", None)
    repo_url = getattr(project, "repo_url", None)

    if not project_id:
        raise ValueError("Project is missing project_id")
    if not repo_url:
        raise ValueError("Project is missing repo_url")

    docker_username = os.getenv("DOCKERHUB_USERNAME")
    if not docker_username:
        raise ValueError("DOCKERHUB_USERNAME is not set")

    return run_pipeline(
        project_id=str(project_id),
        repo_url=str(repo_url),
        docker_username=docker_username.strip(),
    )