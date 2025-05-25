# AI-Powered Learning Assistant

A web application that helps users learn by generating detailed notes and interactive quizzes from text or YouTube videos using AI.

## Features

- **Note Generation**: Generate comprehensive notes from text input or YouTube video transcripts
- **Interactive Quizzes**: Automatically create multiple-choice quizzes from generated notes
- **User Authentication**: Secure user registration and login system
- **Dashboard**: Track your learning progress and review past notes and quizzes
- **Responsive Design**: Works on both desktop and mobile devices

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, CSS, JavaScript (with Jinja2 templating)
- **Database**: SQLite (via SQLAlchemy)
- **AI/ML**: Together AI (DeepSeek-V3 model)
- **Authentication**: JWT (JSON Web Tokens)
- **Video Processing**: yt-dlp, OpenAI Whisper (for YouTube transcription)

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
   Create a `.env` file in the project root and add your Together AI API key:
   ```
   TOGETHER_API_KEY=your_api_key_here
   SECRET_KEY=your_secret_key_here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
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
- `POST /login`: Authenticate and get access token
- `GET /dashboards`: View user's learning dashboards

## Project Structure

- `main.py`: Main FastAPI application and route handlers
- `ai_service.py`: Core AI functionality for note taking and quiz generation
- `auth.py`: Authentication and user management
- `database.py`: Database connection and session management
- `models.py`: SQLAlchemy models
- `youtube.py`: YouTube video processing utilities
- `templates/`: HTML templates
- `static/`: Static files (CSS, JavaScript, images)

## Environment Variables

- `TOGETHER_API_KEY`: Your Together AI API key (required)
- `SECRET_KEY`: Secret key for JWT token signing (required)
- `ALGORITHM`: Algorithm for JWT (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time (default: 30)

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
