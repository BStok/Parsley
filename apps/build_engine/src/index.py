from clone import clone_repo
from detect import detect
from builder import build
import shutil


def run_pipeline(project_id: str, repo_url: str, docker_username: str) -> dict:
    """
    Orchestrates the full build pipeline for a project.
    Returns a dict with image_tag and detected project info.
    """

    repo_path = None

    try:
        # Step 1 — clone repo
        print(f"[1/3] Cloning {repo_url}...")
        repo_path = clone_repo(project_id, repo_url)

        # Step 2 — detect the framework
        print(f"[2/3] Detecting framework...")
        detected = detect(repo_path)
        print(f"      → {detected['framework']} on port {detected['port']}")

        # Step 3 — build and push Docker image
        print(f"[3/3] Building and pushing image...")
        image_tag = build(
            project_id=project_id,
            repo_path=repo_path,
            framework=detected["framework"],
            docker_username=docker_username
        )
        print(f"      → pushed {image_tag}")

        return {
            "image_tag":     image_tag,
            "framework":     detected["framework"],
            "port":          detected["port"],
            "start_command": detected["start_command"],
            "build_command": detected["build_command"]
        }

    except Exception as e:
        print(f"Pipeline failed: {e}")
        raise

    finally:
        # clean up the cloned repo
        if repo_path and repo_path.exists():
            shutil.rmtree(repo_path)
            print(f"Cleaned up {repo_path}")


if __name__ == "__main__":
    # local test
    result = run_pipeline(
        project_id="test-123", # <- PH
        repo_url="https://github.com/kjwdnkjwnwef", # <- PH
        docker_username="parsley" # <- PH
    )
    print(result)