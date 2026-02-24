export type TicketStatus = "OPEN" | "IN_PROGRESS" | "WAITING" | "RESOLVED" | "CLOSED";
export type TicketPriority = "P1" | "P2" | "P3" | "P4";
export type EventType = "CREATED" | "EMAIL_SENT" | "CLOSED" | "NOTE";

export interface Ticket {
  ticket_id: string;
  tenant_id: string;
  status: TicketStatus;
  subject: string;
  priority: TicketPriority;
  description_raw: string;
  requester_name: string;
  requester_email: string;
  assignee_name: string;
  assignee_email: string;
  machine_line: string;
  machine_station: string;
  machine_serial: string;
  sla_due_at: string | null;
  first_response_at: string | null;
  resolved_at: string | null;
  sla_state: "ON_TIME" | "AT_RISK" | "BREACHED" | "NO_SLA" | "CLOSED";
  created_at: string;
  updated_at: string;
}

export interface TicketEvent {
  id: number;
  ticket_id: string;
  event_type: EventType;
  message: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface TenantRoute {
  tenant_id: string;
  channel: string;
  to_emails: string[];
  cc_emails: string[];
  bcc_emails: string[];
  reply_to?: string | null;
  is_active: boolean;
  updated_at: string;
}

export interface TenantEmailHistoryItem {
  email: string;
  last_used_at: string;
}

export interface QueueSummary {
  open_total: number;
  unassigned_total: number;
  my_total: number;
  at_risk_total: number;
  breached_total: number;
}

export interface TicketMetrics {
  open_total: number;
  in_progress_total: number;
  waiting_total: number;
  resolved_total: number;
  closed_total: number;
  created_last_24h: number;
  closed_last_24h: number;
  avg_resolution_minutes: number;
  at_risk_open_total: number;
  breached_open_total: number;
}

export interface ApiStatus {
  status: string;
}

export interface AuthUser {
  email: string;
  full_name: string;
  role: string;
  tenant_id: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  role: "admin" | "operator" | "viewer";
  tenant_id: string;
  is_active: boolean;
  updated_at: string;
}

export interface TenantSlaPolicy {
  tenant_id: string;
  p1_minutes: number;
  p2_minutes: number;
  p3_minutes: number;
  p4_minutes: number;
  updated_at: string;
}

export interface AdminAuditLog {
  id: number;
  tenant_id: string;
  actor_email: string;
  actor_role: string;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface TenantAutomationPolicy {
  tenant_id: string;
  correlation_window_minutes: number;
  at_risk_lead_minutes: number;
  human_review_threshold: number;
  auto_execute_threshold: number;
  auto_assign_name: string;
  auto_assign_email?: string | null;
  action_webhook_url: string;
  updated_at: string;
}

export interface IntakeRequest {
  tenant_id: string;
  source?: string;
  requester: {
    name: string;
    email: string;
  };
  subject: string;
  description_raw: string;
  machine: {
    line: string;
    station: string;
    serial: string;
  };
  priority: TicketPriority;
}

export interface WebhookNotificationOverride {
  to_emails: string[];
}

export interface WebhookIntakeRequest extends IntakeRequest {
  notification?: WebhookNotificationOverride;
}

export interface IntakeResponse {
  ticket_id: string;
  status: TicketStatus;
}

export interface WebhookIntakeResponse {
  ok: boolean;
  ticket_id: string;
  status: TicketStatus;
  tenant_id: string;
  notified_to?: string[];
}

export interface SlaMonitorResponse {
  tenant_id: string;
  scanned: number;
  at_risk_alerted: number;
  breached_alerted: number;
  ticket_ids: string[];
}

export interface AgentDecisionLog {
  id: number;
  tenant_id: string;
  ticket_id: string;
  source_system: string;
  event_id: string;
  event_type: string;
  severity: string;
  decision: string;
  priority: string;
  reason: string;
  confidence: number;
  memory_hint: string;
  playbook: Record<string, string>;
  created_at: string;
}

export interface AgentActionRun {
  id: number;
  tenant_id: string;
  ticket_id: string;
  action_name: string;
  status: "SKIPPED" | "SUCCESS" | "FAILED";
  detail: string;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown>;
  created_at: string;
}

export interface AgentProactiveAction {
  ticket_id: string;
  priority: string;
  sla_state: string;
  recommendation: string;
}

export interface AgentProactiveSummary {
  tenant_id: string;
  predicted_breach_2h: number;
  unassigned_open: number;
  next_best_actions: AgentProactiveAction[];
}

export interface AgentMemorySuggestion {
  ticket_id: string;
  outcome_score: number;
  resolution_note: string;
  created_at: string;
}

export interface AgentPendingDecision {
  id: number;
  tenant_id: string;
  ticket_id: string;
  event_id: string;
  confidence: number;
  status: "PENDING" | "APPROVED" | "REJECTED";
  payload: Record<string, unknown>;
  approved_by: string;
  approved_at: string | null;
  created_at: string;
}

export interface AgentPlaybook {
  id: number;
  tenant_id: string;
  event_type: string;
  severity: string;
  version: number;
  team: string;
  runbook: string;
  action: string;
  is_active: boolean;
  created_at: string;
}

interface ApiClientOptions {
  baseUrl: string;
  apiKey?: string;
  webhookUrl?: string;
  userRole?: string;
  accessToken?: string;
}

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function withTrailingSlashRemoved(value: string): string {
  return value.replace(/\/+$/, "");
}

function createHeaders(apiKey?: string, userRole?: string, accessToken?: string): HeadersInit {
  const headers: Record<string, string> = {};
  if (apiKey) headers["X-API-Key"] = apiKey;
  if (userRole) headers["X-User-Role"] = userRole;
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  return headers;
}

async function parseError(response: Response): Promise<never> {
  try {
    const body = (await response.json()) as { detail?: string };
    throw new ApiError(body.detail || `HTTP ${response.status}`, response.status);
  } catch {
    throw new ApiError(`HTTP ${response.status}`, response.status);
  }
}

async function parseJsonOrThrow<T>(response: Response, emptyBodyMessage: string): Promise<T> {
  const raw = await response.text();
  if (!raw.trim()) {
    throw new ApiError(emptyBodyMessage, response.status);
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new ApiError("Invalid JSON response from upstream service", response.status);
  }
}

export function createApiClient(options: ApiClientOptions) {
  const baseUrl = withTrailingSlashRemoved(options.baseUrl);
  const webhookUrl = options.webhookUrl ? withTrailingSlashRemoved(options.webhookUrl) : "";
  const headers = createHeaders(options.apiKey, options.userRole, options.accessToken);

  async function getJson<T>(path: string): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, { headers });
    if (!response.ok) await parseError(response);
    return parseJsonOrThrow<T>(response, "Empty response from API");
  }

  async function patchJson<T>(path: string, payload?: unknown): Promise<T> {
    const requestInit: RequestInit = { method: "PATCH", headers };
    if (payload !== undefined) {
      requestInit.headers = { ...headers, "Content-Type": "application/json" };
      requestInit.body = JSON.stringify(payload);
    }
    const response = await fetch(`${baseUrl}${path}`, requestInit);
    if (!response.ok) await parseError(response);
    return parseJsonOrThrow<T>(response, "Empty response from API");
  }

  async function postJson<T>(path: string, payload: unknown): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) await parseError(response);
    return parseJsonOrThrow<T>(response, "Empty response from API");
  }

  async function postWebhookJson<T>(payload: unknown): Promise<T> {
    if (!webhookUrl) {
      throw new ApiError("Webhook URL is not configured", 500);
    }
    const response = await fetch(webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) await parseError(response);
    return parseJsonOrThrow<T>(
      response,
      "Webhook responded with empty body. Check n8n 'Respond to Webhook' node output JSON.",
    );
  }

  return {
    health: () => getJson<ApiStatus>("/health"),
    ready: () => getJson<ApiStatus>("/ready"),
    login: (email: string, password: string) =>
      postJson<LoginResponse>("/auth/login", { email, password }),
    me: () => getJson<AuthUser>("/auth/me"),
    listTickets: (
      tenantId: string,
      status: string,
      options?: {
        assigneeEmail?: string;
        onlyUnassigned?: boolean;
        slaState?: "ALL" | "ON_TIME" | "AT_RISK" | "BREACHED";
      },
    ) => {
      const statusParam = status === "ALL" ? "" : `&status=${status}`;
      const assigneeParam = options?.assigneeEmail
        ? `&assignee_email=${encodeURIComponent(options.assigneeEmail)}`
        : "";
      const unassignedParam = options?.onlyUnassigned ? "&only_unassigned=true" : "";
      const slaStateParam = options?.slaState ? `&sla_state=${options.slaState}` : "";
      return getJson<Ticket[]>(
        `/tickets?tenant_id=${encodeURIComponent(tenantId)}${statusParam}${assigneeParam}${unassignedParam}${slaStateParam}&limit=200`,
      );
    },
    getQueueSummary: (tenantId: string, assigneeEmail = "") =>
      getJson<QueueSummary>(
        `/tickets/queue-summary?tenant_id=${encodeURIComponent(tenantId)}&assignee_email=${encodeURIComponent(assigneeEmail)}`,
      ),
    getTicketMetrics: (tenantId: string) =>
      getJson<TicketMetrics>(`/tickets/metrics?tenant_id=${encodeURIComponent(tenantId)}`),
    getTicket: (ticketId: string) => getJson<Ticket>(`/tickets/${encodeURIComponent(ticketId)}`),
    getTicketEvents: (ticketId: string) =>
      getJson<TicketEvent[]>(`/tickets/${encodeURIComponent(ticketId)}/events?limit=500`),
    closeTicket: (ticketId: string) =>
      patchJson<{ ticket_id: string; status: TicketStatus }>(
        `/tickets/${encodeURIComponent(ticketId)}/close`,
      ),
    updateTicketStatus: (ticketId: string, status: TicketStatus) =>
      patchJson<{ ticket_id: string; status: TicketStatus }>(
        `/tickets/${encodeURIComponent(ticketId)}/status`,
        { status },
      ),
    assignTicket: (ticketId: string, assigneeName: string, assigneeEmail: string) =>
      patchJson<{ ticket_id: string; assignee_name: string; assignee_email: string }>(
        `/tickets/${encodeURIComponent(ticketId)}/assign`,
        { assignee_name: assigneeName, assignee_email: assigneeEmail },
      ),
    addTicketNote: (ticketId: string, message: string) =>
      postJson<{ ok: boolean }>(`/tickets/${encodeURIComponent(ticketId)}/notes`, { message }),
    createTicket: (payload: IntakeRequest) => postJson<IntakeResponse>("/intake", payload),
    createTicketViaWebhook: (payload: IntakeRequest, notificationEmail?: string) => {
      const webhookPayload: WebhookIntakeRequest = { ...payload };
      if (notificationEmail) {
        webhookPayload.notification = { to_emails: [notificationEmail] };
      }
      return postWebhookJson<WebhookIntakeResponse>(webhookPayload);
    },
    getTenantRoute: (tenantId: string) =>
      getJson<TenantRoute>(`/tenant-routes/${encodeURIComponent(tenantId)}`),
    updateTenantRoute: (tenantId: string, toEmails: string[]) =>
      patchJson<TenantRoute>(`/tenant-routes/${encodeURIComponent(tenantId)}`, {
        to_emails: toEmails,
      }),
    getTenantEmailHistory: (tenantId: string, limit = 50) =>
      getJson<TenantEmailHistoryItem[]>(
        `/tenant-email-history?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`,
      ),
    getTenantSlaPolicy: (tenantId: string) =>
      getJson<TenantSlaPolicy>(`/tenant-sla-policies/${encodeURIComponent(tenantId)}`),
    updateTenantSlaPolicy: (
      tenantId: string,
      payload: { p1_minutes: number; p2_minutes: number; p3_minutes: number; p4_minutes: number },
    ) =>
      patchJson<TenantSlaPolicy>(`/tenant-sla-policies/${encodeURIComponent(tenantId)}`, payload),
    getTenantAutomationPolicy: (tenantId: string) =>
      getJson<TenantAutomationPolicy>(`/tenant-automation-policies/${encodeURIComponent(tenantId)}`),
    updateTenantAutomationPolicy: (
      tenantId: string,
      payload: {
        correlation_window_minutes: number;
        at_risk_lead_minutes: number;
        human_review_threshold: number;
        auto_execute_threshold: number;
        auto_assign_name: string;
        auto_assign_email?: string | null;
        action_webhook_url?: string;
        action_webhook_token?: string;
      },
    ) => patchJson<TenantAutomationPolicy>(`/tenant-automation-policies/${encodeURIComponent(tenantId)}`, payload),
    runSlaMonitor: (tenantId: string, limit = 200) =>
      postJson<SlaMonitorResponse>("/automation/sla-monitor", { tenant_id: tenantId, limit }),
    listAgentDecisions: (tenantId: string, limit = 100) =>
      getJson<AgentDecisionLog[]>(
        `/automation/decisions?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`,
      ),
    listAgentActions: (tenantId: string, limit = 100) =>
      getJson<AgentActionRun[]>(
        `/automation/actions?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`,
      ),
    getAgentProactiveSummary: (tenantId: string, limit = 20) =>
      getJson<AgentProactiveSummary>(
        `/automation/proactive-summary?tenant_id=${encodeURIComponent(tenantId)}&limit=${limit}`,
      ),
    addAgentMemoryFeedback: (payload: {
      tenant_id: string;
      ticket_id: string;
      event_type: string;
      asset_id: string;
      outcome_score: number;
      resolution_note: string;
    }) => postJson<{ ok: boolean; id: number }>("/automation/memory/feedback", payload),
    listAgentMemorySuggestions: (tenantId: string, eventType: string, assetId = "", limit = 10) =>
      getJson<AgentMemorySuggestion[]>(
        `/automation/memory/suggestions?tenant_id=${encodeURIComponent(tenantId)}&event_type=${encodeURIComponent(eventType)}&asset_id=${encodeURIComponent(assetId)}&limit=${limit}`,
      ),
    listAgentPendingDecisions: (tenantId: string, status: "PENDING" | "APPROVED" | "REJECTED" = "PENDING", limit = 100) =>
      getJson<AgentPendingDecision[]>(
        `/automation/pending-decisions?tenant_id=${encodeURIComponent(tenantId)}&status=${encodeURIComponent(status)}&limit=${limit}`,
      ),
    approveAgentPendingDecision: (decisionId: number, note = "") =>
      postJson<{ ok: boolean; id: number; status: string }>(`/automation/pending-decisions/${decisionId}/approve`, { note }),
    rejectAgentPendingDecision: (decisionId: number, note = "") =>
      postJson<{ ok: boolean; id: number; status: string }>(`/automation/pending-decisions/${decisionId}/reject`, { note }),
    listAgentPlaybooks: (tenantId: string, eventType = "", limit = 200) =>
      getJson<AgentPlaybook[]>(
        `/automation/playbooks?tenant_id=${encodeURIComponent(tenantId)}&event_type=${encodeURIComponent(eventType)}&limit=${limit}`,
      ),
    createAgentPlaybook: (payload: {
      tenant_id: string;
      event_type: string;
      severity: "critical" | "high" | "medium" | "low";
      version: number;
      team: string;
      runbook: string;
      action: string;
      is_active: boolean;
    }) => postJson<AgentPlaybook>("/automation/playbooks", payload),
    listAdminUsers: (tenantId = "") =>
      getJson<AdminUser[]>(
        `/admin/users${tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : ""}`,
      ),
    createAdminUser: (payload: {
      email: string;
      full_name: string;
      password: string;
      role: "admin" | "operator" | "viewer";
      tenant_id: string;
      is_active: boolean;
    }) => postJson<AdminUser>("/admin/users", payload),
    updateAdminUser: (
      userId: number,
      payload: Partial<{
        full_name: string;
        role: "admin" | "operator" | "viewer";
        tenant_id: string;
        is_active: boolean;
      }>,
    ) => patchJson<AdminUser>(`/admin/users/${userId}`, payload),
    updateAdminUserPassword: (userId: number, password: string) =>
      patchJson<{ ok: boolean }>(`/admin/users/${userId}/password`, { password }),
    listAdminAuditLogs: (tenantId = "", limit = 100) =>
      getJson<AdminAuditLog[]>(
        `/admin/audit-logs?limit=${limit}${tenantId ? `&tenant_id=${encodeURIComponent(tenantId)}` : ""}`,
      ),
  };
}

export { ApiError };
