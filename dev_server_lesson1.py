"""
BrightSmile MCP Server — Lesson 1
-----------------------------------
This takes two tools from your dental agent (get_clinic_info and
search_services) and exposes them as a standalone MCP server — meaning
Claude Desktop, or any other MCP-compatible AI tool, can call them
directly, without your dental_agent.py script running at all.

SETUP:
1. pip install fastmcp
2. Run this file directly to test it:  python mcp_server.py
   (fastmcp will start it and wait for a client to connect)
3. To actually see it working, use the built-in inspector:
   fastmcp dev mcp_server.py
   This opens a browser tool where you can call get_clinic_info and
   search_services yourself and see the JSON that comes back — exactly
   what an AI model would see.
"""

from fastmcp import FastMCP

# ---- Same demo data as your dental agent (trimmed to 2 services for this lesson) ----
CLINIC_INFO = {
    "name": "BrightSmile Dental Clinic",
    "address": "12-B, Main Boulevard, Gulberg III, Lahore",
    "phone": "042-3571-2233",
    "hours": "Mon-Sat 10:00-20:00; Sunday closed; Friday break 13:00-14:30",
}

SERVICES = [
    {"id": 1, "name": "Consultation & Examination", "category": "General", "price": 1500},
    {"id": 2, "name": "Scaling & Polishing", "category": "Hygiene", "price": 4000},
    {"id": 5, "name": "Root Canal Treatment", "category": "Restorative", "price": 18000},
]

# ---- Create the MCP server ----
mcp = FastMCP("BrightSmile Dental Info")


@mcp.tool
def get_clinic_info() -> str:
    """Returns the clinic's address, phone number, and opening hours."""
    return (
        "Clinic: BrightSmile Dental Clinic\n"
        "Address: 12-B, Main Boulevard, Gulberg III, Lahore\n"
        "Phone: 042-3571-2233\n"
        "Hours: Mon-Sat 10:00-20:00; Sunday closed; "
        "Friday break 13:00-14:30"
    )


@mcp.tool
def search_services(keyword: str = "") -> list:
    """Search dental services by keyword in the name (e.g. 'root canal', 'cleaning').
    Returns matching services with id, name, category, and price in PKR."""
    if not keyword:
        return SERVICES
    return [s for s in SERVICES if keyword.lower() in s["name"].lower()]

@mcp.tool
def list_doctors() -> list:
    """Returns the list of dentists at the clinic with their specialities."""
    return [
        {"name": "Dr. Ayesha Khan", "speciality": "General & Cosmetic Dentistry"},
        {"name": "Dr. Bilal Ahmed", "speciality": "Orthodontics"},
        {"name": "Dr. Sana Malik", "speciality": "Endodontics"},
        {"name": "Dr. Omar Farooq", "speciality": "Periodontics"},
        {"name": "Dr. Fatima Riaz", "speciality": "Pediatric Dentistry"},
    ]


if __name__ == "__main__":
    mcp.run()