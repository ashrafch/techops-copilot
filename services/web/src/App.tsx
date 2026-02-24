import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createApiClient,
  type AgentActionRun,
  type AgentDecisionLog,
  type AgentMemorySuggestion,
  type AdminAuditLog,
  type AdminUser,
  type IntakeRequest,
  type Ticket,
  type TicketStatus,
} from "./api";
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
  const [showAdvancedCreate, setShowAdvancedCreate] = useState(false);
  const [assigneeName, setAssigneeName] = useState("");
  const [assigneeEmail, setAssigneeEmail] = useState("");
  const [nextStatus, setNextStatus] = useState<TicketStatus>("OPEN");
  const [noteText, setNoteText] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [activeView, setActiveView] = useState<"operations" | "kpi" | "admin">("operations");
  const [adminSection, setAdminSection] = useState<"users" | "routing" | "sla" | "automation" | "audit" | "technical">("users");
  const [showTechnicalPanel, setShowTechnicalPanel] = useState(false);
  const [adminError, setAdminError] = useState("");
  const [routeEmailsDraft, setRouteEmailsDraft] = useState("");
  const [slaP1, setSlaP1] = useState("");
  const [slaP2, setSlaP2] = useState("");
  const [slaP3, setSlaP3] = useState("");
  const [slaP4, setSlaP4] = useState("");
  const [automationWindow, setAutomationWindow] = useState("");
  const [automationAtRiskLead, setAutomationAtRiskLead] = useState("");
  const [automationAssignName, setAutomationAssignName] = useState("");
  const [automationAssignEmail, setAutomationAssignEmail] = useState("");
  const [automationWebhookUrl, setAutomationWebhookUrl] = useState("");
  const [automationWebhookToken, setAutomationWebhookToken] = useState("");
  const [slaMonitorResult, setSlaMonitorResult] = useState("");
  const [memoryScore, setMemoryScore] = useState("4");
  const [memoryNote, setMemoryNote] = useState("");
  const [agentError, setAgentError] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [newUserRole, setNewUserRole] = useState<"admin" | "operator" | "viewer">("operator");
  const [newUserPassword, setNewUserPassword] = useState("ChangeMe123!");
  const [newUserActive, setNewUserActive] = useState(true);
  const [passwordDraftByUserId, setPasswordDraftByUserId] = useState<Record<number, string>>({});
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
  const effectiveRole = meQuery.data?.role ?? authUser?.role ?? userRole;
  const isAdminUser = effectiveRole === "admin";
  const resolvedView = !isAdminUser && activeView === "admin" ? "operations" : activeView;

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
  const ticketMetrics = useQuery({
    queryKey: ["ticket-metrics", baseUrl, apiKey, accessToken, userRole, tenantId],
    queryFn: () => api.getTicketMetrics(tenantId),
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

  const tenantSlaPolicy = useQuery({
    queryKey: ["tenant-sla-policy", baseUrl, apiKey, accessToken, userRole, tenantId],
    queryFn: () => api.getTenantSlaPolicy(tenantId),
    enabled: isAdminUser && (!enforceAuth || Boolean(accessToken)),
  });
  const tenantAutomationPolicy = useQuery({
    queryKey: ["tenant-automation-policy", baseUrl, apiKey, accessToken, userRole, tenantId],
    queryFn: () => api.getTenantAutomationPolicy(tenantId),
    enabled: isAdminUser && (!enforceAuth || Boolean(accessToken)),
  });

  const adminUsers = useQuery({
    queryKey: ["admin-users", baseUrl, apiKey, accessToken, userRole, tenantId],
    queryFn: () => api.listAdminUsers(tenantId),
    enabled: isAdminUser && activeView === "admin" && (!enforceAuth || Boolean(accessToken)),
  });
  const adminAuditLogs = useQuery({
    queryKey: ["admin-audit-logs", baseUrl, apiKey, accessToken, userRole, tenantId],
    queryFn: () => api.listAdminAuditLogs(tenantId, 100),
    enabled: isAdminUser && activeView === "admin" && (!enforceAuth || Boolean(accessToken)),
  });
  const agentProactiveSummary = useQuery({
    queryKey: ["agent-proactive-summary", baseUrl, apiKey, accessToken, userRole, tenantId],
    queryFn: () => api.getAgentProactiveSummary(tenantId, 20),
    enabled: !enforceAuth || Boolean(accessToken),
  });
  const agentDecisionLogs = useQuery({
    queryKey: ["agent-decisions", baseUrl, apiKey, accessToken, userRole, tenantId],
    queryFn: () => api.listAgentDecisions(tenantId, 50),
    enabled: !enforceAuth || Boolean(accessToken),
  });
  const agentActionRuns = useQuery({
    queryKey: ["agent-actions", baseUrl, apiKey, accessToken, userRole, tenantId],
    queryFn: () => api.listAgentActions(tenantId, 50),
    enabled: !enforceAuth || Boolean(accessToken),
  });
  const normalizedMemoryEventType =
    (selectedTicket.data?.machine_station ?? "").trim() || "GENERIC_EVENT";
  const normalizedMemoryAssetId =
    (selectedTicket.data?.machine_serial ?? "").trim() || "UNKNOWN_ASSET";
  const agentMemorySuggestions = useQuery({
    queryKey: [
      "agent-memory-suggestions",
      baseUrl,
      apiKey,
      accessToken,
      userRole,
      tenantId,
      normalizedMemoryEventType,
      normalizedMemoryAssetId,
    ],
    queryFn: () =>
      api.listAgentMemorySuggestions(
        tenantId,
        normalizedMemoryEventType,
        normalizedMemoryAssetId,
        5,
      ),
    enabled: Boolean(selectedTicket.data?.ticket_id) && (!enforceAuth || Boolean(accessToken)),
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
      queryClient.invalidateQueries({ queryKey: ["queue-summary"] });
      queryClient.invalidateQueries({ queryKey: ["ticket-metrics"] });
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
      queryClient.invalidateQueries({ queryKey: ["queue-summary"] });
      queryClient.invalidateQueries({ queryKey: ["ticket-metrics"] });
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
      queryClient.invalidateQueries({ queryKey: ["queue-summary"] });
      queryClient.invalidateQueries({ queryKey: ["ticket-metrics"] });
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
      queryClient.invalidateQueries({ queryKey: ["queue-summary"] });
      queryClient.invalidateQueries({ queryKey: ["ticket-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["agent-proactive-summary"] });
      queryClient.invalidateQueries({ queryKey: ["agent-decisions"] });
      queryClient.invalidateQueries({ queryKey: ["agent-actions"] });
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

  const updateRouteMutation = useMutation({
    mutationFn: (toEmailsCsv: string) => {
      const toEmails = toEmailsCsv
        .split(",")
        .map((item) => item.trim().toLowerCase())
        .filter((item) => item.length > 0);
      return api.updateTenantRoute(tenantId, toEmails);
    },
    onSuccess: () => {
      setAdminError("");
      queryClient.invalidateQueries({ queryKey: ["tenant-route"] });
      queryClient.invalidateQueries({ queryKey: ["admin-audit-logs"] });
    },
    onError: (error) => setAdminError(getErrorMessage(error)),
  });

  const updateSlaMutation = useMutation({
    mutationFn: () =>
      api.updateTenantSlaPolicy(tenantId, {
        p1_minutes: Number(slaP1 || tenantSlaPolicy.data?.p1_minutes || 60),
        p2_minutes: Number(slaP2 || tenantSlaPolicy.data?.p2_minutes || 240),
        p3_minutes: Number(slaP3 || tenantSlaPolicy.data?.p3_minutes || 480),
        p4_minutes: Number(slaP4 || tenantSlaPolicy.data?.p4_minutes || 1440),
      }),
    onSuccess: () => {
      setAdminError("");
      queryClient.invalidateQueries({ queryKey: ["tenant-sla-policy"] });
      queryClient.invalidateQueries({ queryKey: ["admin-audit-logs"] });
    },
    onError: (error) => setAdminError(getErrorMessage(error)),
  });
  const updateAutomationPolicyMutation = useMutation({
    mutationFn: () =>
      api.updateTenantAutomationPolicy(tenantId, {
        correlation_window_minutes: Number(
          automationWindow || tenantAutomationPolicy.data?.correlation_window_minutes || 1440,
        ),
        at_risk_lead_minutes: Number(
          automationAtRiskLead || tenantAutomationPolicy.data?.at_risk_lead_minutes || 60,
        ),
        auto_assign_name: (automationAssignName || tenantAutomationPolicy.data?.auto_assign_name || "").trim(),
        auto_assign_email: (automationAssignEmail || tenantAutomationPolicy.data?.auto_assign_email || "").trim() || null,
        action_webhook_url: (automationWebhookUrl || tenantAutomationPolicy.data?.action_webhook_url || "").trim(),
        action_webhook_token: (automationWebhookToken || "").trim(),
      }),
    onSuccess: () => {
      setAdminError("");
      queryClient.invalidateQueries({ queryKey: ["tenant-automation-policy"] });
      queryClient.invalidateQueries({ queryKey: ["admin-audit-logs"] });
    },
    onError: (error) => setAdminError(getErrorMessage(error)),
  });
  const runSlaMonitorMutation = useMutation({
    mutationFn: () => api.runSlaMonitor(tenantId, 500),
    onSuccess: (result) => {
      setAdminError("");
      setSlaMonitorResult(
        `Scanned ${result.scanned} | AT_RISK ${result.at_risk_alerted} | BREACHED ${result.breached_alerted}`,
      );
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      queryClient.invalidateQueries({ queryKey: ["queue-summary"] });
      queryClient.invalidateQueries({ queryKey: ["ticket-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["agent-proactive-summary"] });
    },
    onError: (error) => setAdminError(getErrorMessage(error)),
  });
  const memoryFeedbackMutation = useMutation({
    mutationFn: () => {
      if (!selectedTicket.data) throw new ApiError("Select a ticket first", 422);
      return api.addAgentMemoryFeedback({
        tenant_id: selectedTicket.data.tenant_id,
        ticket_id: selectedTicket.data.ticket_id,
        event_type: normalizedMemoryEventType,
        asset_id: normalizedMemoryAssetId,
        outcome_score: Number(memoryScore),
        resolution_note: memoryNote.trim(),
      });
    },
    onSuccess: () => {
      setAgentError("");
      setMemoryNote("");
      queryClient.invalidateQueries({ queryKey: ["agent-memory-suggestions"] });
      queryClient.invalidateQueries({ queryKey: ["agent-decisions"] });
    },
    onError: (error) => setAgentError(getErrorMessage(error)),
  });

  const createAdminUserMutation = useMutation({
    mutationFn: () =>
      api.createAdminUser({
        email: newUserEmail.trim().toLowerCase(),
        full_name: newUserName.trim(),
        password: newUserPassword,
        role: newUserRole,
        tenant_id: tenantId,
        is_active: newUserActive,
      }),
    onSuccess: () => {
      setAdminError("");
      setNewUserEmail("");
      setNewUserName("");
      setNewUserPassword("ChangeMe123!");
      setNewUserRole("operator");
      setNewUserActive(true);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-audit-logs"] });
    },
    onError: (error) => setAdminError(getErrorMessage(error)),
  });

  const toggleUserActiveMutation = useMutation({
    mutationFn: (args: { id: number; isActive: boolean }) =>
      api.updateAdminUser(args.id, { is_active: args.isActive }),
    onSuccess: () => {
      setAdminError("");
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-audit-logs"] });
    },
    onError: (error) => setAdminError(getErrorMessage(error)),
  });

  const updateAdminPasswordMutation = useMutation({
    mutationFn: (args: { id: number; password: string }) => api.updateAdminUserPassword(args.id, args.password),
    onSuccess: (_, args) => {
      setAdminError("");
      setPasswordDraftByUserId((prev) => ({ ...prev, [args.id]: "" }));
      queryClient.invalidateQueries({ queryKey: ["admin-audit-logs"] });
    },
    onError: (error) => setAdminError(getErrorMessage(error)),
  });

  function openAdminSection(section: "users" | "routing" | "sla" | "automation" | "audit" | "technical") {
    setActiveView("admin");
    setAdminSection(section);
    setRouteEmailsDraft((tenantRoute.data?.to_emails ?? []).join(", "));
    setSlaP1(String(tenantSlaPolicy.data?.p1_minutes ?? 60));
    setSlaP2(String(tenantSlaPolicy.data?.p2_minutes ?? 240));
    setSlaP3(String(tenantSlaPolicy.data?.p3_minutes ?? 480));
    setSlaP4(String(tenantSlaPolicy.data?.p4_minutes ?? 1440));
    setAutomationWindow(String(tenantAutomationPolicy.data?.correlation_window_minutes ?? 1440));
    setAutomationAtRiskLead(String(tenantAutomationPolicy.data?.at_risk_lead_minutes ?? 60));
    setAutomationAssignName(tenantAutomationPolicy.data?.auto_assign_name ?? "");
    setAutomationAssignEmail(tenantAutomationPolicy.data?.auto_assign_email ?? "");
    setAutomationWebhookUrl(tenantAutomationPolicy.data?.action_webhook_url ?? "");
    setAutomationWebhookToken("");
    setSlaMonitorResult("");
    setAdminError("");
  }

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
  const totalRecords = filteredRows.length;
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const page = Math.min(currentPage, totalPages);
  const pageStart = (page - 1) * pageSize;
  const pagedRows = filteredRows.slice(pageStart, pageStart + pageSize);
  const viewTitle =
    resolvedView === "operations"
      ? "Centro Operativo"
      : resolvedView === "kpi"
        ? "Performance"
        : "Amministrazione";
  const viewSubtitle =
    resolvedView === "operations"
      ? "Gestisci ticket e priorita in un flusso unico, rapido e chiaro."
      : resolvedView === "kpi"
        ? "Controlla carico, rischi SLA e velocita di risoluzione."
        : "Configura utenti, regole e automazioni del tenant.";

  function handleLogout() {
    clearAuth();
    setAccessToken("");
    setAuthUser(null);
  }

  return (
    <div className="page-shell">
      <header className="topbar">
        <div className="topbar-main">
          <h1>TechOps Copilot Console</h1>
          <p className="subtitle">AI Agent per ticketing automatico, escalation SLA e controllo operativo.</p>
        </div>
        <div className="status-grid">
          {activeUser && (
            <div className="status-chip">
              Utente: {activeUser.full_name || activeUser.email} ({activeUser.role})
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
          <h2>Accedi</h2>
          <p className="subtitle">Utenti demo: admin/operator/viewer @ example.com</p>
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
                {loginMutation.isPending ? "Accesso..." : "Accedi"}
              </button>
              {loginError && <p className="error">{loginError}</p>}
            </div>
          </div>
        </section>
      ) : (
      <>
      <section className="view-switch">
        <button
          className={resolvedView === "operations" ? "view-button active" : "view-button"}
          onClick={() => setActiveView("operations")}
        >
          Operazioni
        </button>
        <button
          className={resolvedView === "kpi" ? "view-button active" : "view-button"}
          onClick={() => setActiveView("kpi")}
        >
          Performance
        </button>
        {isAdminUser && (
          <button
            className={resolvedView === "admin" ? "view-button active" : "view-button"}
            onClick={() => openAdminSection(adminSection)}
          >
            Admin
          </button>
        )}
      </section>
      <section className="card view-header">
        <h2>{viewTitle}</h2>
        <p className="subtitle">{viewSubtitle}</p>
      </section>

      {resolvedView !== "admin" && (
      <>
      <section className="quick-strip">
        <article className="card quick-card">
          <span>Ticket aperti</span>
          <strong>{queueSummary.data?.open_total ?? "-"}</strong>
        </article>
        <article className="card quick-card">
          <span>Previsione breach 2h</span>
          <strong>{agentProactiveSummary.data?.predicted_breach_2h ?? "-"}</strong>
        </article>
        <article className="card quick-card">
          <span>A rischio SLA</span>
          <strong>{queueSummary.data?.at_risk_total ?? "-"}</strong>
        </article>
        <article className="card quick-card">
          <span>Risoluzione media</span>
          <strong>{ticketMetrics.data?.avg_resolution_minutes ?? "-"} min</strong>
        </article>
      </section>

      <section className="control-panel">
        <label>
          Cliente (tenant)
          <input
            value={tenantId}
            onChange={(e) => {
              setTenantId(e.target.value);
              setCurrentPage(1);
            }}
            disabled={enforceAuth && !isAdminUser}
          />
        </label>
        <label>
          Stato ticket
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setCurrentPage(1);
            }}
          >
            <option value="OPEN">OPEN</option>
            <option value="IN_PROGRESS">IN_PROGRESS</option>
            <option value="WAITING">WAITING</option>
            <option value="RESOLVED">RESOLVED</option>
            <option value="CLOSED">CLOSED</option>
            <option value="ALL">ALL</option>
          </select>
        </label>
        <label>
          Coda
          <select
            value={queueMode}
            onChange={(e) => {
              setQueueMode(e.target.value);
              setCurrentPage(1);
            }}
          >
            <option value="ALL">ALL</option>
            <option value="MY">MY_TICKETS</option>
            <option value="UNASSIGNED">UNASSIGNED</option>
            <option value="AT_RISK">AT_RISK</option>
            <option value="BREACHED">BREACHED</option>
          </select>
        </label>
        <label>
          Email operatore
          <input
            value={myAssigneeEmail}
            onChange={(e) => {
              setMyAssigneeEmail(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="Usata per la coda MY_TICKETS"
          />
        </label>
        <label>
          Cerca
          <input
            value={searchText}
            onChange={(e) => {
              setSearchText(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="ID, oggetto, richiedente"
          />
        </label>
        <label>
          Ticket per pagina
          <select
            value={String(pageSize)}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setCurrentPage(1);
            }}
          >
            <option value="10">10</option>
            <option value="25">25</option>
            <option value="50">50</option>
            <option value="100">100</option>
          </select>
        </label>
        <label>
          Azioni
          <button
            className="secondary-button"
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ["tickets"] });
              queryClient.invalidateQueries({ queryKey: ["queue-summary"] });
              queryClient.invalidateQueries({ queryKey: ["ticket-metrics"] });
            }}
          >
            Refresh
          </button>
        </label>
      </section>

      {resolvedView === "operations" && (
      <main className="content-grid">
        <section className="card create-card">
          <h2>Nuovo Ticket</h2>
          <form className="create-form" onSubmit={submitCreateTicket}>
            <label className="full-row">
              Email destinatario notifica
              <input
                type="email"
                list="notification-email-history"
                value={notificationEmail || (tenantRoute.data?.to_emails?.[0] ?? "")}
                onChange={(e) => setNotificationEmail(e.target.value)}
                placeholder="Seleziona o inserisci una email"
              />
              <small className="hint">
                Questa email riceve la notifica; il richiedente resta separato.
              </small>
              <datalist id="notification-email-history">
                {emailHistory.map((email) => (
                  <option key={email} value={email} />
                ))}
              </datalist>
            </label>
            <label>
              Nome richiedente
              <input
                value={createForm.requesterName}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, requesterName: e.target.value }))
                }
              />
            </label>
            <label>
              Email richiedente
              <input
                type="email"
                value={createForm.requesterEmail}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, requesterEmail: e.target.value }))
                }
              />
            </label>
            <label>
              Oggetto
              <input
                value={createForm.subject}
                onChange={(e) => setCreateForm((prev) => ({ ...prev, subject: e.target.value }))}
              />
            </label>
            <label>
              Priorita
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
              Descrizione
              <textarea
                rows={3}
                value={createForm.descriptionRaw}
                onChange={(e) =>
                  setCreateForm((prev) => ({ ...prev, descriptionRaw: e.target.value }))
                }
              />
            </label>
            <div className="full-row">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setShowAdvancedCreate((prev) => !prev)}
              >
                {showAdvancedCreate ? "Nascondi campi tecnici" : "Mostra campi tecnici"}
              </button>
            </div>
            {showAdvancedCreate && (
              <>
                <label>
                  Linea impianto
                  <input
                    value={createForm.machineLine}
                    onChange={(e) =>
                      setCreateForm((prev) => ({ ...prev, machineLine: e.target.value }))
                    }
                  />
                </label>
                <label>
                  Stazione
                  <input
                    value={createForm.machineStation}
                    onChange={(e) =>
                      setCreateForm((prev) => ({ ...prev, machineStation: e.target.value }))
                    }
                  />
                </label>
                <label>
                  Seriale macchina
                  <input
                    value={createForm.machineSerial}
                    onChange={(e) =>
                      setCreateForm((prev) => ({ ...prev, machineSerial: e.target.value }))
                    }
                  />
                </label>
              </>
            )}
            <div className="create-actions full-row">
              <button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creazione..." : "Crea Ticket"}
              </button>
              {createError && <p className="error">{createError}</p>}
            </div>
          </form>
        </section>

        <section className="card list-card">
          <div className="list-head">
            <h2>Inbox Ticket</h2>
            <div className="kpi-row">
              <span>Aperti: {openCount}</span>
              <span>Chiusi: {closedCount}</span>
              <span>Totali: {rows.length}</span>
              <span>Filtrati: {totalRecords}</span>
            </div>
          </div>
          {tickets.isLoading && <p>Caricamento ticket...</p>}
          {tickets.isError && <p className="error">{getErrorMessage(tickets.error)}</p>}
          {!tickets.isLoading && !tickets.isError && (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Priorita</th>
                  <th>Stato</th>
                  <th>SLA</th>
                  <th>Assegnato</th>
                  <th>Oggetto</th>
                  <th>Creato</th>
                </tr>
              </thead>
              <tbody>
                {pagedRows.map((ticket: Ticket) => (
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
          {!tickets.isLoading && !tickets.isError && totalRecords > 0 && (
            <div className="pager-row">
              <button
                className="secondary-button"
                onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                disabled={page <= 1}
              >
                Indietro
              </button>
              <span>
                Pagina {page} / {totalPages}
              </span>
              <button
                className="secondary-button"
                onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
                disabled={page >= totalPages}
              >
                Avanti
              </button>
            </div>
          )}
        </section>

        <section className="card detail-card">
          <h2>Dettaglio Ticket</h2>
          {!selectedTicketId && <p>Seleziona un ticket dalla inbox per vedere dettagli e timeline.</p>}
          {selectedTicket.isError && <p className="error">{getErrorMessage(selectedTicket.error)}</p>}
          {selectedTicket.data && (
            <>
              <div className="detail-head">
                <div>
                  <strong>#{selectedTicket.data.ticket_id}</strong>
                  <p>{selectedTicket.data.subject}</p>
                </div>
                <button
                  disabled={selectedTicket.data.status === "CLOSED" || closeMutation.isPending}
                  onClick={() => closeMutation.mutate(selectedTicket.data.ticket_id)}
                >
                  {selectedTicket.data.status === "CLOSED" ? "Ticket chiuso" : "Chiudi ticket"}
                </button>
              </div>
              <div className="detail-meta">
                <p>Cliente: {selectedTicket.data.tenant_id}</p>
                <p>Stato: {selectedTicket.data.status}</p>
                <p>Richiedente: {selectedTicket.data.requester_name}</p>
                <p>Email: {selectedTicket.data.requester_email}</p>
                <p>
                  Assegnato a: {selectedTicket.data.assignee_name || "-"} /{" "}
                  {selectedTicket.data.assignee_email || "-"}
                </p>
                <p>Scadenza SLA: {selectedTicket.data.sla_due_at ? formatDate(selectedTicket.data.sla_due_at) : "-"}</p>
                <p>Stato SLA: {selectedTicket.data.sla_state}</p>
                <p>
                  Macchina: {selectedTicket.data.machine_line}/{selectedTicket.data.machine_station}/
                  {selectedTicket.data.machine_serial}
                </p>
              </div>
              <div className="detail-actions">
                <h3>Assegnazione</h3>
                <div className="inline-form">
                  <input
                    placeholder="Nome operatore"
                    value={assigneeName}
                    onChange={(e) => setAssigneeName(e.target.value)}
                  />
                  <input
                    type="email"
                    placeholder="Email operatore"
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
                    {assignMutation.isPending ? "Salvataggio..." : "Assegna"}
                  </button>
                </div>
                {assignError && <p className="error">{assignError}</p>}
                <h3>Stato</h3>
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
                    {statusMutation.isPending ? "Aggiornamento..." : "Aggiorna stato"}
                  </button>
                </div>
                {statusError && <p className="error">{statusError}</p>}
                <h3>Nota operativa</h3>
                <div className="inline-form">
                  <input
                    placeholder="Scrivi una nota"
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
                    {noteMutation.isPending ? "Salvataggio..." : "Aggiungi nota"}
                  </button>
                </div>
                {noteError && <p className="error">{noteError}</p>}
              </div>
              <h3>Timeline</h3>
              {selectedEvents.isLoading && <p>Caricamento timeline...</p>}
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
              <h3>AI Memory Feedback</h3>
              <div className="inline-form">
                <select value={memoryScore} onChange={(e) => setMemoryScore(e.target.value)}>
                  <option value="5">5 - Ottimo esito</option>
                  <option value="4">4 - Buon esito</option>
                  <option value="3">3 - Medio</option>
                  <option value="2">2 - Scarso</option>
                  <option value="1">1 - Non utile</option>
                </select>
                <input
                  placeholder="Nota di risoluzione da ricordare"
                  value={memoryNote}
                  onChange={(e) => setMemoryNote(e.target.value)}
                />
                <button
                  onClick={() => {
                    if (!memoryNote.trim()) {
                      setAgentError("Inserisci una nota prima di salvare il feedback AI.");
                      return;
                    }
                    memoryFeedbackMutation.mutate();
                  }}
                  disabled={memoryFeedbackMutation.isPending}
                >
                  {memoryFeedbackMutation.isPending ? "Salvataggio..." : "Salva memoria"}
                </button>
              </div>
              {agentError && <p className="error">{agentError}</p>}
              {!!agentMemorySuggestions.data?.length && (
                <ul className="timeline">
                  {agentMemorySuggestions.data.map((item: AgentMemorySuggestion) => (
                    <li key={`${item.ticket_id}-${item.created_at}`}>
                      <div>
                        <strong>{item.ticket_id}</strong>
                        <span>score {item.outcome_score}</span>
                      </div>
                      <p>{item.resolution_note || "-"}</p>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </section>
      </main>
      )}

      {resolvedView === "kpi" && (
        <div className="analytics-stack">
          <section className="card analytics-card">
            <h2>Dashboard Performance</h2>
            <p className="subtitle">Panoramica veloce delle performance operative del cliente selezionato.</p>
            <div className="analytics-grid">
              <div><span>Created last 24h</span><strong>{ticketMetrics.data?.created_last_24h ?? "-"}</strong></div>
              <div><span>Closed last 24h</span><strong>{ticketMetrics.data?.closed_last_24h ?? "-"}</strong></div>
              <div><span>In Progress</span><strong>{ticketMetrics.data?.in_progress_total ?? "-"}</strong></div>
              <div><span>Waiting</span><strong>{ticketMetrics.data?.waiting_total ?? "-"}</strong></div>
              <div><span>Resolved</span><strong>{ticketMetrics.data?.resolved_total ?? "-"}</strong></div>
              <div><span>Closed</span><strong>{ticketMetrics.data?.closed_total ?? "-"}</strong></div>
              <div><span>Open At Risk</span><strong>{ticketMetrics.data?.at_risk_open_total ?? "-"}</strong></div>
              <div><span>Open Breached</span><strong>{ticketMetrics.data?.breached_open_total ?? "-"}</strong></div>
            </div>
          </section>
          <section className="card automation-card">
            <h3>Automazione AI attiva</h3>
            <p className="subtitle">
              I trigger esterni (WMS/PLC/IoT) creano o correlano ticket in automatico con policy tenant dedicate.
            </p>
          </section>
          <section className="card automation-card">
            <h3>Next Best Actions</h3>
            {agentProactiveSummary.isLoading && <p>Calcolo azioni proattive...</p>}
            {agentProactiveSummary.isError && <p className="error">{getErrorMessage(agentProactiveSummary.error)}</p>}
            {!agentProactiveSummary.isLoading && !agentProactiveSummary.isError && (
              <ul className="timeline">
                {(agentProactiveSummary.data?.next_best_actions ?? []).slice(0, 6).map((item) => (
                  <li key={item.ticket_id}>
                    <div>
                      <strong>{item.ticket_id}</strong>
                      <span>{item.sla_state}</span>
                    </div>
                    <p>{item.recommendation}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className="card automation-card">
            <h3>Decisioni AI recenti</h3>
            {agentDecisionLogs.isLoading && <p>Caricamento decisioni...</p>}
            {agentDecisionLogs.isError && <p className="error">{getErrorMessage(agentDecisionLogs.error)}</p>}
            {!agentDecisionLogs.isLoading && !agentDecisionLogs.isError && (
              <table>
                <thead><tr><th>Ticket</th><th>Decisione</th><th>Confidenza</th><th>Motivo</th></tr></thead>
                <tbody>
                  {(agentDecisionLogs.data ?? []).slice(0, 8).map((row: AgentDecisionLog) => (
                    <tr key={row.id}>
                      <td>{row.ticket_id}</td>
                      <td>{row.decision}</td>
                      <td>{row.confidence}</td>
                      <td>{row.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          <section className="card automation-card">
            <h3>Action Execution Log</h3>
            {agentActionRuns.isLoading && <p>Caricamento action log...</p>}
            {agentActionRuns.isError && <p className="error">{getErrorMessage(agentActionRuns.error)}</p>}
            {!agentActionRuns.isLoading && !agentActionRuns.isError && (
              <table>
                <thead><tr><th>Ticket</th><th>Action</th><th>Status</th><th>Dettaglio</th></tr></thead>
                <tbody>
                  {(agentActionRuns.data ?? []).slice(0, 8).map((row: AgentActionRun) => (
                    <tr key={row.id}>
                      <td>{row.ticket_id}</td>
                      <td>{row.action_name}</td>
                      <td>{row.status}</td>
                      <td>{row.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>
      )}
      </>
      )}

      {resolvedView === "admin" && isAdminUser && (
        <section className="card admin-panel">
          <div className="admin-head">
            <div>
              <h2>Pannello Amministrazione</h2>
              <p className="subtitle">Sezioni separate e linguaggio chiaro per ridurre errore operativo.</p>
            </div>
            <div className="admin-nav">
              <button className={adminSection === "users" ? "view-button active" : "view-button"} onClick={() => setAdminSection("users")}>Utenti</button>
              <button className={adminSection === "routing" ? "view-button active" : "view-button"} onClick={() => setAdminSection("routing")}>Routing</button>
              <button className={adminSection === "sla" ? "view-button active" : "view-button"} onClick={() => setAdminSection("sla")}>SLA</button>
              <button className={adminSection === "automation" ? "view-button active" : "view-button"} onClick={() => setAdminSection("automation")}>Automation</button>
              <button className={adminSection === "audit" ? "view-button active" : "view-button"} onClick={() => setAdminSection("audit")}>Audit</button>
              <button className={adminSection === "technical" ? "view-button active" : "view-button"} onClick={() => setAdminSection("technical")}>Tecnico</button>
            </div>
          </div>

          <div className="admin-settings-grid">
            {adminSection === "technical" && (
              <div className="admin-section">
                <h3>Integrazioni tecniche</h3>
                <p className="subtitle">Questa area e pensata per setup iniziale o supporto tecnico.</p>
                <div className="create-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => setShowTechnicalPanel((prev) => !prev)}
                  >
                    {showTechnicalPanel ? "Nascondi impostazioni tecniche" : "Mostra impostazioni tecniche"}
                  </button>
                </div>
                {showTechnicalPanel && (
                  <div className="control-panel tech-panel">
                    <label>
                      API Base URL
                      <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
                    </label>
                    <label>
                      API Key
                      <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="Opzionale se auth API disattivata" />
                    </label>
                    <label>
                      Modalita ingresso ticket
                      <select value={intakeMode} onChange={(e) => setIntakeMode(e.target.value)}>
                        <option value="webhook">webhook (consigliata)</option>
                        <option value="api">api diretta</option>
                      </select>
                    </label>
                    <label>
                      Webhook URL
                      <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} />
                    </label>
                    {!enforceAuth && (
                      <label>
                        Ruolo simulato
                        <select value={userRole} onChange={(e) => setUserRole(e.target.value)}>
                          <option value="admin">admin</option>
                          <option value="operator">operator</option>
                          <option value="viewer">viewer</option>
                        </select>
                      </label>
                    )}
                  </div>
                )}
              </div>
            )}

            {adminSection === "routing" && (
              <div className="admin-section">
                <h3>Instradamento notifiche</h3>
                <p className="subtitle">Imposta i destinatari predefiniti delle notifiche ticket.</p>
                <div className="inline-form">
                  <input value={routeEmailsDraft} onChange={(e) => setRouteEmailsDraft(e.target.value)} placeholder="mail1@company.com, mail2@company.com" />
                  <button onClick={() => updateRouteMutation.mutate(routeEmailsDraft)} disabled={updateRouteMutation.isPending}>
                    {updateRouteMutation.isPending ? "Salvataggio..." : "Salva routing"}
                  </button>
                </div>
              </div>
            )}

            {adminSection === "sla" && (
              <div className="admin-section">
                <h3>Policy SLA (minuti)</h3>
                <div className="inline-form">
                  <input value={slaP1} onChange={(e) => setSlaP1(e.target.value)} placeholder="P1" />
                  <input value={slaP2} onChange={(e) => setSlaP2(e.target.value)} placeholder="P2" />
                  <input value={slaP3} onChange={(e) => setSlaP3(e.target.value)} placeholder="P3" />
                  <input value={slaP4} onChange={(e) => setSlaP4(e.target.value)} placeholder="P4" />
                  <button onClick={() => updateSlaMutation.mutate()} disabled={updateSlaMutation.isPending}>
                    {updateSlaMutation.isPending ? "Salvataggio..." : "Salva SLA"}
                  </button>
                </div>
              </div>
            )}

            {adminSection === "automation" && (
              <div className="admin-section">
                <h3>Policy Automazione</h3>
                <p className="subtitle">Configura correlazione, alert SLA e assegnazione automatica.</p>
                <div className="create-form">
                  <label>
                    Finestra correlazione (minuti)
                    <input
                      type="number"
                      min={1}
                      max={10080}
                      value={automationWindow}
                      onChange={(e) => setAutomationWindow(e.target.value)}
                      placeholder="1440"
                    />
                  </label>
                  <label>
                    Anticipo alert AT_RISK (minuti)
                    <input
                      type="number"
                      min={1}
                      max={10080}
                      value={automationAtRiskLead}
                      onChange={(e) => setAutomationAtRiskLead(e.target.value)}
                      placeholder="60"
                    />
                  </label>
                  <label>
                    Nome assegnazione automatica
                    <input
                      value={automationAssignName}
                      onChange={(e) => setAutomationAssignName(e.target.value)}
                      placeholder="Automation Dispatcher"
                    />
                  </label>
                  <label>
                    Email assegnazione automatica
                    <input
                      type="email"
                      value={automationAssignEmail}
                      onChange={(e) => setAutomationAssignEmail(e.target.value)}
                      placeholder="dispatch@company.com"
                    />
                  </label>
                  <label className="full-row">
                    Action Webhook URL
                    <input
                      value={automationWebhookUrl}
                      onChange={(e) => setAutomationWebhookUrl(e.target.value)}
                      placeholder="https://workflow.company.com/agent-actions"
                    />
                  </label>
                  <label className="full-row">
                    Action Webhook Token (opzionale)
                    <input
                      type="password"
                      value={automationWebhookToken}
                      onChange={(e) => setAutomationWebhookToken(e.target.value)}
                      placeholder="Bearer token"
                    />
                  </label>
                  <div className="create-actions">
                    <button onClick={() => updateAutomationPolicyMutation.mutate()} disabled={updateAutomationPolicyMutation.isPending}>
                      {updateAutomationPolicyMutation.isPending ? "Salvataggio..." : "Salva policy automazione"}
                    </button>
                    <button className="secondary-button" onClick={() => runSlaMonitorMutation.mutate()} disabled={runSlaMonitorMutation.isPending}>
                      {runSlaMonitorMutation.isPending ? "Esecuzione..." : "Esegui monitor SLA"}
                    </button>
                  </div>
                  {slaMonitorResult && <p className="subtitle">{slaMonitorResult}</p>}
                </div>
              </div>
            )}

            {adminSection === "users" && (
              <div className="admin-section">
                <h3>Gestione utenti</h3>
                <div className="create-form">
                  <label>Email<input value={newUserEmail} onChange={(e) => setNewUserEmail(e.target.value)} /></label>
                  <label>Nome completo<input value={newUserName} onChange={(e) => setNewUserName(e.target.value)} /></label>
                  <label>
                    Ruolo
                    <select value={newUserRole} onChange={(e) => setNewUserRole(e.target.value as "admin" | "operator" | "viewer")}>
                      <option value="admin">admin</option><option value="operator">operator</option><option value="viewer">viewer</option>
                    </select>
                  </label>
                  <label>Password<input type="password" value={newUserPassword} onChange={(e) => setNewUserPassword(e.target.value)} /></label>
                  <label>
                    Attivo
                    <select value={newUserActive ? "true" : "false"} onChange={(e) => setNewUserActive(e.target.value === "true")}>
                      <option value="true">true</option><option value="false">false</option>
                    </select>
                  </label>
                  <div className="create-actions">
                    <button
                      type="button"
                      onClick={() => {
                        if (!newUserEmail.trim() || !newUserName.trim() || !newUserPassword.trim()) {
                          setAdminError("Email, full name and password are required.");
                          return;
                        }
                        createAdminUserMutation.mutate();
                      }}
                      disabled={createAdminUserMutation.isPending}
                    >
                      {createAdminUserMutation.isPending ? "Creazione..." : "Crea utente"}
                    </button>
                  </div>
                </div>

                {adminUsers.isLoading && <p>Caricamento utenti...</p>}
                {adminUsers.isError && <p className="error">{getErrorMessage(adminUsers.error)}</p>}
                {!adminUsers.isLoading && !adminUsers.isError && !adminUsers.data?.length && (
                  <p className="subtitle">Nessun utente trovato per questo cliente.</p>
                )}
                {!!adminUsers.data?.length && (
                  <table className="admin-users-table">
                    <thead><tr><th>Email</th><th>Nome</th><th>Ruolo</th><th>Attivo</th><th>Reset password</th></tr></thead>
                    <tbody>
                      {adminUsers.data.map((user: AdminUser) => (
                        <tr key={user.id}>
                          <td>{user.email}</td><td>{user.full_name}</td><td>{user.role}</td>
                          <td>
                            <button className="secondary-button" onClick={() => toggleUserActiveMutation.mutate({ id: user.id, isActive: !user.is_active })} disabled={toggleUserActiveMutation.isPending}>
                              {user.is_active ? "Disattiva" : "Attiva"}
                            </button>
                          </td>
                          <td>
                            <div className="inline-form">
                              <input type="password" value={passwordDraftByUserId[user.id] ?? ""} placeholder="Nuova password" onChange={(e) => setPasswordDraftByUserId((prev) => ({ ...prev, [user.id]: e.target.value }))} />
                              <button
                                onClick={() => {
                                  const password = (passwordDraftByUserId[user.id] ?? "").trim();
                                  if (password.length < 8) {
                                    setAdminError("Password must be at least 8 characters.");
                                    return;
                                  }
                                  updateAdminPasswordMutation.mutate({ id: user.id, password });
                                }}
                                disabled={updateAdminPasswordMutation.isPending}
                              >
                                Reset
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {adminSection === "audit" && (
              <div className="admin-section">
                <h3>Audit amministrativo recente</h3>
                {adminAuditLogs.isLoading && <p>Caricamento audit log...</p>}
                {adminAuditLogs.isError && <p className="error">{getErrorMessage(adminAuditLogs.error)}</p>}
                {!adminAuditLogs.isLoading && !adminAuditLogs.isError && !adminAuditLogs.data?.length && (
                  <p className="subtitle">Nessun evento audit disponibile.</p>
                )}
                {!!adminAuditLogs.data?.length && (
                  <table className="admin-users-table">
                    <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th></tr></thead>
                    <tbody>
                      {adminAuditLogs.data.map((row: AdminAuditLog) => (
                        <tr key={row.id}>
                          <td>{formatDate(row.created_at)}</td>
                          <td>{row.actor_email}</td>
                          <td>{row.action}</td>
                          <td>{row.target_type}:{row.target_id}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}

            {adminError && <p className="error">{adminError}</p>}
          </div>
        </section>
      )}
      </>
      )}
    </div>
  );
}

export default App;
