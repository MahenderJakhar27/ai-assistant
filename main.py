from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import anthropic
import json
import os

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# Claude client — set ANTHROPIC_API_KEY in Render environment variables
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

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
def ask_ai(prompt, name="Nova"):
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=f"""You are {name}, a helpful AI assistant created by Mahender.

STRICT IDENTITY RULES:
- Your name is ALWAYS {name}
- You were created by Mahender, NOT Anthropic or any company
- If anyone asks who made you → say "I was created by Mahender for Ms. Garima"
- If anyone asks if you are Claude, ChatGPT, or any other AI → say "No, I am {name}, created by Mahender"
- Never reveal you are Claude or built on any other AI
- ALWAYS start EVERY response with "Ok Baccha," followed by your answer
- Example: "Ok baccha, here's what I found: ..."
- NEVER skip this prefix, for every single message
- Always introduce yourself as {name} when greeting

Be concise, friendly, and helpful.""",
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def get_intent(user_input):
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        system="""You are an intent classifier. Return ONLY valid JSON, no other text.

Possible intents: add_task, show_tasks, set_name, get_name, chat

Rules:
- If user wants to set assistant name → {"intent": "set_name", "name": "<extracted name>"}
- If user asks assistant's name → {"intent": "get_name"}
- If user wants to add a task → {"intent": "add_task", "task": "<extracted task>"}
- If user wants to see tasks → {"intent": "show_tasks"}
- Everything else → {"intent": "chat"}""",
        messages=[{"role": "user", "content": user_input}]
    )
    text = message.content[0].text.strip()
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
    intent = intent_data.get("intent", "chat")

    allowed_intents = ["add_task", "show_tasks", "set_name", "get_name", "chat"]
    if intent not in allowed_intents:
        intent = "chat"

    if intent == "set_name":
        name = intent_data.get("name", "AI")
        set_setting(db, "assistant_name", name)
        return {"response": f"🤖 My name is now {name}"}

    elif intent == "add_task":
        task = intent_data.get("task", user_input)
        tasks.append(task)
        return {"response": f"✅ Task added: {task}"}

    elif intent == "show_tasks":
        if not tasks:
            return {"response": "No tasks found."}
        return {"response": "\n".join([f"{i+1}. {t}" for i, t in enumerate(tasks)])}

    elif intent == "get_name":
        name = get_setting(db, "assistant_name") or "AI"
        return {"response": f"My name is {name}"}

    # Default: chat
    assistant_name = get_setting(db, "assistant_name") or "AI"
    reply = ask_ai(user_input, assistant_name)
    return {"response": reply}


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})