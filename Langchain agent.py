"""
BrightSmile LangChain Agent — Lesson
---------------------------------------
This rebuilds the SAME two tools from your dental agent (get_clinic_info,
search_services), but instead of manually writing the tool-calling loop
(the `for _ in range(10): ...` in your dental_agent.py), we let
LangChain's create_agent() handle that loop for us.

Compare this file to your dental_agent.py's `chat()` method — you'll see
create_agent() is doing exactly what you built by hand, just packaged
into one function call.

SETUP:
1. pip install langchain langchain-anthropic
2. Make sure ANTHROPIC_API_KEY is set (same as your dental agent needed)
3. Run: python langchain_agent.py
"""

from langchain.agents import create_agent
from langchain_core.tools import tool

# ---- Same demo data as your dental agent ----
CLINIC_INFO = {
    "name": "BrightSmile Dental Clinic",
    "address": "12-B, Main Boulevard, Gulberg III, Lahore",
    "phone": "042-3571-2233",
    "hours": "Mon-Sat 10:00-20:00; Sunday closed; Friday break 13:00-14:30",
}

SERVICES = [
    {"id": 1, "name": "Consultation & Examination", "category": "General", "price": 1500,
     "description": "Check-up of teeth and gums to find out what treatment is needed."},
    {"id": 2, "name": "Scaling & Polishing", "category": "Hygiene", "price": 4000,
     "description": "Professional cleaning that removes plaque and stains."},
    {"id": 5, "name": "Root Canal Treatment", "category": "Restorative", "price": 18000,
     "description": "Removes infected nerve tissue to save a badly damaged tooth."},
]

DOCTORS = [
    {"name": "Dr. Ayesha Khan", "speciality": "General & Cosmetic Dentistry"},
    {"name": "Dr. Bilal Ahmed", "speciality": "Orthodontics"},
    {"name": "Dr. Sana Malik", "speciality": "Pediatric Dentistry (under 14)"},
    {"name": "Dr. Hamza Sheikh", "speciality": "Oral Surgery & Implants"},
]


# ---- Tools: same logic as your dental agent's tool_get_clinic_info /
# tool_search_services, just wrapped with LangChain's @tool decorator
# instead of being a method on your class. ----

@tool
def get_clinic_info() -> dict:
    """Returns the clinic's address, phone number, and opening hours."""
    return CLINIC_INFO


@tool
def search_services(keyword: str = "") -> list:
    """Search dental services by keyword in the name (e.g. 'root canal',
    'cleaning'). Returns matching services with id, name, category, and
    price in PKR."""
    if not keyword:
        return SERVICES
    k = keyword.lower()
    return [s for s in SERVICES if k in s["name"].lower() or k in s["description"].lower()]


@tool
def list_doctors() -> list:
    """Returns the list of dentists at the clinic with their specialities."""
    return DOCTORS


# ---- The agent itself ----
# Compare this ONE call to your dental_agent.py's __init__ + build_tools +
# the whole chat() method. create_agent() builds the same reasoning loop
# internally: call the model -> did it request a tool? -> run the tool ->
# feed the result back -> repeat until the model gives a final answer.

agent = create_agent(
    model="claude-haiku-4-5-20251001",
    tools=[get_clinic_info, search_services, list_doctors],
    system_prompt=(
        "You are 'Smile', the front-desk assistant for BrightSmile Dental "
        "Clinic in Lahore. Prices are in PKR. Only state information that "
        "came from a tool result — never invent prices or hours."
    ),
)


def chat(message: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": message}]})
    return result["messages"][-1].content


if __name__ == "__main__":
    print("BrightSmile LangChain Agent — type 'exit' to quit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            break
        if not user_input:
            continue
        print("AI:", chat(user_input))