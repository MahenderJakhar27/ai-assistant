from fastapi import FastAPI
import requests
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.responses import HTMLResponse
app = FastAPI()
templates = Jinja2Templates(directory="templates")
OLLAMA_URL = "http://localhost:11434/api/generate"

# 🔹 AI Function
def ask_ai(prompt):
    response = requests.post(OLLAMA_URL, json={
        "model": "llama3",
        "prompt": prompt,
        "stream": False
    })
    return response.json()["response"]


@app.get("/")
def home():
    return {"message": "AI Assistant Running"}


# 🔹 Task Storage
tasks = []

# 🔹 Task Handler
def handle_task(user_input):
    text = user_input.lower()

    # ✅ Add Task (more flexible)
    if "add task" in text or "add a task" in text:
        task = text.replace("add task", "").replace("add a task", "").strip()
        tasks.append(task)
        return f"✅ Task added: {task}"

    # ✅ Show Tasks (more flexible)
    elif "show tasks" in text or "show all tasks" in text:
        if not tasks:
            return "No tasks found"
        return "\n".join([f"{i+1}. {t}" for i, t in enumerate(tasks)])

    return None

@app.post("/chat/")
def chat(user_input: str):

    intent_data = get_intent(user_input)

    intent = intent_data.get("intent")

    # ✅ ADD TASK
    if intent == "add_task":
        task = intent_data.get("task", user_input)
        tasks.append(task)
        return {"response": f"✅ Task added: {task}"}

    # ✅ SHOW TASKS
    elif intent == "show_tasks":
        if not tasks:
            return {"response": "No tasks found"}
        return {"response": "\n".join([f"{i+1}. {t}" for i, t in enumerate(tasks)])}

    # ✅ FALLBACK TO CHAT
    reply = ask_ai(user_input)
    return {"response": reply}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

import json

def get_intent(user_input):
    prompt = f"""
    You are an AI assistant.

    Extract intent and data from the user message.

    Respond ONLY in JSON format like:
    {{
        "intent": "add_task",
        "task": "fix bug"
    }}

    OR

    {{
        "intent": "show_tasks"
    }}

    User message: {user_input}
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