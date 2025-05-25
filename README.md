# AI Notes Generator API

A FastAPI backend for generating detailed notes using Together AI's DeepSeek-V3 model.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your Together AI API key:
   - Sign up at [Together AI](https://together.ai)
   - Set your API key as an environment variable:
```bash
export TOGETHER_API_KEY=your_api_key_here
```

## Running the API

Start the server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- API docs: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`

## Endpoints

### POST /generate-notes

Generate detailed notes from provided text.

Example request:
```json
{
    "text": "Your transcript or text here"
}
```

Example response:
```json
{
    "notes": "Generated detailed notes..."
}
```

### GET /

Health check endpoint that returns a welcome message. 