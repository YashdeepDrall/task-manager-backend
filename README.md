# Backend

FastAPI backend for the Project & Task Management System.

## Setup

```bash
py -3.11 -m venv ..\.venv
..\.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

## Environment

Create `backend/.env` locally with:

```env
MONGO_URI=your-mongodb-atlas-connection-string
DB_NAME=TaskManager
SECRET_KEY=your-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

Do not commit `.env`.

## Docs

```text
http://localhost:8000/docs
```
