from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from src.db.database import get_db
from src.db.models import Project, User
from src.lib.auth import get_current_user

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