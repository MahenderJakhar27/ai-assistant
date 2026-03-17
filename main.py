from fastapi import FastAPI, Request
import requests
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import json

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

app = FastAPI()
templates = Jinja2Templates(directory="templates")

OLLAMA_URL = "http://localhost:11434/api/generate"

# ---------------- DB SETUP ----------------
engine = create_engine("sqlite:///memory.db")
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(String)


Base.metadata.create_all(bind=engine)

# ---------------- HELPERS ----------------
def set_setting(db, key, value):
    setting = db.query(Settings).filter(Settings.key == key).first()

    if setting:
        setting.value = value
    else:
        setting = Settings(key=key, value=value)
        db.add(setting)

    db.commit()


def get_setting(db, key):
    setting = db.query(Settings).filter(Settings.key == key).first()
    return setting.value if setting else None


# ---------------- AI ----------------
def ask_ai(prompt, name="AI"):
    full_prompt = f"You are {name}, a helpful assistant.\nUser: {prompt}"

    response = requests.post(OLLAMA_URL, json={
        "model": "llama3",
        "prompt": full_prompt,
        "stream": False
    })

    return response.json()["response"]


def get_intent(user_input):
    prompt = f"""
    Extract intent from user message.

    Return ONLY JSON.

    Examples:
    {{"intent": "add_task", "task": "fix bug"}}
    {{"intent": "show_tasks"}}
    {{"intent": "set_name", "name": "jarvis"}}

    Message: {user_input}
    """

    response = requests.post(OLLAMA_URL, json={
        "model": "llama3",
        "prompt": prompt,
        "stream": False
    })

    text = response.json()["response"]

    try:
        return json.loads(text)
    except:
        return {"intent": "chat"}


# ---------------- TASK STORAGE ----------------
tasks = []


# ---------------- ROUTES ----------------
@app.get("/")
def home():
    return {"message": "AI Assistant Running"}


@app.post("/chat/")
def chat(user_input: str):
    db = SessionLocal()

    intent_data = get_intent(user_input)
    intent = intent_data.get("intent")

    # ✅ SET NAME
    if intent == "set_name":
        name = intent_data.get("name", "AI")
        set_setting(db, "assistant_name", name)
        return {"response": f"🤖 My name is now {name}"}

    # ✅ ADD TASK
    elif intent == "add_task":
        task = intent_data.get("task", user_input)
        tasks.append(task)
        return {"response": f"✅ Task added: {task}"}

    # ✅ SHOW TASKS
    elif intent == "show_tasks":
        if not tasks:
            return {"response": "No tasks found"}
        return {"response": "\n".join([f"{i+1}. {t}" for i, t in enumerate(tasks)])}

    # ✅ GET NAME
    elif "your name" in user_input.lower():
        name = get_setting(db, "assistant_name") or "AI"
        return {"response": f"My name is {name}"}

    # ✅ AI RESPONSE
    assistant_name = get_setting(db, "assistant_name") or "AI"
    reply = ask_ai(user_input, assistant_name)

    return {"response": reply}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})