from enum import Enum

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class DepartmentCode(str, Enum):
    ROADS = "ROADS"
    WATER = "WATER"
    SOLID_WASTE = "SOLID_WASTE"
    ELECTRICAL = "ELECTRICAL"
    PUBLIC_HEALTH = "PUBLIC_HEALTH"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"
    CRITICAL = "CRITICAL"


class TicketStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLUTION_SUBMITTED = "RESOLUTION_SUBMITTED"
    RESOLVED = "RESOLVED"
    BREACHED = "BREACHED"
    REOPENED = "REOPENED"


class UserRole(str, Enum):
    FIELD_OFFICER = "FIELD_OFFICER"
    SUPERVISOR = "SUPERVISOR"
    COMMISSIONER = "COMMISSIONER"


class TicketCreate(BaseModel):
    description: str = Field(..., min_length=12)
    category: str = "General"
    latitude: float
    longitude: float
    address: str | None = None
    before_photo: str | None = None


class TicketResponse(BaseModel):
    model_config = ConfigDict(alias_generator=AliasGenerator(to_camel), populate_by_name=True)

    id: str
    ticket_number: str
    pin: str | None = None
    description: str
    category: str
    department_code: str
    priority: str
    status: str
    latitude: float
    longitude: float
    address: str
    before_photo: str | None = None
    after_photo: str | None = None
    closing_note: str | None = None
    assigned_to: str | None = None
    duplicate_of: str | None = None
    impact_count: int
    created_at: str
    sla_due_at: str
    resolved_at: str | None = None
    timeline: list[dict] = []


class TrackRequest(BaseModel):
    ticket_number: str
    pin: str


class LoginRequest(BaseModel):
    # Plain str: demo accounts use the reserved .local TLD, which EmailStr rejects.
    email: str
    password: str


class LoginResponse(BaseModel):
    email: str
    name: str
    role: str
    token: str


class TicketAction(BaseModel):
    # `action` lives in the URL path; body only carries optional fields.
    closing_note: str | None = None
    after_photo: str | None = None


class TriageResult(BaseModel):
    department: DepartmentCode
    subcategory: str
    priority: Priority
    summary: str
    urgency_score: int


class DashboardStats(BaseModel):
    open: int
    in_progress: int
    breached: int
    resolved_today: int