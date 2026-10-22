import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { MapContainer, Marker, Popup, TileLayer, useMapEvents } from "react-leaflet";
import L from "leaflet";
import {
  AlertCircle,
  ArrowRight,
  BadgeCheck,
  Camera,
  CheckCircle2,
  Clock,
  Crosshair,
  Download,
  FileSearch,
  Filter,
  Lock,
  LogOut,
  MapPin,
  ShieldCheck,
  ShieldPlus,
  UserCheck,
} from "lucide-react";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import { useEffect, useMemo, useState } from "react";

type Role = "FIELD_OFFICER" | "SUPERVISOR" | "COMMISSIONER";
type Status = "SUBMITTED" | "ASSIGNED" | "IN_PROGRESS" | "RESOLUTION_SUBMITTED" | "RESOLVED" | "BREACHED" | "REOPENED";
type Priority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

type Department = {
  code: string;
  name: string;
  slaHours: number;
};

type TimelineEvent = {
  at: string;
  label: string;
  detail: string;
};

type Ticket = {
  id: string;
  ticketNumber: string;
  pin?: string | null;
  description: string;
  category: string;
  departmentCode: string;
  priority: Priority;
  status: Status;
  latitude: number;
  longitude: number;
  address: string;
  beforePhoto?: string;
  afterPhoto?: string;
  closingNote?: string;
  assignedTo?: string;
  duplicateOf?: string;
  impactCount: number;
  createdAt: string;
  slaDueAt: string;
  resolvedAt?: string;
  timeline: TimelineEvent[];
};

type Session = {
  email: string;
  name: string;
  role: Role;
};

const departments: Department[] = [
  { code: "ROADS", name: "Roads", slaHours: 48 },
  { code: "WATER", name: "Water", slaHours: 24 },
  { code: "SOLID_WASTE", name: "Solid Waste", slaHours: 24 },
  { code: "ELECTRICAL", name: "Electrical", slaHours: 12 },
  { code: "PUBLIC_HEALTH", name: "Public Health", slaHours: 36 },
];

const sessionKey = "civicpulse.session.v1";
const tokenKey = "civicpulse.token.v1";
const defaultCenter: [number, number] = [12.9716, 77.5946];
const API_BASE = import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE_URL || "https://civicpulse-api-qd7i.onrender.com");

const markerIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

function readSession(): Session | null {
  const raw = localStorage.getItem(sessionKey);
  return raw ? JSON.parse(raw) as Session : null;
}

function writeSession(session: Session | null, token?: string | null) {
  if (session) {
    localStorage.setItem(sessionKey, JSON.stringify(session));
    if (token) localStorage.setItem(tokenKey, token);
  } else {
    localStorage.removeItem(sessionKey);
    localStorage.removeItem(tokenKey);
  }
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem(tokenKey);
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(body.detail || "Request failed");
  }
  return response.json() as Promise<T>;
}

function App() {
  const [route, setRoute] = useState(location.hash.replace("#", "") || "/");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [session, setSession] = useState<Session | null>(readSession);

  async function refreshTickets() {
    setTickets(await api<Ticket[]>("/tickets"));
  }

  useEffect(() => {
    refreshTickets().catch(console.error);
  }, []);

  function navigate(next: string) {
    location.hash = next;
    setRoute(next);
  }

async function login(email: string, password: string) {
  const result = await api<{ email: string; name: string; role: Role; token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const session: Session = { email: result.email, name: result.name, role: result.role };
  setSession(session);
  writeSession(session, result.token);
  navigate("/admin/dashboard");
}

  function logout() {
    setSession(null);
    writeSession(null);
    navigate("/");
  }

  return (
    <div>
      <Header navigate={navigate} session={session} logout={logout} />
      {route === "/" && <HomePage navigate={navigate} tickets={tickets} />}
      {route === "/report" && <ReportPage refreshTickets={refreshTickets} navigate={navigate} />}
      {route === "/track" && <TrackPage />}
      {route.startsWith("/track/") && <TicketStatus ticket={tickets.find((ticket) => ticket.ticketNumber === route.split("/").at(-1))} navigate={navigate} />}
      {route === "/map" && <PublicMap tickets={tickets} navigate={navigate} />}
      {route === "/admin/login" && <AdminLogin login={login} />}
      {route === "/admin/dashboard" && <Dashboard session={session} tickets={tickets} refreshTickets={refreshTickets} navigate={navigate} />}
      {route.startsWith("/admin/tickets/") && <AdminTicket session={session} ticket={tickets.find((ticket) => ticket.id === route.split("/").at(-1))} refreshTickets={refreshTickets} navigate={navigate} />}
    </div>
  );
}

function Header({ navigate, session, logout }: { navigate: (route: string) => void; session: Session | null; logout: () => void }) {
  return (
    <header className="topbar">
      <button className="brand" onClick={() => navigate("/")}><ShieldCheck size={24} /> CivicPulse</button>
      <nav>
        <button onClick={() => navigate("/report")}><Camera size={18} /> Citizen Report</button>
        <button onClick={() => navigate("/track")}><FileSearch size={18} /> Track</button>
        <button onClick={() => navigate("/map")}><MapPin size={18} /> Issue Map</button>
        {session ? <button onClick={() => navigate("/admin/dashboard")}><ShieldPlus size={18} /> Municipal Portal</button> : null}
        {session ? <button onClick={logout}><LogOut size={18} /> Logout</button> : <button onClick={() => navigate("/admin/login")}><Lock size={18} /> Municipal Login</button>}
      </nav>
    </header>
  );
}

function HomePage({ navigate, tickets }: { navigate: (route: string) => void; tickets: Ticket[] }) {
  const open = tickets.filter((ticket) => ticket.status !== "RESOLVED").length;
  const resolved = tickets.filter((ticket) => ticket.status === "RESOLVED").length;
  return (
    <main className="homeShell">
      <section className="hero">
        <div className="heroCopy">
          <p className="eyebrow">Unified civic service desk</p>
          <h1>Anonymous citizen reports and municipal action in one product.</h1>
          <p>Residents can report issues without an account. Municipal teams can triage, assign, resolve, and publish proof from the same local website.</p>
          <div className="actions">
            <button className="primary" onClick={() => navigate("/report")}>Report an Issue <ArrowRight size={18} /></button>
            <button className="secondary" onClick={() => navigate("/admin/login")}><Lock size={18} /> Municipal Portal</button>
          </div>
        </div>
        <aside className="statsPanel" aria-label="Local ticket summary">
          <Metric label="Open tickets" value={open} />
          <Metric label="Resolved tickets" value={resolved} />
          <Metric label="Active departments" value={departments.length} />
        </aside>
      </section>
      <section className="portalGrid" aria-label="CivicPulse portals">
        <button className="portalTile citizenTile" onClick={() => navigate("/report")}>
          <Camera size={28} />
          <span>Citizen Portal</span>
          <strong>Report anonymously</strong>
          <small>Submit issue, location, before photo, and receive a printable ticket receipt.</small>
        </button>
        <button className="portalTile" onClick={() => navigate("/track")}>
          <FileSearch size={28} />
          <span>Public Tracking</span>
          <strong>Check ticket progress</strong>
          <small>Use ticket number and PIN to view public timeline and resolution proof.</small>
        </button>
        <button className="portalTile municipalTile" onClick={() => navigate("/admin/login")}>
          <ShieldPlus size={28} />
          <span>Municipal Portal</span>
          <strong>Operate the SLA workflow</strong>
          <small>Login as officials, assign work, update status, and close with evidence.</small>
        </button>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="metric"><strong>{value}</strong><span>{label}</span></div>;
}

function ReportPage({ refreshTickets, navigate }: { refreshTickets: () => Promise<void>; navigate: (route: string) => void }) {
  const [created, setCreated] = useState<Ticket | null>(null);
  const [error, setError] = useState("");
  const [locationStatus, setLocationStatus] = useState("Fetching your location...");
  const [position, setPosition] = useState<[number, number]>(defaultCenter);

  useEffect(() => {
    fetchCurrentLocation(true);
  }, []);

  function fetchCurrentLocation(automatic = false) {
    if (!navigator.geolocation) {
      setLocationStatus("Location is not supported in this browser.");
      return;
    }
    setLocationStatus(automatic ? "Requesting location permission..." : "Waiting for location permission...");
    navigator.geolocation.getCurrentPosition(
      (result) => {
        const next: [number, number] = [Number(result.coords.latitude.toFixed(6)), Number(result.coords.longitude.toFixed(6))];
        setPosition(next);
        setLocationStatus(`Latitude and longitude fetched automatically with ${Math.round(result.coords.accuracy)}m accuracy.`);
      },
      (geoError) => setLocationStatus(`${geoError.message || "Location permission was denied."} You can still type coordinates or drag the marker.`),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 },
    );
  }

  async function submit(formData: FormData) {
    const description = String(formData.get("description") || "").trim();
    if (description.length < 12) return setError("Please describe the issue in at least 12 characters.");
    const category = String(formData.get("category") || "General");
    const latitude = position[0];
    const longitude = position[1];
    const address = String(formData.get("address") || "Location provided by citizen");
    const photo = formData.get("photo") as File;
    const beforePhoto = photo?.size ? await fileToDataUrl(photo) : undefined;
    try {
      const createdTicket = await api<Ticket>("/tickets", {
        method: "POST",
        body: JSON.stringify({
          description,
          category,
          latitude,
          longitude,
          address,
          before_photo: beforePhoto,
        }),
      });
      await refreshTickets();
      setCreated(createdTicket);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Ticket creation failed.");
    }
  }

  if (created) return (
    <main className="page narrow">
      <div className="successBlock">
        <BadgeCheck size={34} />
        <h1>Ticket created</h1>
        <p>Save these details. The PIN is shown only in this local receipt.</p>
        <div className="printArea">
          <div className="printHeader"><ShieldCheck size={24} /><strong>CivicPulse Citizen Receipt</strong></div>
          <div className="receipt"><span>Ticket</span><strong>{created.ticketNumber}</strong><span>PIN</span><strong>{created.pin}</strong><span>Status</span><strong>{created.status}</strong><span>SLA due</span><strong>{new Date(created.slaDueAt).toLocaleString()}</strong></div>
        </div>
        {created.duplicateOf && <p className="notice">Possible duplicate of {created.duplicateOf}. Your submission was still preserved.</p>}
        <div className="actions">
          <button className="primary" onClick={() => navigate(`/track/${created.ticketNumber}`)}>Open Tracking Page</button>
          <button className="secondary" onClick={() => window.print()}><Download size={18} /> Print Receipt</button>
        </div>
      </div>
    </main>
  );

  return (
    <main className="page">
      <h1>Report an issue</h1>
      <form className="formGrid" action={submit}>
        <label className="wide">Description<textarea name="description" required placeholder="Describe the issue, landmark, and public impact." /></label>
        <label>Category<select name="category"><option>Road damage</option><option>Water leakage</option><option>Garbage</option><option>Street light</option><option>Public health</option></select></label>
        <label>Before photo<input name="photo" type="file" accept="image/*" /></label>
        <label>Latitude<input value={position[0]} type="number" step="0.000001" onChange={(event) => setPosition([Number(event.target.value), position[1]])} /></label>
        <label>Longitude<input value={position[1]} type="number" step="0.000001" onChange={(event) => setPosition([position[0], Number(event.target.value)])} /></label>
        <label className="wide">Address or landmark<input name="address" defaultValue="MG Road junction" /></label>
        <div className="wide mapField">
          <div className="mapToolbar">
            <span><MapPin size={17} /> Complaint location</span>
            <button type="button" className="secondary" onClick={() => fetchCurrentLocation()}><Crosshair size={18} /> Refresh location</button>
          </div>
          <LocationPicker position={position} setPosition={setPosition} />
          <p className="hint">{locationStatus}</p>
        </div>
        {error && <p className="error wide">{error}</p>}
        <button className="primary wide" type="submit">Submit Anonymous Report</button>
      </form>
    </main>
  );
}

function LocationPicker({ position, setPosition }: { position: [number, number]; setPosition: (position: [number, number]) => void }) {
  function ClickHandler() {
    useMapEvents({
      click(event) {
        setPosition([Number(event.latlng.lat.toFixed(6)), Number(event.latlng.lng.toFixed(6))]);
      },
    });
    return null;
  }

  return (
    <MapContainer className="miniMap" center={position} zoom={15} scrollWheelZoom={false}>
      <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <ClickHandler />
      <Marker
        draggable
        icon={markerIcon}
        position={position}
        eventHandlers={{
          dragend: (event) => {
            const next = event.target.getLatLng();
            setPosition([Number(next.lat.toFixed(6)), Number(next.lng.toFixed(6))]);
          },
        }}
      >
        <Popup>Complaint location</Popup>
      </Marker>
    </MapContainer>
  );
}

function PublicMap({ tickets, navigate }: { tickets: Ticket[]; navigate: (route: string) => void }) {
  const center = tickets[0] ? [tickets[0].latitude, tickets[0].longitude] as [number, number] : defaultCenter;
  return (
    <main className="page">
      <div className="sectionHeader">
        <div><p className="eyebrow">Public issue map</p><h1>Reported civic issues</h1></div>
        <button className="primary" onClick={() => navigate("/report")}><Camera size={18} /> Report Issue</button>
      </div>
      <MapContainer className="publicMap" center={center} zoom={13} scrollWheelZoom>
        <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {tickets.map((ticket) => (
          <Marker key={ticket.id} icon={markerIcon} position={[ticket.latitude, ticket.longitude]}>
            <Popup>
              <strong>{ticket.ticketNumber}</strong><br />
              {ticket.category}<br />
              {ticket.status.replace("_", " ")}<br />
              <button className="popupButton" onClick={() => navigate(`/track/${ticket.ticketNumber}`)}>Open tracking</button>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </main>
  );
}

function TrackPage() {
  const [error, setError] = useState("");
  const [tracked, setTracked] = useState<Ticket | null>(null);
  async function submit(formData: FormData) {
    const ticketNumberValue = String(formData.get("ticket") || "").trim().toUpperCase();
    const pin = String(formData.get("pin") || "").trim();
    try {
      const ticket = await api<Ticket>("/tickets/track", {
        method: "POST",
        body: JSON.stringify({ ticket_number: ticketNumberValue, pin }),
      });
      setTracked(ticket);
      setError("");
    } catch {
      setError("No ticket found for that ticket number and PIN.");
    }
  }
  if (tracked) return <main className="page"><TicketView ticket={tracked} publicView /></main>;
  return (
    <main className="page narrow">
      <h1>Track a ticket</h1>
      <form className="stack" action={submit}>
        <label>Ticket number<input name="ticket" placeholder="CP-2026-123456" /></label>
        <label>PIN<input name="pin" placeholder="6 digit PIN" /></label>
        {error && <p className="error">{error}</p>}
        <button className="primary" type="submit">View Status</button>
      </form>
    </main>
  );
}

function TicketStatus({ ticket, navigate }: { ticket?: Ticket; navigate: (route: string) => void }) {
  if (!ticket) return <main className="page narrow"><h1>Ticket not found</h1><button onClick={() => navigate("/track")}>Track another ticket</button></main>;
  return <TicketView ticket={ticket} publicView />;
}

function AdminLogin({ login }: { login: (email: string, password: string) => Promise<void> }) {
  const [error, setError] = useState("");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const email = String(formData.get("email") || "").trim();
    const password = String(formData.get("password") || "");
    try {
      await login(email, password);
      setError("");
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : "Login failed. Check your credentials.");
    }
  }
  return (
    <main className="page narrow">
      <h1>Official login</h1>
      <form className="stack" onSubmit={submit}>
        <label>Email<input name="email" defaultValue="supervisor@civicpulse.local" /></label>
        <label>Password<input name="password" type="password" defaultValue="password" /></label>
        {error && <p className="error">{error}</p>}
        <button className="primary" type="submit">Sign In</button>
      </form>
      <p className="hint">Demo: officer, supervisor, or commissioner at civicpulse.local with password "password".</p>
    </main>
  );
}

function Dashboard({ session, tickets, refreshTickets, navigate }: { session: Session | null; tickets: Ticket[]; refreshTickets: () => Promise<void>; navigate: (route: string) => void }) {
  const [filter, setFilter] = useState("ALL");
  const visible = useMemo(() => tickets.filter((ticket) => filter === "ALL" || ticket.status === filter), [tickets, filter]);
  if (!session) return <main className="page narrow"><h1>Authentication required</h1><button onClick={() => navigate("/admin/login")}>Go to Login</button></main>;
  async function seedSample() {
    await api<Ticket>("/tickets", {
      method: "POST",
      body: JSON.stringify({
      description: "Large pothole near bus stop causing traffic slowdown and unsafe two-wheeler movement.",
      category: "Road damage",
      latitude: 12.9716,
      longitude: 77.5946,
      address: "MG Road bus stop",
    }),
  });
    await refreshTickets();
  }
  return (
    <main className="page">
      <div className="sectionHeader">
        <div><p className="eyebrow">{session.role.replace("_", " ")}</p><h1>Officer dashboard</h1></div>
        <button className="secondary" onClick={seedSample}>Add Sample Ticket</button>
      </div>
      <div className="toolbar"><Filter size={18} /><select value={filter} onChange={(event) => setFilter(event.target.value)}><option>ALL</option><option>SUBMITTED</option><option>ASSIGNED</option><option>IN_PROGRESS</option><option>RESOLVED</option></select></div>
      <div className="ticketList">
        {visible.map((ticket) => <button className="ticketRow" key={ticket.id} onClick={() => navigate(`/admin/tickets/${ticket.id}`)}>
          <span><strong>{ticket.ticketNumber}</strong><small>{ticket.description}</small></span>
          <StatusBadge status={ticket.status} />
          <span>{ticket.priority}</span>
          <span>{departments.find((item) => item.code === ticket.departmentCode)?.name}</span>
          <span><Clock size={16} /> {new Date(ticket.slaDueAt).toLocaleString()}</span>
        </button>)}
        {!visible.length && <p className="empty">No tickets yet. Submit one as a citizen or add a sample ticket.</p>}
      </div>
    </main>
  );
}

function AdminTicket({ session, ticket, refreshTickets, navigate }: { session: Session | null; ticket?: Ticket; refreshTickets: () => Promise<void>; navigate: (route: string) => void }) {
  const [error, setError] = useState("");
  if (!session) return <main className="page narrow"><h1>Authentication required</h1><button onClick={() => navigate("/admin/login")}>Go to Login</button></main>;
  if (!ticket) return <main className="page narrow"><h1>Ticket not found</h1></main>;
  const currentTicket = ticket;
  async function update(action: "assign" | "start") {
    await api<Ticket>(`/tickets/${currentTicket.id}/${action}`, { method: "PATCH", body: JSON.stringify({}) });
    await refreshTickets();
  }
  async function resolve(formData: FormData) {
    const closingNote = String(formData.get("closingNote") || "").trim();
    const photo = formData.get("afterPhoto") as File;
    if (closingNote.length < 20) return setError("Closing note must be at least 20 characters.");
    if (!photo?.size) return setError("After photo is required.");
    try {
      await api<Ticket>(`/tickets/${currentTicket.id}/resolve`, {
        method: "PATCH",
        body: JSON.stringify({ closing_note: closingNote, after_photo: await fileToDataUrl(photo) }),
      });
      await refreshTickets();
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Resolution failed.");
    }
  }
  return (
    <main className="page detailGrid">
      <section>
        <button className="textButton" onClick={() => navigate("/admin/dashboard")}>Back to dashboard</button>
        <TicketView ticket={ticket} />
      </section>
      <aside className="workPanel">
        <h2>Actions</h2>
        <button onClick={() => update("assign")}><UserCheck size={18} /> Assign to me</button>
        <button onClick={() => update("start")}><Clock size={18} /> Mark in progress</button>
        <form className="stack" action={resolve}>
          <label>After photo<input name="afterPhoto" type="file" accept="image/*" /></label>
          <label>Closing note<textarea name="closingNote" placeholder="Describe what was fixed and verified." /></label>
          {error && <p className="error">{error}</p>}
          <button className="primary" type="submit"><CheckCircle2 size={18} /> Resolve Ticket</button>
        </form>
      </aside>
    </main>
  );
}

function TicketView({ ticket, publicView = false }: { ticket: Ticket; publicView?: boolean }) {
  return (
    <article className="ticketDetail">
      <div className="printControls"><button className="secondary" onClick={() => window.print()}><Download size={18} /> Print Ticket</button></div>
      <div className="printArea">
      <div className="sectionHeader">
        <div><p className="eyebrow">{ticket.ticketNumber}</p><h1>{ticket.category}</h1></div>
        <StatusBadge status={ticket.status} />
      </div>
      <p>{ticket.description}</p>
      <div className="facts">
        <span><MapPin size={16} /> {ticket.address}</span>
        <span><AlertCircle size={16} /> {ticket.priority}</span>
        <span><Clock size={16} /> SLA {new Date(ticket.slaDueAt).toLocaleString()}</span>
      </div>
      <div className="photoGrid">
        <Photo title="Before" src={ticket.beforePhoto} />
        <Photo title="After" src={ticket.afterPhoto} />
      </div>
      {ticket.closingNote && <p className="notice"><strong>Closing note:</strong> {ticket.closingNote}</p>}
      {!publicView && ticket.pin && <p className="hint">Citizen PIN: {ticket.pin}</p>}
      <h2>Timeline</h2>
      <ol className="timeline">{ticket.timeline.map((event) => <li key={`${event.at}-${event.label}`}><strong>{event.label}</strong><span>{event.detail}</span><time>{new Date(event.at).toLocaleString()}</time></li>)}</ol>
      </div>
    </article>
  );
}

function Photo({ title, src }: { title: string; src?: string }) {
  return <figure className="photo">{src ? <img src={src} alt={`${title} proof`} /> : <div>{title} photo pending</div>}<figcaption>{title}</figcaption></figure>;
}

function StatusBadge({ status }: { status: Status }) {
  return <span className={`status ${status.toLowerCase()}`}>{status.replace("_", " ")}</span>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
