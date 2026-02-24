import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, createApiClient, type IntakeRequest, type Ticket, type TicketStatus } from "./api";
import "./App.css";

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";
const DEFAULT_API_KEY = import.meta.env.VITE_API_KEY ?? "";
const DEFAULT_USER_ROLE = import.meta.env.VITE_USER_ROLE ?? "operator";
const DEFAULT_ENFORCE_AUTH = (import.meta.env.VITE_ENFORCE_AUTH ?? "false") === "true";
const DEFAULT_WEBHOOK_URL =
  import.meta.env.VITE_WEBHOOK_URL ?? "http://localhost:5678/webhook/ticket-intake";
const DEFAULT_INTAKE_MODE = import.meta.env.VITE_INTAKE_MODE ?? "webhook";
const EMAIL_HISTORY_KEY = "techops.email_history";
const AUTH_TOKEN_KEY = "techops.auth.token";
const AUTH_USER_KEY = "techops.auth.user";

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}

function isValidEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function loadEmailHistory(): string[] {
  try {
    const raw = window.localStorage.getItem(EMAIL_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .map((item) => String(item).trim().toLowerCase())
      .filter((item) => isValidEmail(item));
  } catch {
    return [];
  }
}

function persistEmailHistory(emails: string[]) {
  window.localStorage.setItem(EMAIL_HISTORY_KEY, JSON.stringify(emails));
}

function loadAuthToken(): string {
  return window.localStorage.getItem(AUTH_TOKEN_KEY) ?? "";
}

function loadAuthUser(): { email: string; full_name: string; role: string; tenant_id: string } | null {
  try {
    const raw = window.localStorage.getItem(AUTH_USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as { email: string; full_name: string; role: string; tenant_id: string };
  } catch {
    return null;
  }
}

function persistAuth(token: string, user: { email: string; full_name: string; role: string; tenant_id: string }) {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
  window.localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
}

function clearAuth() {
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem(AUTH_USER_KEY);
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return `${error.message} (status ${error.status})`;
  if (error instanceof Error) return error.message;
  return "Unknown error";
}

function App() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [apiKey, setApiKey] = useState(DEFAULT_API_KEY);
  const [userRole, setUserRole] = useState(DEFAULT_USER_ROLE);
  const [enforceAuth] = useState(DEFAULT_ENFORCE_AUTH);
  const [accessToken, setAccessToken] = useState(() => loadAuthToken());
  const [authUser, setAuthUser] = useState(() => loadAuthUser());
  const [loginEmail, setLoginEmail] = useState("operator@example.com");
  const [loginPassword, setLoginPassword] = useState("ChangeMe123!");
  const [loginError, setLoginError] = useState("");
  const [webhookUrl, setWebhookUrl] = useState(DEFAULT_WEBHOOK_URL);
  const [intakeMode, setIntakeMode] = useState(DEFAULT_INTAKE_MODE);
  const [tenantId, setTenantId] = useState(() => loadAuthUser()?.tenant_id ?? "demo");
  const [statusFilter, setStatusFilter] = useState("OPEN");
  const [queueMode, setQueueMode] = useState("ALL");
  const [myAssigneeEmail, setMyAssigneeEmail] = useState("");
  const [selectedTicketId, setSelectedTicketId] = useState<string>("");
  const [searchText, setSearchText] = useState("");
  const [createError, setCreateError] = useState("");
  const [assignError, setAssignError] = useState("");
  const [statusError, setStatusError] = useState("");
  const [noteError, setNoteError] = useState("");
  const [notificationEmail, setNotificationEmail] = useState("");
  const [assigneeName, setAssigneeName] = useState("");
  const [assigneeEmail, setAssigneeEmail] = useState("");
  const [nextStatus, setNextStatus] = useState<TicketStatus>("OPEN");
  const [noteText, setNoteText] = useState("");
  const [customEmailHistory, setCustomEmailHistory] = useState<string[]>(() => loadEmailHistory());
  const [createForm, setCreateForm] = useState({
    requesterName: "",
    requesterEmail: "",
    subject: "",
    descriptionRaw: "",
    priority: "P3",
    machineLine: "",
    machineStation: "",
    machineSerial: "",
  });

  const queryClient = useQueryClient();
  const api = useMemo(
    () => createApiClient({ baseUrl, apiKey, webhookUrl, userRole, accessToken }),
    [baseUrl, apiKey, webhookUrl, userRole, accessToken],
  );

  const loginMutation = useMutation({
    mutationFn: (args: { email: string; password: string }) => api.login(args.email, args.password),
    onSuccess: (result) => {
      setLoginError("");
      setAccessToken(result.access_token);
      setAuthUser(result.user);
      setUserRole(result.user.role);
      setTenantId(result.user.tenant_id || "demo");
      persistAuth(result.access_token, result.user);
    },
    onError: (error) => setLoginError(getErrorMessage(error)),
  });

  const meQuery = useQuery({
    queryKey: ["me", baseUrl, accessToken],
    queryFn: () => api.me(),
    enabled: Boolean(accessToken),
    retry: false,
  });

  const health = useQuery({
    queryKey: ["health", baseUrl],
    queryFn: api.health,
  });

  const ready = useQuery({
    queryKey: ["ready", baseUrl],
    queryFn: api.ready,
  });

  const tickets = useQuery({
    queryKey: [
      "tickets",
      baseUrl,
      apiKey,
      accessToken,
      userRole,
      tenantId,
      statusFilter,
      queueMode,
      myAssigneeEmail,
    ],
    queryFn: () =>
      api.listTickets(tenantId, statusFilter, {
        assigneeEmail: queueMode === "MY" ? myAssigneeEmail : "",
        onlyUnassigned: queueMode === "UNASSIGNED",
        slaState:
          queueMode === "AT_RISK" || queueMode === "BREACHED"
            ? (queueMode as "AT_RISK" | "BREACHED")
            : "ALL",
      }),
    enabled: !enforceAuth || Boolean(accessToken),
  });

  const queueSummary = useQuery({
    queryKey: ["queue-summary", baseUrl, apiKey, accessToken, userRole, tenantId, myAssigneeEmail],
    queryFn: () => api.getQueueSummary(tenantId, myAssigneeEmail),
    enabled: !enforceAuth || Boolean(accessToken),
  });

  const selectedTicket = useQuery({
    queryKey: ["ticket", baseUrl, apiKey, accessToken, userRole, selectedTicketId],
    queryFn: () => api.getTicket(selectedTicketId),
    enabled: Boolean(selectedTicketId) && (!enforceAuth || Boolean(accessToken)),
  });

  const selectedEvents = useQuery({
    queryKey: ["events", baseUrl, apiKey, accessToken, userRole, selectedTicketId],
    queryFn: () => api.getTicketEvents(selectedTicketId),
    enabled: Boolean(selectedTicketId) && (!enforceAuth || Boolean(accessToken)),
  });

  const tenantRoute = useQuery({
    queryKey: ["tenant-route", baseUrl, apiKey, accessToken, userRole, tenantId],
    queryFn: () => api.getTenantRoute(tenantId),
    enabled: !enforceAuth || Boolean(accessToken),
  });

  const tenantEmailHistory = useQuery({
    queryKey: ["tenant-email-history", baseUrl, apiKey, accessToken, userRole, tenantId],
    queryFn: () => api.getTenantEmailHistory(tenantId, 100),
    enabled: !enforceAuth || Boolean(accessToken),
  });

  const emailHistory = useMemo(() => {
    const fromApi = (tenantEmailHistory.data ?? []).map((item) => item.email.toLowerCase());
    return Array.from(new Set([...fromApi, ...customEmailHistory])).filter((item) =>
      isValidEmail(item),
    );
  }, [tenantEmailHistory.data, customEmailHistory]);

  const effectiveNotificationEmail =
    notificationEmail.trim().toLowerCase() || (tenantRoute.data?.to_emails?.[0] ?? "").toLowerCase();

  const closeMutation = useMutation({
    mutationFn: (ticketId: string) => api.closeTicket(ticketId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      queryClient.invalidateQueries({ queryKey: ["ticket"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });

  const assignMutation = useMutation({
    mutationFn: (args: { ticketId: string; assigneeName: string; assigneeEmail: string }) =>
      api.assignTicket(args.ticketId, args.assigneeName, args.assigneeEmail),
    onSuccess: () => {
      setAssignError("");
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      queryClient.invalidateQueries({ queryKey: ["ticket"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
    onError: (error) => setAssignError(getErrorMessage(error)),
  });

  const statusMutation = useMutation({
    mutationFn: (args: { ticketId: string; status: TicketStatus }) =>
      api.updateTicketStatus(args.ticketId, args.status),
    onSuccess: () => {
      setStatusError("");
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      queryClient.invalidateQueries({ queryKey: ["ticket"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
    onError: (error) => setStatusError(getErrorMessage(error)),
  });

  const noteMutation = useMutation({
    mutationFn: (args: { ticketId: string; message: string }) =>
      api.addTicketNote(args.ticketId, args.message),
    onSuccess: () => {
      setNoteError("");
      setNoteText("");
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
    onError: (error) => setNoteError(getErrorMessage(error)),
  });

  const createMutation = useMutation({
    mutationFn: async (payload: IntakeRequest) => {
      if (intakeMode === "webhook") {
        const target = effectiveNotificationEmail;
        if (!isValidEmail(target)) {
          throw new ApiError("Notification email is required and must be valid", 422);
        }
        const result = await api.createTicketViaWebhook(payload, target);
        return { ticket_id: result.ticket_id, status: result.status };
      }
      return api.createTicket(payload);
    },
    onSuccess: (result) => {
      setCreateError("");
      setSelectedTicketId(result.ticket_id);
      const normalizedRequester = createForm.requesterEmail.trim().toLowerCase();
      const normalizedTarget = effectiveNotificationEmail;
      setCustomEmailHistory((prev) => {
        const merged = Array.from(
          new Set([normalizedRequester, normalizedTarget, ...prev].filter((item) => isValidEmail(item))),
        );
        persistEmailHistory(merged);
        return merged;
      });
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      queryClient.invalidateQueries({ queryKey: ["ticket"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
      queryClient.invalidateQueries({ queryKey: ["tenant-email-history"] });
      setNotificationEmail("");
      setCreateForm({
        requesterName: "",
        requesterEmail: "",
        subject: "",
        descriptionRaw: "",
        priority: "P3",
        machineLine: "",
        machineStation: "",
        machineSerial: "",
      });
    },
    onError: (error) => {
      setCreateError(getErrorMessage(error));
    },
  });

  function submitCreateTicket(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!createForm.requesterName.trim() || !createForm.requesterEmail.trim()) {
      setCreateError("Requester name and email are required.");
      return;
    }
    if (!createForm.subject.trim() || !createForm.descriptionRaw.trim()) {
      setCreateError("Subject and description are required.");
      return;
    }
    if (intakeMode === "webhook" && !isValidEmail(effectiveNotificationEmail)) {
      setCreateError("Notification email is required for webhook mode.");
      return;
    }

    const payload: IntakeRequest = {
      tenant_id: tenantId.trim(),
      source: "ui",
      requester: {
        name: createForm.requesterName.trim(),
        email: createForm.requesterEmail.trim(),
      },
      subject: createForm.subject.trim(),
      description_raw: createForm.descriptionRaw.trim(),
      priority: createForm.priority as IntakeRequest["priority"],
      machine: {
        line: createForm.machineLine.trim(),
        station: createForm.machineStation.trim(),
        serial: createForm.machineSerial.trim(),
      },
    };

    createMutation.mutate(payload);
  }

  const rows = tickets.data ?? [];
  const filteredRows = rows.filter((ticket) => {
    const q = searchText.trim().toLowerCase();
    if (!q) return true;
    return (
      ticket.ticket_id.toLowerCase().includes(q) ||
      ticket.subject.toLowerCase().includes(q) ||
      ticket.requester_name.toLowerCase().includes(q)
    );
  });
  const openCount = rows.filter((t) => t.status === "OPEN").length;
  const closedCount = rows.filter((t) => t.status === "CLOSED").length;
  const isAuthMissing = enforceAuth && (!accessToken || meQuery.isError);
  const activeUser = meQuery.data ?? authUser;

  function handleLogout() {
    clearAuth();
    setAccessToken("");
    setAuthUser(null);
  }

  return (
    <div className="page-shell">
      <header className="topbar">
        <div>
          <h1>TechOps Copilot Console</h1>
          <p className="subtitle">Ticketing operations with automation visibility</p>
        </div>
        <div className="status-grid">
          {activeUser && (
            <div className="status-chip">
              User: {activeUser.email} ({activeUser.role})
            </div>
          )}
          {enforceAuth && accessToken && (
            <button className="secondary-button" onClick={handleLogout}>
              Logout
            </button>
          )}
          <div className={`status-chip ${health.data?.status === "ok" ? "ok" : "fail"}`}>
            API Health: {health.isLoading ? "..." : health.data?.status ?? "error"}
          </div>
          <div className={`status-chip ${ready.data?.status === "ready" ? "ok" : "fail"}`}>
            API Ready: {ready.isLoading ? "..." : ready.data?.status ?? "error"}
          </div>
        </div>
      </header>

      {isAuthMissing ? (
        <section className="card login-card">
          <h2>Sign In</h2>
          <p className="subtitle">Demo users: admin/operator/viewer @ example.com</p>
          <div className="create-form">
            <label className="full-row">
              Email
              <input value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)} />
            </label>
            <label className="full-row">
              Password
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
              />
            </label>
            <div className="create-actions full-row">
              <button
                type="button"
                onClick={() => loginMutation.mutate({ email: loginEmail.trim(), password: loginPassword })}
                disabled={loginMutation.isPending}
              >
                {loginMutation.isPending ? "Signing in..." : "Sign In"}
              </button>
              {loginError && <p className="error">{loginError}</p>}
            </div>
          </div>
        </section>
      ) : (
      <>
      <section className="control-panel">
        <label>
          API Base URL
          <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        </label>
        <label>
          API Key
          <input
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Optional unless API auth enabled"
          />
        </label>
        <label>
          Intake Mode
          <select value={intakeMode} onChange={(e) => setIntakeMode(e.target.value)}>
            <option value="webhook">webhook (recommended)</option>
            <option value="api">api (/intake direct)</option>
          </select>
        </label>
        <label>
          Webhook URL
          <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} />
        </label>
        <label>
          Tenant
          <input value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
        </label>
        <label>
          Status
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="OPEN">OPEN</option>
            <option value="IN_PROGRESS">IN_PROGRESS</option>
            <option value="WAITING">WAITING</option>
            <option value="RESOLVED">RESOLVED</option>
            <option value="CLOSED">CLOSED</option>
            <option value="ALL">ALL</option>
          </select>
        </label>
        <label>
          User Role
          <select
            value={userRole}
            onChange={(e) => setUserRole(e.target.value)}
            disabled={enforceAuth}
          >
            <option value="admin">admin</option>
            <option value="operator">operator</option>
            <option value="viewer">viewer</option>
          </select>
        </label>
        <label>
          Queue
          <select value={queueMode} onChange={(e) => setQueueMode(e.target.value)}>
            <option value="ALL">ALL</option>
            <option value="MY">MY_TICKETS</option>
            <option value="UNASSIGNED">UNASSIGNED</option>
            <option value="AT_RISK">AT_RISK</option>
            <option value="BREACHED">BREACHED</option>
          </select>
        </label>
        <label>
          My Assignee Email
          <input
            value={myAssigneeEmail}
            onChange={(e) => setMyAssigneeEmail(e.target.value)}
            placeholder="For MY queue"
          />
        </label>
        <label>
          Search
          <input
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="ID, subject, requester"
          />
        </label>
        <label>
          Actions
          <button
            className="secondary-button"
            onClick={() => queryClient.invalidateQueries({ queryKey: ["tickets"] })}
          >
            Refresh Inbox
          </button>
        </label>
      </section>

      <main className="content-grid">
        <section className="card create-card">
          <h2>Create Ticket</h2>
          <form className="create-form" onSubmit={submitCreateTicket}>
            <label className="full-row">
              Notification Email (destinatario notifica)
              <input
                type="email"
                list="notification-email-history"
                value={notificationEmail || (tenantRoute.data?.to_emails?.[0] ?? "")}
                onChange={(e) => setNotificationEmail(e.target.value)}
                placeholder="Select or type destination email"
              />
              <small className="hint">
                Questa email riceve la notifica. Il campo Requester Email identifica chi apre il ticket.
              </small>
              <datalist id="notification-email-history">
                {emailHistory.map((email) => (
                  <option key={email} value={email} />
                ))}
              </datalist>
            </label>
            <label>
              Requester Name
              <input
                value={createForm.requesterName}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, requesterName: e.target.value }))
                }
              />
            </label>
            <label>
              Requester Email (autore ticket)
              <input
                type="email"
                value={createForm.requesterEmail}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, requesterEmail: e.target.value }))
                }
              />
            </label>
            <label>
              Subject
              <input
                value={createForm.subject}
                onChange={(e) => setCreateForm((prev) => ({ ...prev, subject: e.target.value }))}
              />
            </label>
            <label>
              Priority
              <select
                value={createForm.priority}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, priority: e.target.value }))
                }
              >
                <option value="P1">P1</option>
                <option value="P2">P2</option>
                <option value="P3">P3</option>
                <option value="P4">P4</option>
              </select>
            </label>
            <label className="full-row">
              Description
              <textarea
                rows={3}
                value={createForm.descriptionRaw}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, descriptionRaw: e.target.value }))
                }
              />
            </label>
            <label>
              Machine Line
              <input
                value={createForm.machineLine}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, machineLine: e.target.value }))
                }
              />
            </label>
            <label>
              Machine Station
              <input
                value={createForm.machineStation}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, machineStation: e.target.value }))
                }
              />
            </label>
            <label>
              Machine Serial
              <input
                value={createForm.machineSerial}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, machineSerial: e.target.value }))
                }
              />
            </label>
            <div className="create-actions full-row">
              <button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create Ticket"}
              </button>
              {createError && <p className="error">{createError}</p>}
            </div>
          </form>
        </section>

        <section className="card list-card">
          <div className="list-head">
            <h2>Ticket Inbox</h2>
            <div className="kpi-row">
              <span>Open: {openCount}</span>
              <span>Closed: {closedCount}</span>
              <span>Total: {rows.length}</span>
              <span>Unassigned: {queueSummary.data?.unassigned_total ?? "-"}</span>
              <span>At Risk: {queueSummary.data?.at_risk_total ?? "-"}</span>
              <span>Breached: {queueSummary.data?.breached_total ?? "-"}</span>
            </div>
          </div>
          {tickets.isLoading && <p>Loading tickets...</p>}
          {tickets.isError && <p className="error">{getErrorMessage(tickets.error)}</p>}
          {!tickets.isLoading && !tickets.isError && (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>SLA</th>
                  <th>Assignee</th>
                  <th>Subject</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((ticket: Ticket) => (
                  <tr
                    key={ticket.ticket_id}
                    className={ticket.ticket_id === selectedTicketId ? "selected" : ""}
                    onClick={() => setSelectedTicketId(ticket.ticket_id)}
                  >
                    <td>{ticket.ticket_id}</td>
                    <td>{ticket.priority}</td>
                    <td>{ticket.status}</td>
                    <td>{ticket.sla_state}</td>
                    <td>{ticket.assignee_email || "-"}</td>
                    <td>{ticket.subject}</td>
                    <td>{formatDate(ticket.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="card detail-card">
          <h2>Ticket Detail</h2>
          {!selectedTicketId && <p>Select a ticket from the inbox.</p>}
          {selectedTicket.isError && <p className="error">{getErrorMessage(selectedTicket.error)}</p>}
          {selectedTicket.data && (
            <>
              <div className="detail-head">
                <div>
                  <strong>{selectedTicket.data.ticket_id}</strong>
                  <p>{selectedTicket.data.subject}</p>
                </div>
                <button
                  disabled={selectedTicket.data.status === "CLOSED" || closeMutation.isPending}
                  onClick={() => closeMutation.mutate(selectedTicket.data.ticket_id)}
                >
                  {selectedTicket.data.status === "CLOSED" ? "Closed" : "Close Ticket"}
                </button>
              </div>
              <div className="detail-meta">
                <p>Tenant: {selectedTicket.data.tenant_id}</p>
                <p>Status: {selectedTicket.data.status}</p>
                <p>Requester: {selectedTicket.data.requester_name}</p>
                <p>Email: {selectedTicket.data.requester_email}</p>
                <p>
                  Assignee: {selectedTicket.data.assignee_name || "-"} /{" "}
                  {selectedTicket.data.assignee_email || "-"}
                </p>
                <p>SLA Due: {selectedTicket.data.sla_due_at ? formatDate(selectedTicket.data.sla_due_at) : "-"}</p>
                <p>SLA State: {selectedTicket.data.sla_state}</p>
                <p>
                  Machine: {selectedTicket.data.machine_line}/{selectedTicket.data.machine_station}/
                  {selectedTicket.data.machine_serial}
                </p>
              </div>
              <div className="detail-actions">
                <h3>Assignment</h3>
                <div className="inline-form">
                  <input
                    placeholder="Assignee name"
                    value={assigneeName}
                    onChange={(e) => setAssigneeName(e.target.value)}
                  />
                  <input
                    type="email"
                    placeholder="Assignee email"
                    value={assigneeEmail}
                    onChange={(e) => setAssigneeEmail(e.target.value)}
                  />
                  <button
                    onClick={() =>
                      assignMutation.mutate({
                        ticketId: selectedTicket.data.ticket_id,
                        assigneeName: assigneeName.trim(),
                        assigneeEmail: assigneeEmail.trim(),
                      })
                    }
                    disabled={assignMutation.isPending}
                  >
                    {assignMutation.isPending ? "Saving..." : "Assign"}
                  </button>
                </div>
                {assignError && <p className="error">{assignError}</p>}
                <h3>Status</h3>
                <div className="inline-form">
                  <select
                    value={nextStatus}
                    onChange={(e) => setNextStatus(e.target.value as TicketStatus)}
                  >
                    <option value="OPEN">OPEN</option>
                    <option value="IN_PROGRESS">IN_PROGRESS</option>
                    <option value="WAITING">WAITING</option>
                    <option value="RESOLVED">RESOLVED</option>
                    <option value="CLOSED">CLOSED</option>
                  </select>
                  <button
                    onClick={() =>
                      statusMutation.mutate({
                        ticketId: selectedTicket.data.ticket_id,
                        status: nextStatus,
                      })
                    }
                    disabled={statusMutation.isPending}
                  >
                    {statusMutation.isPending ? "Updating..." : "Update Status"}
                  </button>
                </div>
                {statusError && <p className="error">{statusError}</p>}
                <h3>Add Note</h3>
                <div className="inline-form">
                  <input
                    placeholder="Write operational note"
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                  />
                  <button
                    onClick={() =>
                      noteMutation.mutate({
                        ticketId: selectedTicket.data.ticket_id,
                        message: noteText.trim(),
                      })
                    }
                    disabled={noteMutation.isPending || !noteText.trim()}
                  >
                    {noteMutation.isPending ? "Saving..." : "Add Note"}
                  </button>
                </div>
                {noteError && <p className="error">{noteError}</p>}
              </div>
              <h3>Timeline</h3>
              {selectedEvents.isLoading && <p>Loading timeline...</p>}
              {selectedEvents.isError && <p className="error">{getErrorMessage(selectedEvents.error)}</p>}
              <ul className="timeline">
                {(selectedEvents.data ?? []).map((event) => (
                  <li key={event.id}>
                    <div>
                      <strong>{event.event_type}</strong>
                      <span>{formatDate(event.created_at)}</span>
                    </div>
                    <p>{event.message || "-"}</p>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </main>
      </>
      )}
    </div>
  );
}

export default App;
