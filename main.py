
import importlib

# Load FastAPI dynamically so editor diagnostics do not require the package
# to be installed in the language server's selected Python environment.
fastapi = importlib.import_module("fastapi")
FastAPI = fastapi.FastAPI
CORSMiddleware = importlib.import_module(
    "fastapi.middleware.cors"
).CORSMiddleware
StaticFiles = importlib.import_module(
    "fastapi.staticfiles"
).StaticFiles
from pydantic import BaseModel
import os

# Import your dental agent
from agent import DentalClinicAgent, init_db


app = FastAPI(title="BrightSmile Dental AI API")


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATABASE
# ============================================================

init_db()


# ============================================================
# SESSION-BASED AGENTS
# ============================================================

agents: dict[str, DentalClinicAgent] = {}


def get_agent(session_id: str) -> DentalClinicAgent:
    if session_id not in agents:
        agents[session_id] = DentalClinicAgent(
            session_id=session_id
        )

    return agents[session_id]


# ============================================================
# REQUEST MODELS
# ============================================================

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ResetRequest(BaseModel):
    session_id: str = "default"


# ============================================================
# CHAT API
# ============================================================

@app.post("/api/chat")
def chat(req: ChatRequest):

    message = req.message.strip()

    if not message:
        return {
            "reply": "Please enter a message."
        }

    agent = get_agent(req.session_id)

    reply = agent.chat(message)

    return {
        "reply": reply
    }


# ============================================================
# RESET CHAT
# ============================================================

@app.post("/api/reset")
def reset(req: ResetRequest):

    agent = get_agent(req.session_id)

    agent.reset()

    return {
        "status": "reset",
        "session_id": req.session_id
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
def health():

    return {
        "status": "ok",
        "active_sessions": len(agents)
    }


# ============================================================
# FRONTEND
# ============================================================

if os.path.exists("static"):
    app.mount(
        "/",
        StaticFiles(
            html=True,
            directory="static"
        ),
        name="static"
    )


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    uvicorn = importlib.import_module("uvicorn")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )

