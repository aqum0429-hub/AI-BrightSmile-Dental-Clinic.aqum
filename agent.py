import os
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import cast
import anthropic

DB_FILE = "clinic.db"
MODEL = "claude-haiku-4-5-20251001"

WORK_START, WORK_END = "10:00", "20:00"
FRIDAY_BREAK = ("13:00", "14:30")
SLOT_MIN = 30
EMERGENCY_WINDOWS = [("10:00", "11:00"), ("18:00", "19:00")]
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ==========================================================
# 1. SEED DATA
# ==========================================================

DOCTORS = [
    (1, "Dr. Ayesha Khan",   "General & Cosmetic Dentistry",  "Mon,Tue,Thu,Sat", 1500),
    (2, "Dr. Bilal Ahmed",   "Orthodontics",                  "Tue,Wed,Fri",     2500),
    (3, "Dr. Sana Malik",    "Pediatric Dentistry (under 14)", "Mon,Wed,Thu,Sat", 1500),
    (4, "Dr. Hamza Sheikh",  "Oral Surgery & Implants",       "Mon,Wed,Fri,Sat", 3000),
]

# Each service now carries its own post_care tip — general, non-medication
# self-care guidance only. No medicines, dosages, or diagnoses are ever
# included here on purpose.
SERVICES = [
    (1,  "Consultation & Examination", "General",      1500,   30, "1,3",
     "Check-up of teeth and gums to find out what treatment, if any, is needed.",
     "No special aftercare needed — resume normal eating and brushing right away."),
    (2,  "Scaling & Polishing",        "Hygiene",      4000,   30, "1",
     "Professional cleaning that removes plaque and stains.",
     "Mild gum sensitivity for a day is normal. Avoid very hot or cold food/drinks for a few hours."),
    (3,  "Deep Cleaning (per quadrant)","Hygiene",     6000,   60, "1",
     "Cleaning below the gum line for gum disease.",
     "Some soreness for 1-2 days is expected. Rinse gently with warm salt water and brush softly around the area."),
    (4,  "Composite Filling",          "Restorative",  5000,   30, "1,3",
     "Tooth-coloured filling for a cavity.",
     "Avoid chewing on that side until numbness fully wears off. Mild sensitivity to hot/cold for a few days is normal."),
    (5,  "Root Canal Treatment",       "Restorative",  18000,  90, "1",
     "Removes infected nerve tissue to save a badly damaged tooth.",
     "Avoid chewing on the treated tooth until your follow-up crown/filling is placed. Mild soreness for a few days is normal."),
    (6,  "Crown (Zirconia)",           "Restorative",  35000,  60, "1",
     "Strong tooth-coloured cap placed over a weak tooth.",
     "Avoid sticky or very hard foods for the first 24 hours. Some initial sensitivity is normal."),
    (7,  "Simple Extraction",          "Surgery",      4500,   30, "1,4",
     "Removal of a tooth that cannot be saved.",
     "Bite gently on gauze for 30-45 minutes. Avoid rinsing, spitting hard, or using a straw for 24 hours. "
     "Stick to soft foods and use a cold compress on the cheek if swelling occurs."),
    (8,  "Wisdom Tooth Extraction",    "Surgery",      15000,  60, "4",
     "Surgical removal of a wisdom tooth.",
     "Rest for the remainder of the day. Use a cold compress for swelling, eat only soft foods for 2-3 days, "
     "and avoid straws and smoking, which can disturb healing."),
    (9,  "Dental Implant (per tooth)", "Surgery",      120000, 90, "4",
     "Permanent replacement of a missing tooth with a titanium root and crown.",
     "Avoid chewing on the implant side for the first few days. Stick to a soft diet, use a cold compress for "
     "swelling, and avoid strenuous exercise for 48 hours."),
    (10, "Braces (Metal, full)",       "Orthodontics", 150000, 60, "2",
     "Straightens teeth over 12–24 months.",
     "Soreness for the first few days after adjustment is normal. Eat softer foods initially, and use orthodontic "
     "wax on any bracket that irritates your cheek."),
    (11, "Clear Aligners (full)",      "Orthodontics", 280000, 60, "2",
     "Nearly invisible removable trays that straighten teeth.",
     "A feeling of pressure for a day or two after switching to a new tray is normal. Remove aligners before "
     "eating or drinking anything except water."),
    (12, "Teeth Whitening (in-clinic)","Cosmetic",     25000,  60, "1",
     "Brightens teeth several shades in one visit.",
     "Avoid staining foods and drinks (coffee, tea, red wine, curry) for 24-48 hours. Mild, temporary sensitivity "
     "is normal right after treatment."),
    (13, "Veneers (per tooth)",        "Cosmetic",     30000,  60, "1",
     "Thin shells bonded to the front of teeth to improve appearance.",
     "Avoid biting hard objects (pens, nails, ice) to protect the veneer. Mild sensitivity initially is normal."),
    (14, "Child Check-up & Fluoride",  "Pediatric",    2500,   30, "3",
     "Gentle exam and fluoride coating for children.",
     "Avoid eating or drinking for 30 minutes after the fluoride treatment so it can fully absorb."),
    (15, "Emergency Visit",            "Emergency",    3000,   30, "1,2,3,4",
     "Same-day visit for severe pain, swelling, or injury.",
     "Follow-up care depends on what treatment was given during your visit — the dentist will explain this "
     "directly. Rest and a cold compress can help general swelling in the meantime."),
]

CLINIC_INFO = {
    "name": "BrightSmile Dental Clinic",
    "address": "12-B, Main Boulevard, Gulberg III, Lahore",
    "phone": "042-3571-2233",
    "whatsapp": "0321-4455667",
    "hours": "Mon–Sat 10:00–20:00; Sunday closed; Friday break 13:00–14:30",
    "parking": "Free parking behind the building",
    "payment": "Cash, bank transfer, debit/credit cards. Itemised invoice for insurance reimbursement.",
    "instalments": "Available for treatments above Rs. 50,000 — explained by clinic manager at first visit",
    "xray": {"digital_xray": 800, "opg": 2500},
    "accessibility": "Ground floor, wheelchair accessible",
    "cancellation_policy": "Free cancellation 24+ hours before. Late cancellations are noted. After 2 no-shows, advance payment is required.",
}

# ==========================================================
# 2. DATABASE LAYER
# ==========================================================

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db_conn():
    """Connection-per-call context manager that commits/rolls back AND
    always closes the connection (sqlite3's own context manager only
    commits/rolls back — it never closes, which leaks connections)."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT NOT NULL UNIQUE,
            age INTEGER, gender TEXT, city TEXT, allergies TEXT, conditions TEXT,
            no_shows INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, speciality TEXT NOT NULL,
            working_days TEXT NOT NULL, fee INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price INTEGER NOT NULL,
            duration_min INTEGER NOT NULL, doctor_ids TEXT NOT NULL, description TEXT NOT NULL,
            post_care TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER NOT NULL, doctor_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL, date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
            status TEXT NOT NULL, is_emergency INTEGER NOT NULL DEFAULT 0, notes TEXT, created_at TEXT NOT NULL);
    """)
    if conn.execute("SELECT COUNT(*) c FROM doctors").fetchone()["c"] == 0:
        conn.executemany("INSERT INTO doctors VALUES (?,?,?,?,?)", DOCTORS)
        conn.executemany("INSERT INTO services VALUES (?,?,?,?,?,?,?,?)", SERVICES)
        print(f"(seeded {len(DOCTORS)} doctors, {len(SERVICES)} services)")
    conn.commit()
    conn.close()


# ==========================================================
# 3. HELPERS
# ==========================================================

def ok(**d):      return json.dumps({"success": True, **d}, ensure_ascii=False)
def fail(r, **d):  return json.dumps({"success": False, "reason": r, **d}, ensure_ascii=False)
def rows(rs):      return [dict(r) for r in rs]

def t2m(t):  h, m = map(int, t.split(":")); return h * 60 + m
def m2t(m):  return f"{m // 60:02d}:{m % 60:02d}"
def add_min(t, n): return m2t(t2m(t) + n)

def overlaps(a_start, a_end, b_start, b_end):
    return t2m(a_start) < t2m(b_end) and t2m(b_start) < t2m(a_end)


# ==========================================================
# 4. AGENT
# ==========================================================

def _load_system_prompt():
    if os.path.exists("dental_system_prompt.txt"):
        with open("dental_system_prompt.txt", encoding="utf-8") as f:
            return f.read()
    return (
        "You are 'Smile', the virtual front-desk assistant for BrightSmile Dental Clinic, Lahore, Pakistan. "
        "Prices are in Rs. HARD RULES: never state prices/slots/patient data not from a tool; never invent doctors, "
        "services or slots; NEVER diagnose or name/recommend any medicine, drug, or dosage — if asked about "
        "medication, say to ask a pharmacist or the dentist at the visit; identify the patient (find_patient, then "
        "add_patient) before booking/viewing/cancelling; confirm doctor+service+date+time and wait for a clear yes "
        "before book_appointment; when a booking succeeds, always share its post_care tip from the tool result; if "
        "a tool fails, say so honestly and offer an alternative; children under 14 see Dr. Sana Malik only; "
        "braces/aligners → Dr. Bilal Ahmed; implants/wisdom teeth → Dr. Hamza Sheikh. EMERGENCY (severe pain, "
        "swelling, bleeding, knocked-out tooth): empathise, take only name+phone, book same-day emergency slot; "
        "suggest only safe self-care while they wait (cold compress, saltwater rinse, keep head elevated) — never "
        "medication; if swelling affects breathing/swallowing or high fever, send to hospital ER. After booking "
        "give pre-visit instructions: arrive 10 min early with CNIC and old X-rays, mention medical conditions/"
        "blood thinners, guardian required for children, arrange a driver for extractions/implants. Be warm, "
        "brief, and reassuring."
    )


SYSTEM_PROMPT = _load_system_prompt()


class DentalClinicAgent:

    def __init__(self, session_id: str = "default"):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Set it with:\n"
                "  export ANTHROPIC_API_KEY=your-key-here   (macOS/Linux)\n"
                "  setx ANTHROPIC_API_KEY your-key-here      (Windows)"
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.session_id = session_id
        # Each session gets its own memory file, so one patient's
        # conversation/state never leaks into another patient's session.
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        self.memory_file = f"clinic_memory_{safe_id}.json"
        self.active_patient_id = None
        self.conversation = self.load_memory() or []
        # The schemas are plain dictionaries at runtime, but the Anthropic
        # client expects its generated ToolParam TypedDict type statically.
        self.tools = cast(list[anthropic.types.ToolParam], self.build_tools())

    # ---------------- tool schemas ----------------
    def build_tools(self):
        return [
            {"name": "get_clinic_info", "description": "Address, hours, parking, payment, cancellation policy, X-ray prices.",
             "input_schema": {"type": "object", "properties": {}, "required": []}},
            {"name": "list_doctors", "description": "List doctors with speciality, working days and fee.",
             "input_schema": {"type": "object", "properties": {"speciality": {"type": "string"}}, "required": []}},
            {"name": "search_services", "description": "Search services by keyword, category or max price. Returns id, price, duration, eligible doctors, and post-care tips.",
             "input_schema": {"type": "object", "properties": {
                 "keyword": {"type": "string"}, "category": {"type": "string"}, "max_price": {"type": "integer"}}, "required": []}},
            {"name": "find_patient", "description": "Look up a patient by phone (preferred) or name. Sets active patient if exactly one match.",
             "input_schema": {"type": "object", "properties": {"phone": {"type": "string"}, "name": {"type": "string"}}, "required": []}},
            {"name": "add_patient", "description": "Register a new patient. Call only after find_patient failed.",
             "input_schema": {"type": "object", "properties": {
                 "name": {"type": "string"}, "phone": {"type": "string"}, "age": {"type": "integer"},
                 "gender": {"type": "string"}, "city": {"type": "string"},
                 "allergies": {"type": "string"}, "conditions": {"type": "string"}}, "required": ["name", "phone"]}},
            {"name": "update_patient", "description": "Update one field of the active patient: name, phone, age, gender, city, allergies, conditions.",
             "input_schema": {"type": "object", "properties": {"field": {"type": "string"}, "value": {"type": "string"}}, "required": ["field", "value"]}},
            {"name": "get_available_slots", "description": "Free start times for a doctor on a date (YYYY-MM-DD). Pass service_id so the full duration fits. emergency=true restricts to emergency windows today.",
             "input_schema": {"type": "object", "properties": {
                 "doctor_id": {"type": "integer"}, "date": {"type": "string"},
                 "service_id": {"type": "integer"}, "emergency": {"type": "boolean"}}, "required": ["doctor_id", "date"]}},
            {"name": "book_appointment", "description": "Book for the active patient. Validates doctor/service match, age rules and slot availability. Result includes post-care tips for the booked service.",
             "input_schema": {"type": "object", "properties": {
                 "doctor_id": {"type": "integer"}, "service_id": {"type": "integer"},
                 "date": {"type": "string"}, "start_time": {"type": "string"},
                 "is_emergency": {"type": "boolean"}, "notes": {"type": "string"}},
                 "required": ["doctor_id", "service_id", "date", "start_time"]}},
            {"name": "view_appointments", "description": "Active patient's upcoming and past appointments.",
             "input_schema": {"type": "object", "properties": {}, "required": []}},
            {"name": "cancel_appointment", "description": "Cancel one of the active patient's appointments by id.",
             "input_schema": {"type": "object", "properties": {"appointment_id": {"type": "integer"}}, "required": ["appointment_id"]}},
        ]

    # ---------------- tool implementations ----------------
    def _need_patient(self):
        return None if self.active_patient_id else fail("No active patient. Call find_patient or add_patient first.")

    def tool_get_clinic_info(self):
        return ok(currency="PKR", **CLINIC_INFO)

    def tool_list_doctors(self, speciality=None):
        with db_conn() as c:
            rs = c.execute("SELECT * FROM doctors").fetchall()
        docs = rows(rs)
        if speciality:
            docs = [d for d in docs if speciality.lower() in d["speciality"].lower()]
        return ok(currency="PKR", doctors=docs) if docs else fail("No doctor with that speciality.")

    def tool_search_services(self, keyword=None, category=None, max_price=None):
        sql, p = "SELECT * FROM services WHERE 1=1", []
        if keyword:   sql += " AND (lower(name) LIKE lower(?) OR lower(description) LIKE lower(?))"; p += [f"%{keyword}%"] * 2
        if category:  sql += " AND lower(category)=lower(?)"; p.append(category)
        if max_price: sql += " AND price<=?"; p.append(int(max_price))
        with db_conn() as c:
            rs = rows(c.execute(sql + " ORDER BY category, price", p).fetchall())
            names = {d["id"]: d["name"] for d in rows(c.execute("SELECT id,name FROM doctors").fetchall())}
        for s in rs:
            s["doctors"] = [names[int(i)] for i in s["doctor_ids"].split(",")]
        return ok(currency="PKR", services=rs) if rs else fail("No matching service. Offer a Consultation instead.")

    def tool_find_patient(self, phone=None, name=None):
        if not phone and not name:
            return fail("Provide phone or name.")
        with db_conn() as c:
            if phone:
                rs = rows(c.execute("SELECT * FROM patients WHERE phone=?", (phone.strip(),)).fetchall())
            else:
                rs = rows(c.execute("SELECT * FROM patients WHERE lower(name) LIKE lower(?)", (f"%{name.strip() if name else ''}%",)).fetchall())
        if not rs:
            return fail("Patient not found.")
        if len(rs) > 1:
            return fail("Multiple patients match. Ask for phone number.", matches=[{"id": r["id"], "name": r["name"]} for r in rs])
        self.active_patient_id = rs[0]["id"]
        return ok(patient=rs[0], active=True)

    def tool_add_patient(self, name, phone, age=None, gender=None, city=None, allergies=None, conditions=None):
        try:
            with db_conn() as c:
                cur = c.execute("INSERT INTO patients (name,phone,age,gender,city,allergies,conditions,created_at) VALUES (?,?,?,?,?,?,?,?)",
                                (name.strip(), phone.strip(), age, gender, city, allergies, conditions, datetime.now().isoformat(timespec="seconds")))
                pid = cur.lastrowid
        except sqlite3.IntegrityError:
            return fail("This phone number is already registered. Use find_patient.")
        self.active_patient_id = pid
        return ok(patient={"id": pid, "name": name, "phone": phone, "age": age}, active=True)

    def tool_update_patient(self, field, value):
        if e := self._need_patient(): return e
        if field not in ("name", "phone", "age", "gender", "city", "allergies", "conditions"):
            return fail(f"Cannot update '{field}'.")
        try:
            with db_conn() as c:
                c.execute(f"UPDATE patients SET {field}=? WHERE id=?", (value, self.active_patient_id))
                row = c.execute("SELECT * FROM patients WHERE id=?", (self.active_patient_id,)).fetchone()
        except sqlite3.IntegrityError:
            return fail("That phone number belongs to another patient.")
        return ok(patient=dict(row))

    def _day_ok(self, d, doc):
        abbr = DAY_ABBR[d.weekday()]
        if abbr == "Sun":
            return "Clinic is closed on Sunday."
        if abbr not in doc["working_days"].split(","):
            return f"{doc['name']} works on {doc['working_days']} only."
        return None

    def tool_get_available_slots(self, doctor_id, date, service_id=None, emergency=False):
        try:
            d = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return fail("Date must be YYYY-MM-DD.")
        today = datetime.now().date()
        if d < today:
            return fail("That date is in the past.", today=str(today))
        if emergency and d != today:
            return fail("Emergency slots are same-day only.", today=str(today))
        with db_conn() as c:
            doc = c.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,)).fetchone()
            if not doc: return fail("No such doctor.")
            dur = SLOT_MIN
            if service_id:
                svc = c.execute("SELECT * FROM services WHERE id=?", (service_id,)).fetchone()
                if not svc: return fail("No such service.")
                if str(doctor_id) not in svc["doctor_ids"].split(","):
                    return fail(f"{doc['name']} does not perform {svc['name']}.", eligible_doctor_ids=svc["doctor_ids"])
                dur = svc["duration_min"]
            if (why := self._day_ok(d, doc)):
                return fail(why)
            booked = rows(c.execute("SELECT start_time,end_time FROM appointments WHERE doctor_id=? AND date=? AND status='booked'",
                                    (doctor_id, date)).fetchall())
        windows = EMERGENCY_WINDOWS if emergency else [(WORK_START, WORK_END)]
        now_m = t2m(datetime.now().strftime("%H:%M")) if d == today else -1
        free = []
        for ws, we in windows:
            t = t2m(ws)
            while t + dur <= t2m(we):
                s, e = m2t(t), m2t(t + dur)
                clash = any(overlaps(s, e, b["start_time"], b["end_time"]) for b in booked)
                fri_break = DAY_ABBR[d.weekday()] == "Fri" and overlaps(s, e, *FRIDAY_BREAK)
                if not clash and not fri_break and t > now_m:
                    free.append(s)
                t += SLOT_MIN
        if not free:
            return fail("No free slots that day.", suggestion="Try the doctor's next working day.")
        return ok(doctor=doc["name"], date=date, duration_min=dur, slots=free)

    def tool_book_appointment(self, doctor_id, service_id, date, start_time, is_emergency=False, notes=None):
        if e := self._need_patient(): return e
        slots = json.loads(self.tool_get_available_slots(doctor_id, date, service_id, is_emergency))
        if not slots["success"]:
            return json.dumps(slots)
        if start_time not in slots["slots"]:
            return fail("That time is not available.", available=slots["slots"][:6])
        with db_conn() as c:
            pat = c.execute("SELECT * FROM patients WHERE id=?", (self.active_patient_id,)).fetchone()
            svc = c.execute("SELECT * FROM services WHERE id=?", (service_id,)).fetchone()
            doc = c.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,)).fetchone()
            if pat["no_shows"] >= 2:
                return fail("Patient has 2+ no-shows. Ask them to call the clinic to book with advance payment.")
            if pat["age"] is not None and pat["age"] < 14 and doctor_id != 3:
                return fail("Patients under 14 must be booked with Dr. Sana Malik (doctor_id 3).")
            if pat["age"] is not None and pat["age"] >= 14 and doctor_id == 3 and not is_emergency:
                return fail("Dr. Sana Malik sees children under 14 only.")
            end_time = add_min(start_time, svc["duration_min"])
            mine = rows(c.execute("SELECT start_time,end_time FROM appointments WHERE patient_id=? AND date=? AND status='booked'",
                                  (self.active_patient_id, date)).fetchall())
            if any(overlaps(start_time, end_time, m["start_time"], m["end_time"]) for m in mine):
                return fail("Patient already has an appointment at that time.")
            cur = c.execute("INSERT INTO appointments (patient_id,doctor_id,service_id,date,start_time,end_time,status,is_emergency,notes,created_at) "
                            "VALUES (?,?,?,?,?,?,'booked',?,?,?)",
                            (self.active_patient_id, doctor_id, service_id, date, start_time, end_time,
                             1 if is_emergency else 0, notes, datetime.now().isoformat(timespec="seconds")))
            aid = cur.lastrowid
        return ok(currency="PKR", appointment_id=aid, patient=pat["name"], doctor=doc["name"], service=svc["name"],
                  date=date, start_time=start_time, end_time=end_time, price=svc["price"],
                  post_care=svc["post_care"],
                  pre_visit=["Arrive 10 minutes early with CNIC and any old X-rays",
                             "Tell reception about medical conditions and medicines (esp. blood thinners)",
                             "Guardian must attend for children",
                             "Arrange a driver for extractions or implants"])

    def tool_view_appointments(self):
        if e := self._need_patient(): return e
        with db_conn() as c:
            rs = rows(c.execute("""SELECT a.id, a.date, a.start_time, a.end_time, a.status, a.is_emergency,
                                          d.name AS doctor, s.name AS service, s.price
                                   FROM appointments a JOIN doctors d ON d.id=a.doctor_id JOIN services s ON s.id=a.service_id
                                   WHERE a.patient_id=? ORDER BY a.date, a.start_time""", (self.active_patient_id,)).fetchall())
        today = str(datetime.now().date())
        return ok(currency="PKR",
                  upcoming=[r for r in rs if r["status"] == "booked" and r["date"] >= today],
                  past=[r for r in rs if not (r["status"] == "booked" and r["date"] >= today)])

    def tool_cancel_appointment(self, appointment_id):
        if e := self._need_patient(): return e
        with db_conn() as c:
            a = c.execute("SELECT * FROM appointments WHERE id=? AND patient_id=?", (appointment_id, self.active_patient_id)).fetchone()
            if not a: return fail("No such appointment for this patient.")
            if a["status"] != "booked": return fail(f"Appointment is already {a['status']}.")
            start = datetime.strptime(f"{a['date']} {a['start_time']}", "%Y-%m-%d %H:%M")
            late = (start - datetime.now()) < timedelta(hours=24)
            c.execute("UPDATE appointments SET status='cancelled', notes=COALESCE(notes,'') || ? WHERE id=?",
                      (" [late cancellation]" if late else " [cancelled]", appointment_id))
        return ok(appointment_id=appointment_id, status="cancelled", late_cancellation=late)

    def run_tool(self, name, args):
        fn = getattr(self, f"tool_{name}", None)
        if not fn: return fail(f"Unknown tool {name}")
        try:
            return fn(**args)
        except TypeError as ex:
            return fail(f"Bad arguments: {ex}")
        except Exception as ex:
            return fail(f"Internal error: {type(ex).__name__}: {ex}")

    # ---------------- memory ----------------
    def load_memory(self):
        if not os.path.exists(self.memory_file): return None
        try:
            with open(self.memory_file, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        conv = data.get("conversation", [])
        self.active_patient_id = data.get("active_patient_id")
        if conv and conv[-1]["role"] == "assistant":
            content = conv[-1]["content"]
            if isinstance(content, list) and any(b.get("type") == "tool_use" for b in content):
                conv.pop()
        if conv and conv[-1]["role"] == "user" and isinstance(conv[-1]["content"], list):
            # A dangling tool_result batch with no assistant reply yet — drop the
            # matching tool_use turn before it too, so history stays valid to resend.
            conv.pop()
            if conv and conv[-1]["role"] == "assistant":
                conv.pop()
        return conv or None

    def save_memory(self):
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump({"active_patient_id": self.active_patient_id, "conversation": self.conversation},
                      f, ensure_ascii=False, indent=2)

    def reset(self):
        self.conversation, self.active_patient_id = [], None
        if os.path.exists(self.memory_file): os.remove(self.memory_file)

    # ---------------- agent loop ----------------
    def chat(self, text, verbose=True):
        self.conversation.append({"role": "user", "content": text})
        now = datetime.now()
        system = SYSTEM_PROMPT + f"\n\nCURRENT DATE/TIME: {now.strftime('%A, %d %B %Y, %H:%M')} (ISO {now.date()})"

        for _ in range(10):
            try:
                resp = self.client.messages.create(model=MODEL, max_tokens=1024, system=system,
                                                    tools=self.tools, messages=self.conversation)
            except Exception as e:
                self.conversation.pop()  # drop the user message that failed to get a response
                return f"Something went wrong talking to the model ({e})."

            blocks = [b.model_dump(exclude_none=True) for b in resp.content]
            self.conversation.append({"role": "assistant", "content": blocks})

            tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
            text_blocks = [b.get("text", "") for b in blocks if b.get("type") == "text"]

            if verbose:
                for tu in tool_uses:
                    print(f"[tool:{self.session_id}] {tu['name']}({tu.get('input')})")

            if not tool_uses:
                self.save_memory()
                return "".join(text_blocks)

            tool_results = []
            for tu in tool_uses:
                result = self.run_tool(tu["name"], tu.get("input", {}))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": result
                })
            self.conversation.append({"role": "user", "content": tool_results})

        self.save_memory()
        return "Sorry, that took too many steps to resolve. Could you rephrase or simplify your request?"

    def run(self):
        print("BrightSmile Dental Clinic — 'Smile' assistant ready. Type 'exit' to quit, 'reset' to start over.\n")
        while True:
            try:
                text = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break
            if not text:
                continue
            if text.lower() == "exit":
                print("Goodbye!")
                break
            if text.lower() == "reset":
                self.reset()
                print("(conversation reset)")
                continue
            reply = self.chat(text)
            print("AI:", reply)


if __name__ == "__main__":
    init_db()
    agent = DentalClinicAgent()
    agent.run()