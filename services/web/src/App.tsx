import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, createApiClient, type Ticket } from "./api";
import "./App.css";

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";
const DEFAULT_API_KEY = import.meta.env.VITE_API_KEY ?? "";

function formatDate(value: string): string {
  return new Date(value).toLocaleString();
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return `${error.message} (status ${error.status})`;
  if (error instanceof Error) return error.message;
  return "Unknown error";
}

function App() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [apiKey, setApiKey] = useState(DEFAULT_API_KEY);
  const [tenantId, setTenantId] = useState("demo");
  const [statusFilter, setStatusFilter] = useState("OPEN");
  const [selectedTicketId, setSelectedTicketId] = useState<string>("");

  const queryClient = useQueryClient();
  const api = useMemo(() => createApiClient({ baseUrl, apiKey }), [baseUrl, apiKey]);

  const health = useQuery({
    queryKey: ["health", baseUrl],
    queryFn: api.health,
  });

  const ready = useQuery({
    queryKey: ["ready", baseUrl],
    queryFn: api.ready,
  });

  const tickets = useQuery({
    queryKey: ["tickets", baseUrl, apiKey, tenantId, statusFilter],
    queryFn: () => api.listTickets(tenantId, statusFilter),
  });

  const selectedTicket = useQuery({
    queryKey: ["ticket", baseUrl, apiKey, selectedTicketId],
    queryFn: () => api.getTicket(selectedTicketId),
    enabled: Boolean(selectedTicketId),
  });

  const selectedEvents = useQuery({
    queryKey: ["events", baseUrl, apiKey, selectedTicketId],
    queryFn: () => api.getTicketEvents(selectedTicketId),
    enabled: Boolean(selectedTicketId),
  });

  const closeMutation = useMutation({
    mutationFn: (ticketId: string) => api.closeTicket(ticketId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      queryClient.invalidateQueries({ queryKey: ["ticket"] });
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });

  const rows = tickets.data ?? [];

  return (
    <div className="page-shell">
      <header className="topbar">
        <div>
          <h1>TechOps Copilot Console</h1>
          <p className="subtitle">Ticketing operations with automation visibility</p>
        </div>
        <div className="status-grid">
          <div className={`status-chip ${health.data?.status === "ok" ? "ok" : "fail"}`}>
            API Health: {health.isLoading ? "..." : health.data?.status ?? "error"}
          </div>
          <div className={`status-chip ${ready.data?.status === "ready" ? "ok" : "fail"}`}>
            API Ready: {ready.isLoading ? "..." : ready.data?.status ?? "error"}
          </div>
        </div>
      </header>

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
          Tenant
          <input value={tenantId} onChange={(e) => setTenantId(e.target.value)} />
        </label>
        <label>
          Status
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="OPEN">OPEN</option>
            <option value="CLOSED">CLOSED</option>
            <option value="ALL">ALL</option>
          </select>
        </label>
      </section>

      <main className="content-grid">
        <section className="card list-card">
          <h2>Ticket Inbox</h2>
          {tickets.isLoading && <p>Loading tickets...</p>}
          {tickets.isError && <p className="error">{getErrorMessage(tickets.error)}</p>}
          {!tickets.isLoading && !tickets.isError && (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Subject</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((ticket: Ticket) => (
                  <tr
                    key={ticket.ticket_id}
                    className={ticket.ticket_id === selectedTicketId ? "selected" : ""}
                    onClick={() => setSelectedTicketId(ticket.ticket_id)}
                  >
                    <td>{ticket.ticket_id}</td>
                    <td>{ticket.priority}</td>
                    <td>{ticket.status}</td>
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
                <p>Requester: {selectedTicket.data.requester_name}</p>
                <p>Email: {selectedTicket.data.requester_email}</p>
                <p>
                  Machine: {selectedTicket.data.machine_line}/{selectedTicket.data.machine_station}/
                  {selectedTicket.data.machine_serial}
                </p>
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
    </div>
  );
}

export default App;
