from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from apps.api.src.db.database import get_db
from apps.api.src.db.models import Project, User
from apps.api.src.lib.auth import get_current_user

import threading
import sys
import os

from apps.build_engine.src.index import run_pipeline

router = APIRouter(prefix="/projects", tags=["projects"])

class CreateProjectBody(BaseModel):
    name: str
    repo_url: str

@router.post("/")
def create_project(
    body: CreateProjectBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    subdomain = body.name.lower().replace(" ", "-")
    
    existing = db.query(Project).filter(Project.subdomain == subdomain).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project name already taken")
    
    project = Project(
        project_id=str(uuid.uuid4()),
        user_id=current_user.user_id,
        name=body.name,
        repo_url=body.repo_url,
        subdomain=subdomain,
        status="pending"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return {
        "project_id": project.project_id,
        "name": project.name,
        "repo_url": project.repo_url,
        "subdomain": project.subdomain,
        "status": project.status
    }

@router.post("/{project_id}/deploy")
def deploy_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not your project")
    if project.status == "building":
        raise HTTPException(status_code=409, detail="Build already in progress")

    # Create a build record
    from apps.api.src.db.models import Build
    from datetime import datetime
    build = Build(
        build_id=str(uuid.uuid4()),
        project_id=project.project_id,
        status="queued",
        created_at=datetime.utcnow()
    )
    db.add(build)

    # Update project status
    project.status = "building"
    db.commit()
    db.refresh(build)

    # Run pipeline in background so endpoint returns immediately
    def run_build():
        try:
            result = run_pipeline(
                project_id=project.project_id,
                repo_url=project.repo_url,
                docker_username=os.getenv("DOCKER_USERNAME")
            )
            build.status = "success"
            build.image_tag = result["image_tag"]
            project.status = "running"
            project.framework = result["framework"]
            project.port = result["port"]
            project.start_command = result["start_command"]
        except Exception as e:
            build.status = "failed"
            project.status = "failed"
            print(f"Build failed: {e}")
        finally:
            from datetime import datetime
            build.finished_at = datetime.utcnow()
            db.commit()

    thread = threading.Thread(target=run_build)
    thread.start()

    return {
        "build_id": build.build_id,
        "status": "queued",
        "message": "Build started"
    }