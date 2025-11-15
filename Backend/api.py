from datetime import datetime, date
from enum import Enum
from typing import List, Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from email_advising import (
    EmailAdvisor,
    TfidfRetriever,
    load_knowledge_base,
    load_reference_corpus,
)

# --- SQLAlchemy imports for SQLite persistence ---
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    Enum as SAEnum,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# =====================================================
# FastAPI app + CORS
# =====================================================

app = FastAPI(title="Email Advising System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# Load backend advising logic
# =====================================================

knowledge_base = load_knowledge_base()
reference_corpus = load_reference_corpus()
retriever = TfidfRetriever(reference_corpus)
advisor = EmailAdvisor(knowledge_base, retriever=retriever)

# =====================================================
# Database setup (SQLite + SQLAlchemy)
# =====================================================

DATABASE_URL = "sqlite:///./emails.db"  # file in Backend directory

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + threads
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# =====================================================
# Email models (Enum, Pydantic, SQLAlchemy ORM)
# =====================================================


class EmailStatus(str, Enum):
    auto = "auto"      # approved / high-confidence
    review = "review"  # needs manual review


# ---------- Pydantic models (API schemas) ----------


class EmailIn(BaseModel):
    """
    Payload when a *new email* arrives to the system.
    This is what your ingestion script or frontend button sends.
    """
    student_name: Optional[str] = None
    subject: str
    body: str
    received_at: Optional[datetime] = None


class Email(BaseModel):
    """
    Full email object as stored/returned by the backend.
    """
    id: int
    student_name: Optional[str] = None
    subject: str
    body: str
    confidence: float
    status: EmailStatus
    suggested_reply: str
    received_at: datetime


class EmailUpdate(BaseModel):
    """
    Fields that can be updated by the advisor (or system).
    Supports changing status and editing the suggested_reply text.
    """
    status: Optional[EmailStatus] = None
    suggested_reply: Optional[str] = None


# ---------- SQLAlchemy ORM model (DB table) ----------


class EmailORM(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    student_name = Column(String, nullable=True)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(SAEnum(EmailStatus), nullable=False)
    suggested_reply = Column(Text, nullable=False)
    received_at = Column(DateTime, nullable=False, index=True)


# Create tables if they don't exist yet
Base.metadata.create_all(bind=engine)


# ---------- Utility: DB session + conversion ----------

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def orm_to_schema(email: EmailORM) -> Email:
    return Email(
        id=email.id,
        student_name=email.student_name,
        subject=email.subject,
        body=email.body,
        confidence=email.confidence,
        status=email.status,
        suggested_reply=email.suggested_reply,
        received_at=email.received_at,
    )


CONFIDENCE_THRESHOLD = 0.9  # >= this → auto, else review

# =====================================================
# Endpoint: ingest email
# =====================================================


@app.post("/emails/ingest", response_model=Email)
def ingest_email(email_in: EmailIn):
    """
    Simulate 'an email came into the advisor inbox'.

    1. Run the EmailAdvisor on the email body.
    2. Decide if it's auto or review based on confidence.
    3. Store it in SQLite.
    4. Return the stored email object.
    """
    received_at = email_in.received_at or datetime.utcnow()

    # Run advisor on the body (what the student actually wrote)
    result = advisor.process_query(
        email_in.body,
        {"student_name": email_in.student_name},
    )

    confidence = float(result.confidence or 0.0)
    suggested_reply = result.body

    # Simple policy: high confidence => auto, otherwise => review
    status = EmailStatus.auto if confidence >= CONFIDENCE_THRESHOLD else EmailStatus.review

    db = SessionLocal()
    try:
        email_obj = EmailORM(
            student_name=email_in.student_name,
            subject=email_in.subject,
            body=email_in.body,
            confidence=confidence,
            status=status,
            suggested_reply=suggested_reply,
            received_at=received_at,
        )
        db.add(email_obj)
        db.commit()
        db.refresh(email_obj)
        return orm_to_schema(email_obj)
    finally:
        db.close()


# =====================================================
# Endpoint: list emails
# =====================================================


@app.get("/emails", response_model=List[Email])
def list_emails(
    status: Optional[EmailStatus] = Query(
        default=None,
        description="Filter by 'auto' or 'review'. Leave empty for all.",
    )
):
    """
    Returns a list of stored emails for the dashboard.
    /emails               → all
    /emails?status=auto   → only auto
    /emails?status=review → only review
    """
    db = SessionLocal()
    try:
        query = db.query(EmailORM)
        if status is not None:
            query = query.filter(EmailORM.status == status)
        query = query.order_by(EmailORM.received_at.desc())
        emails = query.all()
        return [orm_to_schema(e) for e in emails]
    finally:
        db.close()


# =====================================================
# Endpoint: update email (advisor actions)
# =====================================================


@app.patch("/emails/{email_id}", response_model=Email)
def update_email(email_id: int, update: EmailUpdate):
    """
    Update an email (e.g., change status from 'review' to 'auto',
    and/or edit the suggested_reply text).
    """
    db = SessionLocal()
    try:
        email_obj = db.query(EmailORM).filter(EmailORM.id == email_id).first()
        if email_obj is None:
            raise HTTPException(status_code=404, detail="Email not found")

        data = update.dict(exclude_unset=True)
        for field, value in data.items():
            setattr(email_obj, field, value)

        db.commit()
        db.refresh(email_obj)
        return orm_to_schema(email_obj)
    finally:
        db.close()


# =====================================================
# Endpoint: delete email
# =====================================================


@app.delete("/emails/{email_id}")
def delete_email(email_id: int):
    """
    Delete an email from the database.
    """
    db = SessionLocal()
    try:
        email_obj = db.query(EmailORM).filter(EmailORM.id == email_id).first()
        if email_obj is None:
            raise HTTPException(status_code=404, detail="Email not found")

        db.delete(email_obj)
        db.commit()
        return {"ok": True}
    finally:
        db.close()


# =====================================================
# Endpoint: respond (playground / dev tool)
# =====================================================


@app.get("/respond")
def respond(
    query: str = Query(..., description="Student's email query"),
    student_name: Optional[str] = None,
):
    """
    Process a student query using the EmailAdvisor backend.
    Returns subject, body, and confidence.

    This is like a playground / test endpoint for manually trying prompts.
    """
    result = advisor.process_query(query, {"student_name": student_name})
    return {
        "subject": result.subject,
        "body": result.body,
        "confidence": result.confidence,
    }

# =====================================================
# Endpoint: metrics (REAL data from DB)
# =====================================================

@app.get("/metrics")
def metrics():
    """
    Returns real dashboard statistics computed from the database.
    """
    db = SessionLocal()
    try:
        # Total emails
        total = db.query(func.count(EmailORM.id)).scalar() or 0

        # Emails received today (UTC)
        today = datetime.utcnow().date()
        start_of_today = datetime(today.year, today.month, today.day)

        emails_today = (
            db.query(func.count(EmailORM.id))
            .filter(EmailORM.received_at >= start_of_today)
            .scalar()
            or 0
        )

        # Counts by status
        auto_count = (
            db.query(func.count(EmailORM.id))
            .filter(EmailORM.status == EmailStatus.auto)
            .scalar()
            or 0
        )
        review_count = (
            db.query(func.count(EmailORM.id))
            .filter(EmailORM.status == EmailStatus.review)
            .scalar()
            or 0
        )

        # Average confidence for ALL emails
        avg_conf = db.query(func.avg(EmailORM.confidence)).scalar()
        if avg_conf is None:
            avg_conf = 0.0

        # Average confidence for approved (auto) emails only
        avg_auto_conf = (
            db.query(func.avg(EmailORM.confidence))
            .filter(EmailORM.status == EmailStatus.auto)
            .scalar()
        )
        if avg_auto_conf is None:
            avg_auto_conf = 0.0

        return {
            "emails_total": int(total),
            "emails_today": int(emails_today),
            "auto_count": int(auto_count),
            "review_count": int(review_count),
            "avg_confidence": float(avg_conf),          # NEW: all emails
            "avg_auto_confidence": float(avg_auto_conf) # kept for other views if needed
        }
    finally:
        db.close()