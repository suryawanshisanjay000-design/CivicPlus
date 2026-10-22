import base64
import hashlib
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import create_access_token, decode_access_token, verify_password
from config import settings
from database import supabase
from models import (
    DashboardStats,
    DepartmentCode,
    LoginRequest,
    LoginResponse,
    TicketAction,
    TicketCreate,
    TicketResponse,
    TicketStatus,
    TrackRequest,
    UserRole,
)
from triage import groq_triage

app = FastAPI(title="CivicPulse API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

DEPARTMENTS = {
    DepartmentCode.ROADS: ("Roads", 48),
    DepartmentCode.WATER: ("Water", 24),
    DepartmentCode.SOLID_WASTE: ("Solid Waste", 24),
    DepartmentCode.ELECTRICAL: ("Electrical", 12),
    DepartmentCode.PUBLIC_HEALTH: ("Public Health", 72),
}

SLA_HOURS = {
    DepartmentCode.ROADS: 48,
    DepartmentCode.WATER: 24,
    DepartmentCode.SOLID_WASTE: 24,
    DepartmentCode.ELECTRICAL: 12,
    DepartmentCode.PUBLIC_HEALTH: 72,
}


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


async def get_current_official(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    user = await get_current_user(credentials)
    if user.get("role") not in [r.value for r in UserRole]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return user


def save_data_url(data_url: str | None, prefix: str) -> str | None:
    if not data_url:
        return None
    if "," not in data_url:
        return data_url
    header, payload = data_url.split(",", 1)
    ext = "jpg" if "jpeg" in header or "jpg" in header else "png"
    filename = f"{prefix}-{uuid4()}.{ext}"
    path = UPLOAD_DIR / filename
    path.write_bytes(base64.b64decode(payload))
    return f"/uploads/{filename}"


def upload_to_supabase_storage(data_url: str, prefix: str, bucket: str = "tickets") -> str | None:
    """Upload base64 image to Supabase Storage."""
    if not data_url or "," not in data_url:
        return None
    
    try:
        header, payload = data_url.split(",", 1)
        ext = "jpg" if "jpeg" in header or "jpg" in header else "png"
        # Supabase only accepts image/jpeg / image/png — never "image/jpg".
        content_type = "image/jpeg" if ext == "jpg" else "image/png"
        filename = f"{prefix}-{uuid4()}.{ext}"
        file_bytes = base64.b64decode(payload)
        
        # Upload to Supabase Storage
        result = supabase.storage.from_(bucket).upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": content_type}
        )
        
        if result:
            public_url = supabase.storage.from_(bucket).get_public_url(filename)
            return public_url
    except Exception as e:
        print(f"Storage upload error: {e}")
    
    return None


def add_event(ticket_id: str, label: str, detail: str, actor_id: str | None = None):
    supabase.table("timeline_events").insert({
        "id": str(uuid4()),
        "ticket_id": ticket_id,
        "at": utcnow(),
        "label": label,
        "detail": detail,
        "actor_id": actor_id
    }).execute()


def fetch_timeline_events(ticket_ids: list[str]) -> dict[str, list[dict]]:
    """Fetch timelines for many tickets in one query (avoids the N+1 pattern)."""
    if not ticket_ids:
        return {}
    result = (
        supabase.table("timeline_events")
        .select("ticket_id,at,label,detail")
        .in_("ticket_id", ticket_ids)
        .order("at")
        .execute()
    )
    grouped: dict[str, list[dict]] = {}
    for event in result.data or []:
        grouped.setdefault(event["ticket_id"], []).append(
            {"at": event["at"], "label": event["label"], "detail": event["detail"]}
        )
    return grouped


def fetch_duplicate_numbers(rows: list[dict]) -> dict[str, str]:
    """Resolve every duplicate_of id to its master ticket number in one query."""
    duplicate_ids = {row["duplicate_of"] for row in rows if row.get("duplicate_of")}
    if not duplicate_ids:
        return {}
    result = supabase.table("tickets").select("id,ticket_number").in_("id", list(duplicate_ids)).execute()
    return {row["id"]: row["ticket_number"] for row in result.data or []}


TICKETS_CACHE_TTL = 5.0
_tickets_cache_payload: list[dict] | None = None
_tickets_cache_at: float = 0.0


def invalidate_tickets_cache() -> None:
    global _tickets_cache_payload, _tickets_cache_at
    _tickets_cache_payload = None
    _tickets_cache_at = 0.0


def serialize_ticket(
    row: dict,
    pin: str | None = None,
    events: list[dict] | None = None,
    duplicate_numbers: dict[str, str] | None = None,
) -> dict:
    if events is None:
        fetched = (
            supabase.table("timeline_events")
            .select("at,label,detail")
            .eq("ticket_id", row["id"])
            .order("at")
            .execute()
        )
        events = fetched.data or []
    duplicate_of = row.get("duplicate_of")
    if duplicate_of:
        if duplicate_numbers is not None:
            duplicate_of = duplicate_numbers.get(duplicate_of)
        else:
            master = supabase.table("tickets").select("ticket_number").eq("id", duplicate_of).limit(1).execute()
            duplicate_of = master.data[0]["ticket_number"] if master.data else None
    return {
        "id": row["id"],
        "ticketNumber": row["ticket_number"],
        "pin": pin,
        "description": row["description"],
        "category": row["category"],
        "departmentCode": row["department_code"],
        "priority": row["priority"],
        "status": row["status"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "address": row["address"],
        "beforePhoto": row.get("before_photo_url"),
        "afterPhoto": row.get("after_photo_url"),
        "closingNote": row.get("closing_notes"),
        "assignedTo": row.get("assigned_officer_id"),
        "duplicateOf": duplicate_of,
        "impactCount": row.get("impact_count", 1),
        "createdAt": row["created_at"],
        "slaDueAt": row["sla_deadline"],
        "resolvedAt": row.get("resolved_at"),
        "timeline": events,
    }


@app.get("/health")
async def health():
    return {"ok": True, "database": "supabase", "timestamp": utcnow()}


@app.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest):
    result = supabase.table("officials").select("*").eq("email", request.email).execute()
    
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = result.data[0]
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user["id"], "email": user["email"], "role": user["role"]})
    
    return LoginResponse(
        email=user["email"],
        name=user["full_name"],
        role=user["role"],
        token=token
    )


@app.post("/tickets", response_model=TicketResponse, status_code=201)
async def create_ticket(ticket: TicketCreate):
    # Triage
    triage_result = await groq_triage(ticket.description, ticket.category)
    
    dept_name, sla_hours = DEPARTMENTS[triage_result.department]
    
    # Duplicate detection
    duplicate_ticket = None
    if ticket.latitude and ticket.longitude:
        # Get active tickets in same department
        active_tickets = supabase.table("tickets").select("id,ticket_number,latitude,longitude,impact_count").eq(
            "department_code", triage_result.department.value
        ).neq("status", "RESOLVED").execute()
        
        for t in active_tickets.data or []:
            if t.get("latitude") and t.get("longitude"):
                # Simple distance check (Haversine approximation for small distances)
                lat_diff = abs(ticket.latitude - t["latitude"])
                lon_diff = abs(ticket.longitude - t["longitude"])
                # Rough 50m threshold (~0.0005 degrees)
                if lat_diff < 0.0005 and lon_diff < 0.0005:
                    duplicate_ticket = t
                    break
    
    created = datetime.now(timezone.utc)
    pin = str(uuid4().int)[:6]
    ticket_id = str(uuid4())
    number = f"CP-{created.year}-{uuid4().int % 1000000:06d}"
    
    # Upload before photo if provided
    before_photo_url = None
    if ticket.before_photo:
        before_photo_url = upload_to_supabase_storage(ticket.before_photo, "before")
    
    # Create ticket
    ticket_data = {
        "id": ticket_id,
        "ticket_number": number,
        "tracking_pin_hash": hash_value(pin),
        "description": ticket.description,
        "category": ticket.category,
        "department_code": triage_result.department.value,
        "priority": triage_result.priority.value,
        "status": TicketStatus.SUBMITTED.value,
        "latitude": ticket.latitude,
        "longitude": ticket.longitude,
        "address": ticket.address or "Location provided by citizen",
        "before_photo_url": before_photo_url,
        "sla_hours": sla_hours,
        "duplicate_of": duplicate_ticket["id"] if duplicate_ticket else None,
        "impact_count": 1,
        "created_at": created.isoformat(),
        "sla_deadline": (created + timedelta(hours=sla_hours)).isoformat(),
    }
    
    result = supabase.table("tickets").insert(ticket_data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create ticket")
    
    created_ticket = result.data[0]
    
    # Add timeline events
    add_event(ticket_id, "Submitted", "Anonymous complaint received.")
    add_event(ticket_id, "Triaged", f"Routed to {dept_name} with {triage_result.priority.value.lower()} priority.")
    
    if duplicate_ticket:
        add_event(ticket_id, "Duplicate Detected", f"Linked to existing ticket {duplicate_ticket['ticket_number']}")
        # Increment impact count on master ticket (int read-modify-write; no rpc needed)
        new_impact = int(duplicate_ticket.get("impact_count") or 1) + 1
        supabase.table("tickets").update({"impact_count": new_impact}).eq("id", duplicate_ticket["id"]).execute()

    invalidate_tickets_cache()
    return serialize_ticket(created_ticket, pin)


@app.get("/tickets", response_model=list[TicketResponse])
def list_tickets():
    # Public read: homepage, map, and post-submit refresh work without a session.
    # PINs are never included (serialize_ticket only sets pin when explicitly passed).
    global _tickets_cache_payload, _tickets_cache_at
    now = time.monotonic()
    if _tickets_cache_payload is not None and now - _tickets_cache_at < TICKETS_CACHE_TTL:
        return _tickets_cache_payload

    result = supabase.table("tickets").select("*").order("created_at", desc=True).execute()
    rows = result.data or []
    events_map = fetch_timeline_events([row["id"] for row in rows])
    duplicate_numbers = fetch_duplicate_numbers(rows)
    payload = [
        serialize_ticket(
            row,
            events=events_map.get(row["id"], []),
            duplicate_numbers=duplicate_numbers,
        )
        for row in rows
    ]
    _tickets_cache_payload = payload
    _tickets_cache_at = now
    return payload


@app.post("/tickets/track", response_model=TicketResponse)
def track_ticket(request: TrackRequest):
    ticket_number = request.ticket_number.upper()
    result = supabase.table("tickets").select("*").eq("ticket_number", ticket_number).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket = result.data[0]
    if ticket["tracking_pin_hash"] != hash_value(request.pin):
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    return serialize_ticket(ticket)


@app.patch("/tickets/{ticket_id}/{action}")
def ticket_action(ticket_id: str, action: str, request: TicketAction, user: dict = Depends(get_current_official)):
    ticket_result = supabase.table("tickets").select("*").eq("id", ticket_id).execute()
    
    if not ticket_result.data:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if action == "assign":
        supabase.table("tickets").update({
            "status": TicketStatus.ASSIGNED.value,
            "assigned_officer_id": user.get("sub"),
            "assigned_at": utcnow()
        }).eq("id", ticket_id).execute()
        add_event(ticket_id, "Assigned", f"Assigned to {user.get('name', 'Officer')}.", user.get("sub"))
        
    elif action == "start":
        supabase.table("tickets").update({
            "status": TicketStatus.IN_PROGRESS.value,
            "started_at": utcnow()
        }).eq("id", ticket_id).execute()
        add_event(ticket_id, "In Progress", "Field work has started.", user.get("sub"))
        
    elif action == "resolve":
        note = request.closing_note or ""
        if len(note) < 20:
            raise HTTPException(status_code=400, detail="Closing note must be at least 20 characters")
        if not request.after_photo:
            raise HTTPException(status_code=400, detail="After photo required")
        
        after_photo_url = upload_to_supabase_storage(request.after_photo, "after")
        if not after_photo_url:
            raise HTTPException(status_code=400, detail="Failed to upload after photo")
        
        supabase.table("tickets").update({
            "status": TicketStatus.RESOLVED.value,
            "after_photo_url": after_photo_url,
            "closing_notes": note,
            "resolved_at": utcnow()
        }).eq("id", ticket_id).execute()
        add_event(ticket_id, "Resolved", "Officer submitted after photo and closure note.", user.get("sub"))
        
    else:
        raise HTTPException(status_code=404, detail="Invalid action")
    
    invalidate_tickets_cache()
    updated = supabase.table("tickets").select("*").eq("id", ticket_id).execute()
    return serialize_ticket(updated.data[0])


@app.get("/dashboard/stats", response_model=DashboardStats)
def dashboard_stats(user: dict = Depends(get_current_official)):
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    # One round-trip instead of four sequential count queries.
    result = supabase.table("tickets").select("status,resolved_at").execute()
    rows = result.data or []
    open_count = 0
    in_progress = 0
    breached = 0
    resolved_today = 0
    for row in rows:
        status = row.get("status")
        if status in ("SUBMITTED", "ASSIGNED"):
            open_count += 1
        elif status == "IN_PROGRESS":
            in_progress += 1
        elif status == "BREACHED":
            breached += 1
        elif status == "RESOLVED" and (row.get("resolved_at") or "") >= today_start:
            resolved_today += 1

    return DashboardStats(
        open=open_count,
        in_progress=in_progress,
        breached=breached,
        resolved_today=resolved_today
    )


@app.get("/uploads/{filename}")
async def get_upload(filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.port)