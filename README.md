# AI-BrightSmile-Dental-Clinic.aqum
AI-powered dental clinic front-desk assistant — patient booking, scheduling, and clinic info via Claude's tool-calling API
# 🦷 BrightSmile Dental Clinic — AI Receptionist Agent

An AI-powered virtual receptionist for a dental clinic, built with the
Claude API. It handles patient lookup/registration, appointment booking,
service and doctor search, and clinic FAQs — with hard safety rules
against ever giving medical advice or naming medications.

## What it does

- 📅 **Books, views, and cancels appointments** — checks real doctor
  availability, working days, and avoids double-booking
- 🧑‍⚕️ **Routes patients to the right doctor** — e.g. children under 14
  are automatically routed to the pediatric dentist
- 🔍 **Searches services and doctors** by keyword or speciality
- 🚨 **Handles emergencies** — same-day emergency slots, safe self-care
  guidance only (never medication), escalates to ER when needed
- 🛡️ **Safety-first by design** — never diagnoses, never names or doses
  medication, never invents prices, slots, or patient data

## Three versions in this repo

| File | What it demonstrates |
|---|---|
| `agent.py` | Core agent — manual tool-calling loop with the raw Anthropic API |
| `mcp_server.py` | The same tools exposed as an MCP server (usable by Claude Desktop or any MCP client) |
| `Langchain agent.py` | The same tools rebuilt using LangChain's `create_agent()` |

## Tech stack

- Python
- Anthropic Claude API (`claude-haiku-4-5`)
- SQLite (patients, doctors, services, appointments)
- FastAPI (`main.py`) — HTTP API wrapper for a frontend
- MCP (Model Context Protocol)
- LangChain

## How to run it

```bash
pip install anthropic fastapi uvicorn langchain langchain-anthropic fastmcp
export ANTHROPIC_API_KEY=your-key-here   # Windows: setx ANTHROPIC_API_KEY your-key-here

python agent.py              # command-line chat
python main.py                # run as an API (for a website/frontend)
python mcp_server.py          # run as an MCP server
python "Langchain agent.py"   # run the LangChain version
```

## Demo

*(video link here — see it book a real appointment end-to-end)*

## Why this project

Built as a portfolio piece demonstrating production-style patterns for
service-business AI agents: tool calling, safety guardrails, database-backed
state, and multiple integration paths (raw API, MCP, LangChain).

⚠️ **Demo project** — clinic name, doctors, and data are fictional.
