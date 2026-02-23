export type TicketStatus = "OPEN" | "CLOSED";
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
  machine_line: string;
  machine_station: string;
  machine_serial: string;
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

export interface ApiStatus {
  status: string;
}

interface ApiClientOptions {
  baseUrl: string;
  apiKey?: string;
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

function createHeaders(apiKey?: string): HeadersInit {
  const headers: Record<string, string> = {};
  if (apiKey) headers["X-API-Key"] = apiKey;
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
  const headers = createHeaders(options.apiKey);

  async function getJson<T>(path: string): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, { headers });
    if (!response.ok) await parseError(response);
    return (await response.json()) as T;
  }

  async function patchJson<T>(path: string): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, { method: "PATCH", headers });
    if (!response.ok) await parseError(response);
    return (await response.json()) as T;
  }

  return {
    health: () => getJson<ApiStatus>("/health"),
    ready: () => getJson<ApiStatus>("/ready"),
    listTickets: (tenantId: string, status: string) => {
      const statusParam = status === "ALL" ? "" : `&status=${status}`;
      return getJson<Ticket[]>(
        `/tickets?tenant_id=${encodeURIComponent(tenantId)}${statusParam}&limit=200`,
      );
    },
    getTicket: (ticketId: string) => getJson<Ticket>(`/tickets/${encodeURIComponent(ticketId)}`),
    getTicketEvents: (ticketId: string) =>
      getJson<TicketEvent[]>(`/tickets/${encodeURIComponent(ticketId)}/events?limit=500`),
    closeTicket: (ticketId: string) =>
      patchJson<{ ticket_id: string; status: TicketStatus }>(
        `/tickets/${encodeURIComponent(ticketId)}/close`,
      ),
  };
}

export { ApiError };
