# AI-Powered Learning Assistant

A web application that helps users learn by generating detailed notes and interactive quizzes from text or YouTube videos using AI. Now includes an AI-powered study chatbot with persistent conversation history and LaTeX/Markdown support.

## Features

- **Note Generation**: Generate comprehensive notes from text input or YouTube video transcripts
- **Interactive Quizzes**: Automatically create multiple-choice quizzes from generated notes
- **AI Study Chatbot**: Ask questions about your notes with a context-aware AI assistant. Supports Markdown and LaTeX formatting, and saves your chat history per session.
- **User Authentication**: Secure user registration and login system (JWT-based)
- **Dashboard**: Track your learning progress, review past notes, quizzes, and chat sessions
- **Delete Chat**: Easily clear your chat history for any session
- **Responsive Design**: Works on both desktop and mobile devices

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, CSS, JavaScript (with Jinja2 templating)
- **Database**: SQLite (via SQLAlchemy, aiosqlite)
- **AI/ML**: Together AI (DeepSeek-V3 model)
- **Authentication**: JWT (JSON Web Tokens)
- **Video Processing**: YouTubeTranscriptAPI (for YouTube transcription)
- **Math/Markdown**: MathJax for LaTeX, marked.js for Markdown, highlight.js for code

## Prerequisites

- Python 3.8+
- Together AI API key

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd learnai/revamp
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file in the project root and add your Together AI API key and other secrets:
   ```
   TOGETHER_API_KEY=your_api_key_here
   SECRET_KEY=your_secret_key_here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=43200  # 30 days
   MAIL_USERNAME=your_email@example.com
   MAIL_PASSWORD=your_email_password
   MAIL_FROM=your_email@example.com
   MAIL_PORT=587
   MAIL_SERVER=smtp.example.com
   MAIL_STARTTLS=True
   MAIL_SSL_TLS=False
   ```

5. Initialize the database:
   ```bash
   python -c "from database import engine; import asyncio; from models import init_db; asyncio.run(init_db(engine))"
   ```

## Running the Application

Start the development server:
```bash
uvicorn main:app --reload
```

The application will be available at `http://localhost:8000`

## API Endpoints

- `POST /generate-notes`: Generate notes from text or YouTube URL
- `POST /generate-quiz`: Generate a quiz from notes
- `GET /quiz/{quiz_id}`: View a specific quiz
- `POST /register`: Register a new user
- `POST /token`: Authenticate and get access token
- `GET /dashboards`: View user's learning dashboards
- `GET /chat/{quiz_id}`: Access the AI study chatbot for a quiz/session
- `POST /api/chat/{quiz_id}`: Interact with the AI chatbot (persistent, context-aware)

## Project Structure

- `main.py`: Main FastAPI application and route handlers
- `ai_service.py`: Core AI functionality for note taking, quiz generation, and chat
- `auth.py`: Authentication and user management
- `database.py`: Database connection and session management
- `models.py`: SQLAlchemy models
- `youtube.py`: YouTube video processing utilities
- `templates/`: HTML templates (dashboard, quiz, chat, etc.)
- `static/`: Static files (CSS, JavaScript, images)

## Environment Variables

- `TOGETHER_API_KEY`: Your Together AI API key (required)
- `SECRET_KEY`: Secret key for JWT token signing (required)
- `ALGORITHM`: Algorithm for JWT (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time (default: 43200 for 30 days)
- `MAIL_*`: Email settings for password reset (see example above)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Acknowledgments

- Together AI for the powerful language models
- FastAPI for the awesome web framework
- The open-source community for various libraries and tools used in this project
- MathJax, marked.js, and highlight.js for rich chat and note formatting
