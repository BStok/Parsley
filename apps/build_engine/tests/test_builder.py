from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from builder import BuildError, build


def write_file(repo: Path, relative_path: str, content: str = "") -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "demo-app"
    repo.mkdir()
    return repo


def detection(framework: str = "react", *, port: int = 5173, start_command: str | None = "npm run preview", build_command: str | None = "npm run build") -> dict:
    data: dict[str, object | None] = {
        "framework": framework,
        "port": port,
        "start_command": start_command,
        "build_command": build_command,
    }
    return data  # type: ignore[return-value]


def template_file(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text("PORT={{PORT}}\nSTART={{START_COMMAND}}\nBUILD={{BUILD_COMMAND}}\n", encoding="utf-8")
    return path


def test_missing_repo_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build(tmp_path / "missing", detection())


def test_repo_path_must_be_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError):
        build(file_path, detection())


def test_detection_must_be_mapping(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with pytest.raises(TypeError):
        build(repo, "not-a-dict")  # type: ignore[arg-type]


def test_invalid_framework(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with pytest.raises(ValueError):
        build(repo, {"framework": "svelte"})


def test_invalid_tag(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with pytest.raises(ValueError):
        build(repo, detection(), image_repository="demo/image", tag="bad tag")


def test_missing_template(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with patch("builder._template_path") as mock_template:
        mock_template.side_effect = FileNotFoundError("template missing")

        with pytest.raises(FileNotFoundError):
            build(repo, detection(), image_repository="demo/image")


def test_requires_image_repository_or_env(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError):
            build(repo, detection())


def test_image_repository_is_trimmed(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with patch("builder._template_path", return_value=template_file(tmp_path, "react-vite.dockerfile")):
        with patch("builder._run"):
            result = build(repo, detection(), image_repository="  demo/image  ")

    assert result["image"] == "demo/image:latest"


def test_image_repository_rejects_internal_whitespace(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    with pytest.raises(ValueError):
        build(repo, detection(), image_repository="demo /image")


def test_image_name_from_env(tmp_path: Path, monkeypatch) -> None:
    repo = make_repo(tmp_path)

    monkeypatch.setenv("DOCKERHUB_USERNAME", "sadie")

    with patch("builder._run"):
        with patch("builder._template_path", return_value=template_file(tmp_path, "react-vite.dockerfile")):
            result = build(repo, detection())

    assert result["image"] == "sadie/demo-app:latest"


@pytest.mark.parametrize(
    "framework,template_name,port,expected_build,expected_start",
    [
        ("react", "react-vite.dockerfile", 5173, "npm run build", "serve -s dist -l 5173"),
        ("vue", "vue.dockerfile", 5173, "npm run build", "serve -s dist -l 5173"),
        ("next", "next.dockerfile", 3000, "npm run build", "npx next start -p 3000 -H 0.0.0.0"),
        ("nuxt", "nuxt.dockerfile", 3000, "npm run build", "npx nuxi preview --host 0.0.0.0 --port 3000"),
        ("express", "express.dockerfile", 3000, "npm install", "node index.js"),
        ("fastapi", "fastapi.dockerfile", 8000, "pip install --no-cache-dir -r requirements.txt", "uvicorn main:app --host 0.0.0.0 --port 8000"),
        ("flask", "flask.dockerfile", 5000, "pip install --no-cache-dir -r requirements.txt", "flask run --host 0.0.0.0 --port 5000"),
        ("django", "django.dockerfile", 8000, "pip install --no-cache-dir -r requirements.txt", "python manage.py runserver 0.0.0.0:8000"),
        ("static", "static.dockerfile", 8000, "true", "python -m http.server 8000 --bind 0.0.0.0"),
    ],
)
def test_supported_frameworks_use_defaults_when_detection_omits_commands(
    tmp_path: Path,
    framework: str,
    template_name: str,
    port: int,
    expected_build: str,
    expected_start: str,
) -> None:
    repo = make_repo(tmp_path)
    dockerfile = template_file(tmp_path, template_name)

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run"):
            result = build(
                repo,
                {
                    "framework": framework,
                    "port": port,
                    "build_command": None,
                    "start_command": None,
                },
                image_repository="demo/image",
            )

    assert result["framework"] == framework
    assert result["port"] == port
    assert result["build_command"] == expected_build
    assert result["start_command"] == expected_start
    assert result["template"] == str(dockerfile)
    assert result["image"] == "demo/image:latest"


@pytest.mark.parametrize(
    "framework,template_name,port,build_command,start_command",
    [
        ("react", "react-vite.dockerfile", 5173, "vite build", "vite preview"),
        ("vue", "vue.dockerfile", 5173, "vite build", "vite preview"),
        ("next", "next.dockerfile", 3001, "pnpm build", "pnpm start"),
        ("nuxt", "nuxt.dockerfile", 3002, "pnpm build", "pnpm start"),
        ("express", "express.dockerfile", 3003, "npm run build", "node server.js"),
        ("fastapi", "fastapi.dockerfile", 8004, "pip install -r requirements.txt", "uvicorn app.main:app --host 0.0.0.0 --port 8004"),
        ("flask", "flask.dockerfile", 5005, "pip install -r requirements.txt", "flask --app app run --host 0.0.0.0 --port 5005"),
        ("django", "django.dockerfile", 8006, "pip install -r requirements.txt", "python manage.py runserver 0.0.0.0:8006"),
        ("static", "static.dockerfile", 8080, "true", "python -m http.server 8080 --bind 0.0.0.0"),
    ],
)
def test_supported_frameworks_preserve_explicit_detection_commands(
    tmp_path: Path,
    framework: str,
    template_name: str,
    port: int,
    build_command: str,
    start_command: str,
) -> None:
    repo = make_repo(tmp_path)
    dockerfile = template_file(tmp_path, template_name)

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run"):
            result = build(
                repo,
                {
                    "framework": framework,
                    "port": port,
                    "build_command": build_command,
                    "start_command": start_command,
                },
                image_repository="demo/image",
                tag="v1",
            )

    assert result["framework"] == framework
    assert result["port"] == port
    assert result["build_command"] == build_command
    assert result["start_command"] == start_command
    assert result["image"] == "demo/image:v1"


def test_react_uses_provided_start_command_when_present(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    dockerfile = template_file(tmp_path, "react-vite.dockerfile")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run"):
            result = build(
                repo,
                {
                    "framework": "react",
                    "port": 5173,
                    "start_command": "npm run preview",
                    "build_command": "npm run build",
                },
                image_repository="demo/react",
            )

    assert result["start_command"] == "npm run preview"


def test_docker_build_and_push_are_called(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    dockerfile = template_file(tmp_path, "react-vite.dockerfile")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run") as mock_run:
            build(
                repo,
                detection(),
                image_repository="demo/image",
            )

    assert mock_run.call_count == 2

    first_call = mock_run.call_args_list[0][0][0]
    second_call = mock_run.call_args_list[1][0][0]

    assert first_call[:2] == ["docker", "build"]
    assert second_call[:2] == ["docker", "push"]


def test_docker_failure_bubbles_up(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    dockerfile = template_file(tmp_path, "react-vite.dockerfile")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run", side_effect=BuildError("docker failed")):
            with pytest.raises(BuildError):
                build(
                    repo,
                    detection(),
                    image_repository="demo/image",
                )


def test_successful_build_returns_metadata(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "package.json", "{}")
    dockerfile = template_file(tmp_path, "react-vite.dockerfile")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run"):
            result = build(
                repo,
                detection(),
                image_repository="demo/image",
                tag="v1",
            )

    assert result["image"] == "demo/image:v1"
    assert result["framework"] == "react"
    assert result["port"] == 5173
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run preview"


def test_excluded_directories_do_not_break_build(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)

    write_file(repo, "node_modules/big.js", "ignore")
    write_file(repo, ".git/config", "ignore")
    write_file(repo, "__pycache__/a.pyc", "ignore")
    write_file(repo, "app.py", "print('hello')")

    dockerfile = template_file(tmp_path, "flask.dockerfile")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run"):
            result = build(
                repo,
                {
                    "framework": "flask",
                    "port": 5000,
                    "start_command": "flask run",
                    "build_command": None,
                },
                image_repository="demo/flask",
            )

    assert result["framework"] == "flask"


def test_static_build_uses_true_command_when_build_command_missing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "index.html", "<!doctype html><html><body>Hello</body></html>")
    dockerfile = template_file(tmp_path, "static.dockerfile")

    with patch("builder._template_path", return_value=dockerfile):
        with patch("builder._run"):
            result = build(
                repo,
                {
                    "framework": "static",
                    "port": 8080,
                    "build_command": None,
                    "start_command": None,
                },
                image_repository="demo/static",
            )

    assert result["build_command"] == "true"
    assert result["start_command"] == "python -m http.server 8080 --bind 0.0.0.0"