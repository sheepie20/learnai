from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float, JSON, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from passlib.context import CryptContext

Base = declarative_base()

# Password hashing context
# Use bcrypt with specific configuration to avoid version reading errors
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Explicitly set rounds
    bcrypt__ident="2b"  # Use the standard identifier
)

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to dashboards
    dashboards = relationship("Dashboard", back_populates="user", lazy="selectin")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        # Use the module-level pwd_context without importing
        # This avoids circular imports
        return CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12,
            bcrypt__ident="2b"
        ).verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        # Use the same approach as verify_password
        return CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12,
            bcrypt__ident="2b"
        ).hash(password)

class Dashboard(Base):
    __tablename__ = 'dashboards'

    id = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    notes = Column(String)
    buffered_questions = Column(JSON)  # Store questions as JSON
    current_set = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)
    total_correct = Column(Integer, default=0)
    best_streak = Column(Integer, default=0)
    is_generating = Column(Integer, default=0)  # Use as boolean
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="dashboards", lazy="selectin")
    attempts = relationship("QuizAttempt", back_populates="dashboard", lazy="selectin")

class QuizAttempt(Base):
    __tablename__ = 'quiz_attempts'

    id = Column(Integer, primary_key=True)
    dashboard_id = Column(String, ForeignKey('dashboards.id'))
    questions_answered = Column(Integer)
    correct_answers = Column(Integer)
    score = Column(Float)
    streak = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to dashboard
    dashboard = relationship("Dashboard", back_populates="attempts", lazy="selectin")

def init_db(bind=None):
    """Initialize database tables"""
    Base.metadata.create_all(bind=bind) 