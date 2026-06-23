from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from detect import detect


def write_file(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    return repo


def test_detect_missing_repo_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        detect(tmp_path / "missing-repo")


def test_detect_rejects_file_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo.txt"
    repo.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ValueError):
        detect(repo)


def test_detect_rejects_invalid_package_json(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "package.json", "{")

    with pytest.raises(ValueError):
        detect(repo)


def test_detect_rejects_unsupported_repo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "README.md", "# hello")

    with pytest.raises(ValueError):
        detect(repo)


def test_detect_ignores_signals_inside_skipped_dirs(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, ".venv/app.py", "from fastapi import FastAPI\napp = FastAPI()")
    write_file(repo, "node_modules/package.json", json.dumps({"dependencies": {"react": "^18.0.0"}}))
    write_file(repo, "README.md", "nothing useful here")

    with pytest.raises(ValueError):
        detect(repo)


def test_detect_react_with_preview_script(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"react": "^18.0.0"},
                "scripts": {
                    "build": "vite build",
                    "preview": "vite preview",
                },
            }
        ),
    )

    result = detect(repo)

    assert result["framework"] == "react"
    assert result["port"] == 5173
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run preview"


def test_detect_react_falls_back_to_start_script_when_preview_missing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"react": "^18.0.0"},
                "scripts": {
                    "build": "vite build",
                    "start": "vite preview",
                },
            }
        ),
    )

    result = detect(repo)

    assert result["framework"] == "react"
    assert result["port"] == 5173
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run start"


def test_detect_next_from_package_json_and_scripts(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {
                    "next": "^15.0.0",
                    "react": "^18.0.0",
                    "react-dom": "^18.0.0",
                },
                "scripts": {
                    "build": "next build",
                    "start": "next start",
                },
            }
        ),
    )
    write_file(repo, "pages/index.tsx", "export default function Home() { return <div>Hello</div>; }")

    result = detect(repo)

    assert result["framework"] == "next"
    assert result["port"] == 3000
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run start"


def test_detect_next_wins_over_react_when_both_dependencies_exist(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {
                    "react": "^18.0.0",
                    "react-dom": "^18.0.0",
                    "next": "^15.0.0",
                },
                "scripts": {
                    "build": "next build",
                    "start": "next start",
                },
            }
        ),
    )

    result = detect(repo)

    assert result["framework"] == "next"
    assert result["port"] == 3000
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run start"


def test_detect_next_from_next_config_without_package_json(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "next.config.js", "module.exports = {};")
    write_file(repo, "pages/index.js", "export default function Home() { return <div>Hello</div>; }")

    result = detect(repo)

    assert result["framework"] == "next"
    assert result["port"] == 3000
    assert result["build_command"] == "npx next build"
    assert result["start_command"] == "npx next start -p 3000 -H 0.0.0.0"


def test_detect_next_uses_detected_port_from_comment_when_no_start_script(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"next": "^15.0.0"},
                "scripts": {
                    "build": "next build",
                },
            }
        ),
    )
    write_file(repo, "server.js", "// npx next start -p 4000\n")

    result = detect(repo)

    assert result["framework"] == "next"
    assert result["port"] == 4000
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npx next start -p 4000 -H 0.0.0.0"


def test_detect_nuxt_from_package_json_and_scripts(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"nuxt": "^4.0.0"},
                "scripts": {
                    "build": "nuxt build",
                    "start": "nuxt preview",
                },
            }
        ),
    )
    write_file(repo, "app.vue", "<template><div>Hello</div></template>")

    result = detect(repo)

    assert result["framework"] == "nuxt"
    assert result["port"] == 3000
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run start"


def test_detect_nuxt_wins_over_vue_when_both_dependencies_exist(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {
                    "vue": "^3.0.0",
                    "nuxt": "^4.0.0",
                },
                "scripts": {
                    "build": "nuxt build",
                    "start": "nuxt preview",
                },
            }
        ),
    )

    result = detect(repo)

    assert result["framework"] == "nuxt"
    assert result["port"] == 3000
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run start"


def test_detect_nuxt_from_nuxt_config_without_package_json(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "nuxt.config.ts", "export default defineNuxtConfig({});")
    write_file(repo, "app.vue", "<template><div>Hello</div></template>")
    write_file(repo, "server.ts", "// npx nuxi preview --host 0.0.0.0 --port 4555\n")

    result = detect(repo)

    assert result["framework"] == "nuxt"
    assert result["port"] == 4555
    assert result["build_command"] == "npx nuxi build"
    assert result["start_command"] == "npx nuxi preview --host 0.0.0.0 --port 4555"


def test_detect_vue_from_package_json_and_scripts(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"vue": "^3.0.0"},
                "scripts": {
                    "build": "vite build",
                    "preview": "vite preview",
                },
            }
        ),
    )
    write_file(repo, "src/App.vue", "<template><div>Hello</div></template>")

    result = detect(repo)

    assert result["framework"] == "vue"
    assert result["port"] == 5173
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run preview"


def test_detect_vue_from_vue_file_without_package_json(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "src/components/App.vue", "<template><div>Hello</div></template>")

    result = detect(repo)

    assert result["framework"] == "vue"
    assert result["port"] == 5173
    assert result["build_command"] == "vite build"
    assert result["start_command"] == "serve -s dist -l 5173"


def test_detect_vue_falls_back_to_start_script_when_preview_missing(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "package.json",
        json.dumps(
            {
                "dependencies": {"vue": "^3.0.0"},
                "scripts": {
                    "build": "vite build",
                    "start": "vite preview",
                },
            }
        ),
    )

    result = detect(repo)

    assert result["framework"] == "vue"
    assert result["port"] == 5173
    assert result["build_command"] == "npm run build"
    assert result["start_command"] == "npm run start"


def test_detect_django_from_requirements_and_manage_py(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "requirements.txt", "django\nasgiref\n")
    write_file(
        repo,
        "manage.py",
        "import django\n"
        "# python manage.py runserver 0.0.0.0:9090\n",
    )

    result = detect(repo)

    assert result["framework"] == "django"
    assert result["port"] == 9090
    assert result["build_command"] is None
    assert result["start_command"] == "python manage.py runserver 0.0.0.0:9090"


def test_detect_django_from_manage_py_without_requirements(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(
        repo,
        "manage.py",
        "import django\n"
        "from django.core.management import execute_from_command_line\n"
        "# runserver 8001\n",
    )

    result = detect(repo)

    assert result["framework"] == "django"
    assert result["port"] == 8001
    assert result["build_command"] is None
    assert result["start_command"] == "python manage.py runserver 0.0.0.0:8001"


def test_detect_fastapi_from_requirements_and_source_port(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "requirements.txt", "fastapi\nuvicorn\n")
    write_file(
        repo,
        "main.py",
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n"
        "# uvicorn main:app --host 0.0.0.0 --port 9000\n",
    )

    result = detect(repo)

    assert result["framework"] == "fastapi"
    assert result["port"] == 9000
    assert result["build_command"] is None
    assert result["start_command"] == "uvicorn main:app --host 0.0.0.0 --port 9000"


def test_detect_flask_nested_module_and_port(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "requirements.txt", "flask\n")
    write_file(
        repo,
        "src/api/app.py",
        "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "# flask run --host 0.0.0.0 --port 5050\n",
    )

    result = detect(repo)

    assert result["framework"] == "flask"
    assert result["port"] == 5050
    assert result["build_command"] is None
    assert result["start_command"] == "flask --app src.api.app run --host 0.0.0.0 --port 5050"


def test_detect_static_repo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_file(repo, "index.html", "<!doctype html><html><body>Hello</body></html>")
    write_file(repo, "styles.css", "body { margin: 0; }")

    result = detect(repo)

    assert result["framework"] == "static"
    assert result["port"] == 80
    assert result["build_command"] is None
    assert result["start_command"] is None