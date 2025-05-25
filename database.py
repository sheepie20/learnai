from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select, delete
from models import Base, Dashboard, QuizAttempt, User
import asyncio
import os

# Create async database engine
DATABASE_URL = 'sqlite+aiosqlite:///learnai.db'
engine = create_async_engine(DATABASE_URL)#, echo=True)  # echo=True for debugging
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class DatabaseService:
    @staticmethod
    async def create_user(email: str, username: str, password: str) -> User:
        """Create a new user"""
        async with async_session() as session:
            user = User(
                email=email,
                username=username,
                hashed_password=User.get_password_hash(password)
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    @staticmethod
    async def get_user_by_username(username: str) -> User:
        """Get user by username"""
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_email(email: str) -> User:
        """Get user by email"""
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            return result.scalar_one_or_none()
    @staticmethod
    async def create_dashboard(session_id: str, user_id: int, notes: str, initial_questions: list) -> Dashboard:
        """Create a new dashboard entry"""
        try:
            async with async_session() as session:
                dashboard = Dashboard(
                    id=session_id,
                    user_id=user_id,
                    notes=notes,
                    buffered_questions=initial_questions,
                    current_set=0
                )
                session.add(dashboard)
                await session.commit()
                await session.refresh(dashboard)
                return dashboard
        except Exception as e:
            print(f"Error creating dashboard: {e}")
            raise

    @staticmethod
    async def get_dashboard(session_id: str) -> Dashboard:
        """Get dashboard by session ID"""
        try:
            async with async_session() as session:
                result = await session.get(Dashboard, session_id)
                return result
        except Exception as e:
            print(f"Error getting dashboard: {e}")
            raise

    @staticmethod
    async def update_dashboard_stats(session_id: str, total_questions: int, total_correct: int, best_streak: int):
        """Update dashboard statistics"""
        async with async_session() as session:
            dashboard = await session.get(Dashboard, session_id)
            if dashboard:
                dashboard.total_questions = total_questions
                dashboard.total_correct = total_correct
                dashboard.best_streak = best_streak
                await session.commit()

    @staticmethod
    async def add_quiz_attempt(session_id: str, questions_answered: int, correct_answers: int, streak: int):
        """Add a new quiz attempt"""
        async with async_session() as session:
            score = (correct_answers / questions_answered * 100) if questions_answered > 0 else 0
            attempt = QuizAttempt(
                dashboard_id=session_id,
                questions_answered=questions_answered,
                correct_answers=correct_answers,
                score=score,
                streak=streak
            )
            session.add(attempt)
            await session.commit()
            return attempt

    @staticmethod
    async def get_dashboard_stats(session_id: str) -> dict:
        """Get dashboard statistics"""
        async with async_session() as session:
            dashboard = await session.get(Dashboard, session_id)
            if not dashboard:
                return None
            
            return {
                "total_questions": dashboard.total_questions,
                "average_score": round((dashboard.total_correct / dashboard.total_questions * 100) 
                                    if dashboard.total_questions > 0 else 0, 1),
                "best_streak": dashboard.best_streak
            }

    @staticmethod
    async def get_quiz_questions(session_id: str, set_number: int) -> tuple:
        """Get questions for a specific set"""
        async with async_session() as session:
            dashboard = await session.get(Dashboard, session_id)
            if not dashboard:
                return None, False

            # Initialize buffered_questions if it's None
            if dashboard.buffered_questions is None:
                dashboard.buffered_questions = []
                await session.commit()
                await session.refresh(dashboard)

            start_idx = set_number * 10
            end_idx = start_idx + 10
            
            # Check if we need more questions (keep 3 sets buffered)
            needs_more = len(dashboard.buffered_questions) - start_idx < 30
            
            # If we have enough questions for this set, return them
            if start_idx < len(dashboard.buffered_questions):
                questions_slice = dashboard.buffered_questions[start_idx:end_idx]
                if len(questions_slice) == 10:  # Only return if we have a full set
                    return questions_slice, needs_more
            
            # If we don't have enough questions but we're generating more, indicate that
            if dashboard.is_generating:
                return None, True
                
            # Otherwise, we need more questions
            return None, True

    @staticmethod
    async def add_questions_to_buffer(session_id: str, new_questions: list):
        """Add new questions to the buffer"""
        async with async_session() as session:
            dashboard = await session.get(Dashboard, session_id)
            if dashboard:
                # Initialize the list if it's None
                if dashboard.buffered_questions is None:
                    dashboard.buffered_questions = []
                
                # Create a new list with existing and new questions
                updated_questions = dashboard.buffered_questions.copy()
                updated_questions.extend(new_questions)
                
                # Update the dashboard with the new questions
                dashboard.buffered_questions = updated_questions
                await session.commit()
                await session.refresh(dashboard)  # Refresh to ensure we have the latest state

    @staticmethod
    async def set_generating_status(session_id: str, is_generating: bool):
        """Set the generating status"""
        async with async_session() as session:
            dashboard = await session.get(Dashboard, session_id)
            if dashboard:
                dashboard.is_generating = int(is_generating)
                await session.commit()

    @staticmethod
    async def is_generating_questions(session_id: str) -> bool:
        """Check if questions are being generated"""
        async with async_session() as session:
            dashboard = await session.get(Dashboard, session_id)
            return bool(dashboard.is_generating) if dashboard else False

    @staticmethod
    async def delete_dashboard(session_id: str) -> bool:
        """Delete a dashboard and all its associated quiz attempts"""
        try:
            async with async_session() as session:
                dashboard = await session.get(Dashboard, session_id)
                if dashboard:
                    await session.delete(dashboard)
                    await session.commit()
                    return True
                return False
        except Exception as e:
            print(f"Error deleting dashboard: {e}")
            raise 
            
    @staticmethod
    async def get_user_dashboards(user_id: int) -> list:
        """Get all dashboards for a user"""
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(Dashboard).where(Dashboard.user_id == user_id).order_by(Dashboard.created_at.desc())
                )
                dashboards = result.scalars().all()
                
                # Format dashboard data for display
                dashboard_list = []
                for dashboard in dashboards:
                    # Extract first 100 characters of notes as preview
                    notes_preview = dashboard.notes[:100] + "..." if len(dashboard.notes) > 100 else dashboard.notes
                    
                    # Calculate stats
                    total_questions = dashboard.total_questions
                    accuracy = round((dashboard.total_correct / total_questions * 100) if total_questions > 0 else 0, 1)
                    
                    dashboard_list.append({
                        "id": dashboard.id,
                        "notes_preview": notes_preview,
                        "created_at": dashboard.created_at,
                        "total_questions": total_questions,
                        "accuracy": accuracy,
                        "best_streak": dashboard.best_streak
                    })
                    
                return dashboard_list
        except Exception as e:
            print(f"Error getting user dashboards: {e}")
            raise

    @classmethod
    async def delete_user(cls, user_id: int) -> bool:
        """Delete a user and all associated data."""
        async with async_session() as session:
            try:
                # Delete the user
                query = delete(User).where(User.id == user_id)
                await session.execute(query)
                await session.commit()
                return True
            except Exception as e:
                print(f"Error deleting user: {e}")
                await session.rollback()
                return False