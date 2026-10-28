import logging

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import administration
from app.api.routes import product
from app.api.routes import backups
from app.api.routes import drafts, student_imports, academic_years
from app.api.routes import curriculum
from app.api.routes import dashboards, academic_documents, final_grades, grading_policy, progression
from app.core.config import settings
from app.core.deps import get_current_context, AuthContext
from app.core.exception_handlers import register_exception_handlers
from app.core.security_headers import SecurityHeadersMiddleware

from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserSummary

from app.api.routes import auth, invitations, platform, teaching, learning, contact, workspace_access

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Learning Institution Management System API")

register_exception_handlers(app)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(workspace_access.router)
app.include_router(contact.router)
app.include_router(platform.router)
app.include_router(invitations.router)
app.include_router(teaching.router)
app.include_router(learning.router)
app.include_router(administration.router)
app.include_router(product.router)
app.include_router(backups.router)
app.include_router(drafts.router)
app.include_router(student_imports.router)
app.include_router(academic_years.router)
app.include_router(curriculum.router)
app.include_router(dashboards.router)
app.include_router(academic_documents.router)
app.include_router(final_grades.router)
app.include_router(grading_policy.router)
app.include_router(progression.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/me", response_model=UserSummary)
def get_me(ctx: AuthContext = Depends(get_current_context), db: Session = Depends(get_db)):
    user = db.get(User, ctx.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    summary = UserSummary.model_validate(user)
    return summary.model_copy(update={"must_change_password": False}) if ctx.actor_user_id else summary
