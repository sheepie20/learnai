from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends, status, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from ai_service import NoteTaker, TranscriptionService, QuizGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
import secrets
from fastapi.responses import RedirectResponse

import uuid
from models import init_db, User
from database import DatabaseService, engine, async_session
from auth import (
    Token, UserCreate, hash_password, verify_password, create_access_token,
    get_current_active_user, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY, ALGORITHM, REFRESH_TOKEN_EXPIRE_DAYS
)
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import os

# Update token expiration time to 30 days
ACCESS_TOKEN_EXPIRE_MINUTES = 43200  # 30 days * 24 hours * 60 minutes

# Initialize database
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(lambda bind: init_db(bind=bind))
    yield

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Notes Generator API",
    description="API for generating detailed notes from text or YouTube videos using Together AI",
    version="1.0.0",
    lifespan=lifespan
)

# Allow all CORS for debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize services
note_taker = NoteTaker()
transcription_service = TranscriptionService()
quiz_generator = QuizGenerator()

# In-memory store for password reset tokens (for demo; use DB/Redis in prod)
reset_tokens = {}

conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD"),
    MAIL_FROM = os.getenv("MAIL_FROM"),
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER = os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS = os.getenv("MAIL_STARTTLS", "True") == "True",
    MAIL_SSL_TLS = os.getenv("MAIL_SSL_TLS", "False") == "True",
    USE_CREDENTIALS = True
)

async def generate_more_questions(session_id: str, notes: str):
    """Background task to generate more questions"""
    if await DatabaseService.is_generating_questions(session_id):
        print(f"Already generating questions for session {session_id}")
        return
        
    try:
        await DatabaseService.set_generating_status(session_id, True)
        print(f"Generating more questions for session {session_id}")
        
        # Generate 3 sets of questions at once
        for _ in range(3):
            try:
                response = await quiz_generator.generate_quiz(notes)
                new_questions = response.get("questions", [])
                if new_questions:
                    await DatabaseService.add_questions_to_buffer(session_id, new_questions)
                    print(f"Added {len(new_questions)} questions to buffer for session {session_id}")
            except Exception as e:
                print(f"Error generating quiz set: {e}")
                # Continue generating remaining sets even if one fails
                continue
                
    except Exception as e:
        print(f"Error in generate_more_questions: {e}")
    finally:
        await DatabaseService.set_generating_status(session_id, False)
        print(f"Finished generating questions for session {session_id}")

class NotesRequest(BaseModel):
    text: Optional[str] = Field(None, min_length=1, description="The text to generate notes from")
    youtube_url: Optional[str] = Field(None, description="YouTube URL to transcribe and generate notes from")

    @field_validator('youtube_url')
    @classmethod
    def validate_youtube_url(cls, v: Optional[str], info) -> Optional[str]:
        if v is None and info.data.get('text') is None:
            raise ValueError("Either text or youtube_url must be provided")
        return v

    @field_validator('text')
    @classmethod
    def validate_text(cls, v: Optional[str], info) -> Optional[str]:
        if v is None and info.data.get('youtube_url') is None:
            raise ValueError("Either text or youtube_url must be provided")
        return v

class NotesResponse(BaseModel):
    transcription: Optional[str] = Field(None, description="The transcribed text (if YouTube URL was provided)")
    cleaned_text: str = Field(..., description="The cleaned and preprocessed text")
    notes: str = Field(..., description="The generated notes")

class QuizRequest(BaseModel):
    notes: str = Field(..., min_length=1, description="The notes to generate quiz questions from")

class QuizQuestion(BaseModel):
    question_text: str
    options: Dict[str, str]  # A, B, C, D as keys
    correct_answer: str      # A, B, C, or D

class QuizResponse(BaseModel):
    quiz_id: str
    questions: List[QuizQuestion]
    set_number: int = 0

@app.post("/generate-notes", response_model=NotesResponse)
async def generate_notes(
    request: NotesRequest,
    current_user: User = Depends(get_current_active_user)
):
    try:
        transcribed_text = None

        # Step 1: Get or transcribe the text content
        if request.text and not request.youtube_url:
            # Direct text input
            raw_text = request.text
        elif request.youtube_url:
            # YouTube URL
            try:
                transcribed_text = await transcription_service.transcribe(request.youtube_url)
                if not transcribed_text:
                    raise HTTPException(
                        status_code=400,
                        detail="Failed to transcribe the YouTube video. Please check the URL and try again."
                    )
                raw_text = transcribed_text
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to process YouTube URL: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Please provide either text or a YouTube URL"
            )

        cleaned_text = note_taker._preprocess_text(raw_text)
        if not cleaned_text.strip():
            raise HTTPException(
                status_code=400,
                detail="The processed text is empty. Please provide valid input."
            )

        # Step 3: Generate notes from the cleaned text
        notes = await note_taker.generate_notes(cleaned_text)
        print(f"Generated notes length: {len(notes)}")  # Debug print

        # Return all the information
        return NotesResponse(
            transcription=transcribed_text,
            cleaned_text=cleaned_text,
            notes=notes
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.get("/quiz/{quiz_id}")
async def show_quiz(request: Request, quiz_id: str):
    # Check if quiz exists
    dashboard = await DatabaseService.get_dashboard(quiz_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    return templates.TemplateResponse(
        "quiz.html", 
        {"request": request, "quiz_id": quiz_id}
    )

@app.get("/api/quiz/{quiz_id}")
async def get_quiz_data(background_tasks: BackgroundTasks, quiz_id: str, set_number: int = 0):
    dashboard = await DatabaseService.get_dashboard(quiz_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    questions, needs_more = await DatabaseService.get_quiz_questions(quiz_id, set_number)
    
    # If we need more questions and we're not already generating them
    if needs_more and not await DatabaseService.is_generating_questions(quiz_id):
        background_tasks.add_task(generate_more_questions, quiz_id, dashboard.notes)
    
    # If we don't have questions for this set yet
    if questions is None:
        raise HTTPException(
            status_code=202,  # 202 Accepted indicates the request was accepted but not completed
            detail="Questions are being generated. Please try again in a moment."
        )
    
    # Return the questions we have
    return {
        "questions": questions,
        "set_number": set_number,
        "has_next": True  # Always true since we're making it infinite
    }

@app.post("/generate-quiz", response_model=QuizResponse)
async def generate_quiz(
    request: QuizRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user)
):
    try:
        print(f"Generating quiz from notes: {request.notes[:100]}...")  # Print first 100 chars for debugging
        
        if not request.notes or not request.notes.strip():
            raise HTTPException(status_code=400, detail="Notes cannot be empty")
            
        # Initialize first set of questions
        try:
            response = await quiz_generator.generate_quiz(request.notes)
            questions = response.get("questions", [])
            
            if not questions:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate quiz questions. Please try again."
                )
        except Exception as e:
            print(f"Error generating quiz: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate quiz questions. Please try again."
            )
        
        # Create new quiz session
        session_id = str(uuid.uuid4())
        
        # Store in database with initial questions
        try:
            await DatabaseService.create_dashboard(session_id, current_user.id, request.notes, questions)
        except Exception as e:
            print(f"Error creating dashboard: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to save quiz data. Please try again."
            )
        
        # Start generating next set in the background
        background_tasks.add_task(generate_more_questions, session_id, request.notes)
        
        return {
            "quiz_id": session_id,
            "questions": questions,
            "set_number": 0
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in generate_quiz: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again."
        )

@app.post("/register")
async def register(user_data: UserCreate):
    existing_user = await DatabaseService.get_user_by_username(user_data.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    # Use the User model's password hashing method to be consistent with existing users
    user = await DatabaseService.create_user(user_data.email, user_data.username, user_data.password)
    # Automatically log in the user after registration
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
        token_type="access"
    )
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_access_token(
        data={"sub": user.username},
        expires_delta=refresh_token_expires,
        token_type="refresh"
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await DatabaseService.get_user_by_username(form_data.username)
    if not user or not User.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, 
        expires_delta=access_token_expires,
        token_type="access"
    )
    
    # Create refresh token (optional)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_access_token(
        data={"sub": user.username}, 
        expires_delta=refresh_token_expires,
        token_type="refresh"
    )
    
    # Return complete token response
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

# Since we're using the simpler auth model without refresh tokens,
# we'll comment out this endpoint for now
# @app.post("/refresh", response_model=Token)
# async def refresh_token(request: Request):
#     auth_header = request.headers.get("Authorization")
#     if not auth_header or not auth_header.startswith("Bearer "):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Missing refresh token",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     
#     refresh_token = auth_header.split(" ")[1]
#     try:
#         # This would need to be reimplemented with the new auth system
#         # if refresh tokens are needed
#         pass
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=str(e),
#             headers={"WWW-Authenticate": "Bearer"},
#         )

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/")
async def root(request: Request):
    # Check if user is logged in via Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return templates.TemplateResponse("index.html", {"request": request, "authenticated": False})
    
    # Try to validate the token
    try:
        token = auth_header.split(" ")[1]
        # Use jwt.decode directly for simple validation without DB lookup
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # If we get here, token is valid
        return templates.TemplateResponse("index.html", {"request": request, "authenticated": True})
    except JWTError:
        # Instead of raising an error, log the user out and redirect to login
        return templates.TemplateResponse(
            "logout.html",
            {"request": request}
        )

@app.get("/dashboards")
async def show_dashboards(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    # Get all dashboards for the current user
    dashboards = await DatabaseService.get_user_dashboards(current_user.id)
    
    return templates.TemplateResponse(
        "dashboards.html",
        {
            "request": request,
            "username": current_user.username,
            "dashboards": dashboards
        }
    )

@app.post("/dashboards")
async def post_dashboards(
    request: Request,
    token: str = Form(...)  # Get token from form data
):
    # Manually validate the token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return templates.TemplateResponse(
                "logout.html",
                {"request": request}
            )
            
        # Get the user from database
        user = await DatabaseService.get_user_by_username(username)
        if not user:
            return templates.TemplateResponse(
                "logout.html",
                {"request": request}
            )
            
        # Get all dashboards for the user
        dashboards = await DatabaseService.get_user_dashboards(user.id)
        
        # Return the dashboards template
        return templates.TemplateResponse(
            "dashboards.html",
            {
                "request": request,
                "username": user.username,
                "dashboards": dashboards
            }
        )
    except JWTError:
        # Instead of raising an error, log the user out and redirect to login
        return templates.TemplateResponse(
            "logout.html",
            {"request": request}
        )

@app.get("/dashboard/{session_id}")
async def show_dashboard(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    dashboard = await DatabaseService.get_dashboard(session_id)
    if not dashboard:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "session_id": session_id,
            "notes": dashboard.notes
        }
    )

# Add a POST endpoint for the dashboard to accept token in the request body
@app.post("/dashboard/{session_id}")
async def post_dashboard(
    request: Request,
    session_id: str,
    token: str = Form(...)  # Get token from form data
):
    # Manually validate the token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return templates.TemplateResponse(
                "logout.html",
                {"request": request}
            )
            
        # Get the user from database
        user = await DatabaseService.get_user_by_username(username)
        if not user:
            return templates.TemplateResponse(
                "logout.html",
                {"request": request}
            )
            
        # Get the dashboard
        dashboard = await DatabaseService.get_dashboard(session_id)
        if not dashboard:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Return the dashboard template
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "session_id": session_id,
                "notes": dashboard.notes
            }
        )
    except JWTError:
        # Instead of raising an error, log the user out and redirect to login
        return templates.TemplateResponse(
            "logout.html",
            {"request": request}
        )

@app.get("/api/quiz-stats/{session_id}")
async def get_quiz_stats(session_id: str):
    stats = await DatabaseService.get_dashboard_stats(session_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Session not found")
    return stats

@app.post("/submit-quiz-results/{session_id}")
async def submit_quiz_results(session_id: str, results: dict):
    try:
        # Add the quiz attempt
        await DatabaseService.add_quiz_attempt(
            session_id=session_id,
            questions_answered=results["total_questions"],
            correct_answers=results["correct_answers"],
            streak=results.get("streak", 0)
        )
        
        # Update overall dashboard stats
        dashboard = await DatabaseService.get_dashboard(session_id)
        if dashboard:
            new_total = dashboard.total_questions + results["total_questions"]
            new_correct = dashboard.total_correct + results["correct_answers"]
            new_streak = max(dashboard.best_streak, results.get("streak", 0))
            
            await DatabaseService.update_dashboard_stats(
                session_id=session_id,
                total_questions=new_total,
                total_correct=new_correct,
                best_streak=new_streak
            )
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit results: {str(e)}")

@app.delete("/api/dashboard/{session_id}")
async def delete_dashboard(session_id: str):
    try:
        success = await DatabaseService.delete_dashboard(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return {"success": True, "message": "Dashboard deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete dashboard")

@app.get("/profile")
async def profile_page(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    # Get user's dashboards
    dashboards = await DatabaseService.get_user_dashboards(current_user.id)
    
    # Calculate statistics
    total_dashboards = len(dashboards)
    total_quizzes = sum(1 for d in dashboards if d.total_questions > 0)
    
    # Calculate average score
    total_correct = sum(d.total_correct for d in dashboards)
    total_questions = sum(d.total_questions for d in dashboards)
    avg_score = round((total_correct / total_questions * 100) if total_questions > 0 else 0, 1)
    
    # Get best streak across all dashboards
    best_streak = max((d.best_streak for d in dashboards), default=0)
    
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "username": current_user.username,
            "email": current_user.email,
            "joined_date": current_user.created_at,
            "total_dashboards": total_dashboards,
            "total_quizzes": total_quizzes,
            "avg_score": avg_score,
            "best_streak": best_streak
        }
    )

@app.post("/profile")
async def post_profile(
    request: Request,
    token: str = Form(...)  # Get token from form data
):
    # Manually validate the token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return templates.TemplateResponse(
                "logout.html",
                {"request": request}
            )
            
        # Get the user from database
        user = await DatabaseService.get_user_by_username(username)
        if not user:
            return templates.TemplateResponse(
                "logout.html",
                {"request": request}
            )
            
        # Get user's dashboards
        dashboards = await DatabaseService.get_user_dashboards(user.id)
        
        # Calculate statistics
        total_dashboards = len(dashboards)
        total_quizzes = sum(1 for d in dashboards if d.get('total_questions', 0) > 0)
        
        # Calculate average score
        total_correct = sum(d.get('total_correct', 0) for d in dashboards)
        total_questions = sum(d.get('total_questions', 0) for d in dashboards)
        avg_score = round((total_correct / total_questions * 100) if total_questions > 0 else 0, 1)
        
        # Get best streak across all dashboards
        best_streak = max((d.get('best_streak', 0) for d in dashboards), default=0)
        
        # Return the profile template
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "username": user.username,
                "email": user.email,
                "joined_date": user.created_at,
                "total_dashboards": total_dashboards,
                "total_quizzes": total_quizzes,
                "avg_score": avg_score,
                "best_streak": best_streak
            }
        )
    except JWTError:
        # Instead of raising an error, log the user out and redirect to login
        return templates.TemplateResponse(
            "logout.html",
            {"request": request}
        )

@app.delete("/api/user/delete")
async def delete_user(current_user: User = Depends(get_current_active_user)):
    try:
        # Get all user's dashboards
        dashboards = await DatabaseService.get_user_dashboards(current_user.id)
        
        # Delete all dashboards
        for dashboard in dashboards:
            await DatabaseService.delete_dashboard(dashboard['id'])
        
        # Delete the user
        await DatabaseService.delete_user(current_user.id)
        
        return {"message": "User account deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete account: {str(e)}"
        )

@app.post("/quiz/{quiz_id}")
async def post_quiz(
    request: Request,
    quiz_id: str,
    token: str = Form(...)  # Get token from form data
):
    # Manually validate the token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return templates.TemplateResponse(
                "logout.html",
                {"request": request}
            )
            
        # Get the user from database
        user = await DatabaseService.get_user_by_username(username)
        if not user:
            return templates.TemplateResponse(
                "logout.html",
                {"request": request}
            )
            
        # Check if quiz exists
        dashboard = await DatabaseService.get_dashboard(quiz_id)
        if not dashboard:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        return templates.TemplateResponse(
            "quiz.html", 
            {"request": request, "quiz_id": quiz_id}
        )
    except JWTError:
        # Instead of raising an error, log the user out and redirect to login
        return templates.TemplateResponse(
            "logout.html",
            {"request": request}
        )

@app.get("/forgot-password")
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})

@app.post("/forgot-password")
async def forgot_password_submit(request: Request, email: str = Form(...)):
    user = await DatabaseService.get_user_by_email(email)
    if user:
        token = secrets.token_urlsafe(32)
        reset_tokens[token] = user.username
        reset_link = f"http://localhost:8000/reset-password/{token}"
        message = MessageSchema(
            subject="Password Reset Request",
            recipients=[user.email],
            body=f"""
                <div style='font-family: Arial, sans-serif; max-width: 500px; margin: auto; border: 1px solid #eee; border-radius: 8px; padding: 24px; background: #f9f9f9;'>
                    <h2 style='color: #2c3e50;'>Password Reset Request</h2>
                    <p>Hi <strong>{user.username}</strong>,</p>
                    <p>We received a request to reset your password for your LearnAI account.</p>
                    <p style='margin: 24px 0;'>
                        <a href='{reset_link}' style='display: inline-block; padding: 12px 24px; background: #3498db; color: #fff; text-decoration: none; border-radius: 5px; font-weight: bold;'>
                            Reset Password
                        </a>
                    </p>
                    <p>If you did not request this, you can safely ignore this email.</p>
                    <hr style='margin: 24px 0; border: none; border-top: 1px solid #eee;'>
                    <p style='font-size: 12px; color: #888;'>If the button above does not work, copy and paste this link into your browser:<br>{reset_link}</p>
                    <p style='font-size: 12px; color: #888;'>Thank you,<br>The LearnAI Team</p>
                </div>
            """,
            subtype="html"
        )
        fm = FastMail(conf)
        await fm.send_message(message)
    # Always show the same response
    return templates.TemplateResponse("forgot_password_submitted.html", {"request": request})

@app.get("/reset-password/{token}")
async def reset_password_page(request: Request, token: str):
    username = reset_tokens.get(token)
    if not username:
        return templates.TemplateResponse("reset_password_invalid.html", {"request": request})
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})

@app.post("/reset-password/{token}")
async def reset_password_submit(request: Request, token: str, password: str = Form(...)):
    username = reset_tokens.get(token)
    if not username:
        return templates.TemplateResponse("reset_password_invalid.html", {"request": request})
    user = await DatabaseService.get_user_by_username(username)
    if not user:
        return templates.TemplateResponse("reset_password_invalid.html", {"request": request})
    # Update password
    user.hashed_password = User.get_password_hash(password)
    async with async_session() as session:
        session.add(user)
        await session.commit()
    del reset_tokens[token]
    return RedirectResponse("/login", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)