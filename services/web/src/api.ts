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

export function createApiClient(options: ApiClientOptions) {
  const baseUrl = withTrailingSlashRemoved(options.baseUrl);
  const webhookUrl = options.webhookUrl ? withTrailingSlashRemoved(options.webhookUrl) : "";
  const headers = createHeaders(options.apiKey, options.userRole, options.accessToken);

  async function getJson<T>(path: string): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, { headers });
    if (!response.ok) await parseError(response);
    return (await response.json()) as T;
  }

  async function patchJson<T>(path: string, payload?: unknown): Promise<T> {
    const requestInit: RequestInit = { method: "PATCH", headers };
    if (payload !== undefined) {
      requestInit.headers = { ...headers, "Content-Type": "application/json" };
      requestInit.body = JSON.stringify(payload);
    }
    const response = await fetch(`${baseUrl}${path}`, requestInit);
    if (!response.ok) await parseError(response);
    return (await response.json()) as T;
  }

  async function postJson<T>(path: string, payload: unknown): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) await parseError(response);
    return (await response.json()) as T;
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
    return (await response.json()) as T;
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
  };
}

export { ApiError };
