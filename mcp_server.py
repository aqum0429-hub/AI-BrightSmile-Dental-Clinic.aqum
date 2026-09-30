from fastmcp import FastMCP
import agent as dental
import json

# --------------------------------------------------
# MCP SERVER
# --------------------------------------------------

mcp = FastMCP("BrightSmile Dental Clinic")


# --------------------------------------------------
# 1. CLINIC INFO
# --------------------------------------------------

@mcp.tool
def get_clinic_info() -> str:
    """Get BrightSmile Dental Clinic address, phone, hours, parking and payment information."""
    return dental.ok(
        currency="PKR",
        **dental.CLINIC_INFO
    )


# --------------------------------------------------
# 2. LIST DOCTORS
# --------------------------------------------------

@mcp.tool
def list_doctors(speciality: str = "") -> str:
    """List clinic doctors. Optionally filter by speciality."""
    # Create lightweight object without starting the Anthropic AI agent
    obj = dental.DentalClinicAgent.__new__(dental.DentalClinicAgent)

    result = obj.tool_list_doctors(
        speciality=speciality if speciality else None
    )

    return result


# --------------------------------------------------
# 3. SEARCH SERVICES
# --------------------------------------------------

@mcp.tool
def search_services(
    keyword: str = "",
    category: str = "",
    max_price: int = 0
) -> str:
    """Search dental services by keyword, category or maximum price."""
    obj = dental.DentalClinicAgent.__new__(dental.DentalClinicAgent)

    result = obj.tool_search_services(
        keyword=keyword if keyword else None,
        category=category if category else None,
        max_price=max_price if max_price > 0 else None
    )

    return result


# --------------------------------------------------
# 4. FIND PATIENT
# --------------------------------------------------

@mcp.tool
def find_patient(
    phone: str = "",
    name: str = ""
) -> str:
    """Find a patient using phone number or name."""
    obj = dental.DentalClinicAgent.__new__(dental.DentalClinicAgent)
    obj.active_patient_id = None

    result = obj.tool_find_patient(
        phone=phone if phone else None,
        name=name if name else None
    )

    return result


# --------------------------------------------------
# 5. ADD PATIENT
# --------------------------------------------------

@mcp.tool
def add_patient(
    name: str,
    phone: str,
    age: int = 0,
    gender: str = "",
    city: str = "",
    allergies: str = "",
    conditions: str = ""
) -> str:
    """Register a new dental patient."""
    obj = dental.DentalClinicAgent.__new__(dental.DentalClinicAgent)
    obj.active_patient_id = None

    result = obj.tool_add_patient(
        name=name,
        phone=phone,
        age=age if age > 0 else None,
        gender=gender if gender else None,
        city=city if city else None,
        allergies=allergies if allergies else None,
        conditions=conditions if conditions else None
    )

    return result


# --------------------------------------------------
# 6. AVAILABLE APPOINTMENT SLOTS
# --------------------------------------------------

@mcp.tool
def get_available_slots(
    doctor_id: int,
    date: str,
    service_id: int = 0,
    emergency: bool = False
) -> str:
    """Find available appointment times for a doctor on a specific date."""
    obj = dental.DentalClinicAgent.__new__(dental.DentalClinicAgent)

    result = obj.tool_get_available_slots(
        doctor_id=doctor_id,
        date=date,
        service_id=service_id if service_id > 0 else None,
        emergency=emergency
    )

    return result


# --------------------------------------------------
# 7. DATABASE INITIALIZATION
# --------------------------------------------------

try:
    dental.init_db()
    print("Database initialized successfully.")
except Exception as e:
    print(f"Database initialization warning: {e}")


# --------------------------------------------------
# START MCP SERVER
# --------------------------------------------------

if __name__ == "__main__":
    mcp.run()