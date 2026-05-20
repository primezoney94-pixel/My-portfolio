import os
import uvicorn
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, HttpUrl, validator

# ─── Constants ────────────────────────────────────────────────────────────────
DATABASE_URL = "sqlite:///./portfolio.db"
ADMIN_PASSWORD = "SUPER_ADMIN_2026"
VALID_CATEGORIES = {"Bot", "Website", "AI"}

# ─── Database Setup ───────────────────────────────────────────────────────────
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ProjectModel(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(String(2000), nullable=False)
    image_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


Base.metadata.create_all(bind=engine)


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    title: str
    category: str
    description: str
    image_url: Optional[str] = None
    github_url: Optional[str] = None

    @validator("title")
    def title_must_not_be_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("title cannot be empty")
        if len(v) > 200:
            raise ValueError("title cannot exceed 200 characters")
        return v

    @validator("category")
    def category_must_be_valid(cls, v):
        if v not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(VALID_CATEGORIES)}")
        return v

    @validator("description")
    def description_must_not_be_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("description cannot be empty")
        if len(v) > 2000:
            raise ValueError("description cannot exceed 2000 characters")
        return v

    @validator("image_url", "github_url", pre=True, always=True)
    def url_optional_empty(cls, v):
        if v is None or v.strip() == "":
            return None
        return v.strip()


class ProjectResponse(BaseModel):
    id: int
    title: str
    category: str
    description: str
    image_url: Optional[str]
    github_url: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Portfolio API",
    description="Production-ready Portfolio & Admin Panel API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Dependencies ─────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_admin(x_admin_password: Optional[str] = Header(None)):
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail={"error": "Unauthorized", "message": "Invalid admin password"},
        )
    return True


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {
        "status": "online",
        "service": "Portfolio API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/projects", response_model=list[ProjectResponse], tags=["Projects"])
def get_projects(db: Session = Depends(get_db)):
    projects = db.query(ProjectModel).order_by(desc(ProjectModel.created_at)).all()
    return projects


@app.post(
    "/api/projects",
    response_model=ProjectResponse,
    status_code=201,
    tags=["Projects"],
)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
):
    db_project = ProjectModel(
        title=project.title,
        category=project.category,
        description=project.description,
        image_url=project.image_url,
        github_url=project.github_url,
        created_at=datetime.utcnow(),
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project


@app.delete("/api/projects/{project_id}", tags=["Projects"])
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin),
):
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=404,
            detail={"error": "Not Found", "message": f"Project with id {project_id} not found"},
        )
    db.delete(project)
    db.commit()
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": f"Project {project_id} deleted successfully"},
    )


# ─── Exception Handlers ───────────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Not Found", "message": "The requested resource was not found"},
    )


@app.exception_handler(500)
async def server_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": "An unexpected error occurred"},
    )


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
