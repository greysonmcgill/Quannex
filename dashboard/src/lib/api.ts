const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export interface DashboardData {
  generated_at: string;
  executive: ExecutiveData;
  operations: OperationsData;
  compliance: ComplianceData;
  tokenization: TokenizationData;
  system_health: SystemHealth;
  alerts: Alert[];
}

export interface ExecutiveData {
  generated_at: string;
  period: string;
  kpis: {
    total_revenue: KPIValue;
    gross_margin: KPIValue;
    recovery_rate: KPIValue;
    roi: KPIValue;
    cost_per_dollar: KPIValue;
  };
  trends: {
    revenue: [string, number][];
    collections: [string, number][];
    recovery_rate: [string, number][];
  };
  alerts: Alert[];
}

export interface KPIValue {
  value: number;
  unit: string;
  change: {
    value: number;
    direction: string;
  };
}

export interface OperationsData {
  generated_at: string;
  pipeline: Record<string, PipelineStage>;
  channels: Record<string, ChannelMetrics>;
  queues: Record<string, QueueStatus>;
  bottlenecks: Bottleneck[];
  throughput: ThroughputMetrics;
}

export interface PipelineStage {
  count: number;
  conversion_rate: number;
  avg_time_in_stage: string;
}

export interface ChannelMetrics {
  attempts: number | null;
  responses: number | null;
  conversions: number | null;
  response_rate: number;
  conversion_rate: number;
  cost_per_contact: number;
}

export interface QueueStatus {
  depth: number;
  processing_rate: number;
  estimated_clear_time: string;
}

export interface Bottleneck {
  location: string;
  severity: string;
  issue: string;
  recommendation: string;
}

export interface ThroughputMetrics {
  accounts_per_hour: number;
  contacts_per_hour: number;
  resolutions_per_hour: number;
  payments_per_hour: number;
  current_capacity_utilization: number;
}

export interface ComplianceData {
  generated_at: string;
  overall_score: {
    score: number;
    rating: string;
    trend: string;
    components: Record<string, number>;
  };
  audit_readiness: {
    overall_readiness: string;
    score: number;
    checklist: Record<string, { status: string; coverage: number }>;
    last_audit: string;
    next_scheduled: string;
  };
  violations: {
    total_30d: number;
    total_90d: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
    recent: Violation[];
  };
  state_compliance: {
    fully_compliant: number;
    requires_attention: number;
    attention_states: string[];
    details: Record<string, StateCompliance>;
  };
  regulation_status: Record<string, RegulationStatus>;
}

export interface Violation {
  id: string;
  date: string;
  type: string;
  description: string;
  severity: string;
  resolution: string;
}

export interface StateCompliance {
  status: string;
  license_expiry?: string;
  note?: string;
}

export interface RegulationStatus {
  status: string;
  last_review?: string;
  automation_coverage?: number;
  consent_rate?: number;
  dnc_compliance?: number;
  "7_in_7_compliance"?: number;
  model_notice_usage?: number;
  pending_changes?: number;
}

export interface TokenizationData {
  generated_at: string;
  portfolio_summary: PortfolioSummary;
  pools: Pool[];
  tranches: Record<string, TrancheData>;
  investor_metrics: InvestorMetrics;
  secondary_market: SecondaryMarket;
}

export interface PortfolioSummary {
  total_face_value: number;
  total_nav: number;
  total_pools: number;
  active_tranches: number;
  total_investors: number;
  avg_yield: number;
  default_rate: number;
}

export interface Pool {
  pool_id: string;
  asset_class: string;
  face_value: number;
  nav: number;
  recovery_rate: number;
  yield: number;
  status: string;
}

export interface TrancheData {
  total_value: number;
  avg_yield: number;
  default_rate: number;
  rating: string;
}

export interface InvestorMetrics {
  total_invested: number;
  distributions_ytd: number;
  realized_yield_ytd: number;
  investor_retention: number;
  new_investors_30d: number;
  pending_redemptions: number;
}

export interface SecondaryMarket {
  volume_30d: number;
  avg_discount: number;
  bid_ask_spread: number;
  active_listings: number;
  recent_trades: Trade[];
}

export interface Trade {
  date: string;
  tranche: string;
  amount: number;
  price: number;
}

export interface SystemHealth {
  status: string;
  uptime: string;
  modules: Record<string, string>;
  last_incident: string;
  mttr: string;
}

export interface Alert {
  severity: string;
  metric?: string;
  source?: string;
  message: string;
  recommendation?: string;
}

export interface SummaryStats {
  generated_at: string;
  executive: {
    total_revenue: number;
    recovery_rate: number;
    roi: number;
    cost_per_dollar: number;
  };
  operations: {
    accounts_processing: number;
    capacity_utilization: number;
    bottleneck_count: number;
  };
  compliance: {
    score: number;
    violations_30d: number;
    audit_readiness: number;
  };
  tokenization: {
    total_nav: number;
    avg_yield: number;
    active_pools: number;
  };
  alert_count: number;
}

export interface AccountSummary {
  account_id: string;
  debtor_name: string;
  balance: number;
  original_balance: number;
  original_creditor: string;
  debt_type: string;
  days_past_due: number;
  state: string;
  phone?: string | null;
  email?: string | null;
  status: string;
  recovery_probability: number;
  optimal_channels: string[];
  settlement_threshold: number;
  total_paid: number;
  total_contact_attempts: number;
  last_contact_at?: string | null;
  last_payment_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ContactHistoryEntry {
  attempt_id: string;
  channel: string;
  outcome: string;
  compliant: boolean;
  cost: number;
  agent_name?: string | null;
  notes?: string | null;
  attempted_at: string;
}

export interface PaymentHistoryEntry {
  payment_id: string;
  amount: number;
  method: string;
  status: string;
  reference?: string | null;
  notes?: string | null;
  recorded_at: string;
}

export interface ComplianceEventRecord {
  event_id: string;
  event_type: string;
  severity: string;
  message: string;
  resolution?: string | null;
  resolved: boolean;
  occurred_at: string;
}

export interface AccountDetail extends AccountSummary {
  contact_history: ContactHistoryEntry[];
  payments: PaymentHistoryEntry[];
  compliance_events: ComplianceEventRecord[];
}

export interface AccountsResponse {
  page: number;
  page_size: number;
  total: number;
  pages: number;
  items: AccountSummary[];
}

export interface PortfolioUploadRowError {
  row_number: number;
  account_id?: string | null;
  errors: string[];
}

export interface UploadedAccountSummary {
  account_id: string;
  debtor_name: string;
  debt_type: string;
  balance: number;
  recovery_probability: number;
  optimal_channels: string[];
  settlement_threshold: number;
}

export interface PortfolioUploadResult {
  portfolio_id: string;
  portfolio_name: string;
  filename: string;
  received_rows: number;
  imported_rows: number;
  rejected_rows: number;
  debt_mix: Record<string, number>;
  row_errors: PortfolioUploadRowError[];
  accounts: UploadedAccountSummary[];
}

export interface AccountsQuery {
  page?: number;
  page_size?: number;
  status?: string;
  debt_type?: string;
  state?: string;
  search?: string;
}

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

export function getApiBase(): string {
  return API_BASE;
}

export function getWebSocketUrl(path = "/api/v1/dashboard/ws"): string {
  const url = new URL(apiUrl(path));
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    cache: "no-store",
    ...init,
  });
  if (!response.ok) {
    throw new Error(await response.text() || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function createEmptyExecutiveData(): ExecutiveData {
  return {
    generated_at: new Date().toISOString(),
    period: "30d",
    kpis: {
      total_revenue: { value: 0, unit: "USD", change: { value: 0, direction: "stable" } },
      gross_margin: { value: 0, unit: "%", change: { value: 0, direction: "stable" } },
      recovery_rate: { value: 0, unit: "%", change: { value: 0, direction: "stable" } },
      roi: { value: 0, unit: "%", change: { value: 0, direction: "stable" } },
      cost_per_dollar: { value: 0, unit: "USD", change: { value: 0, direction: "stable" } },
    },
    trends: {
      revenue: [],
      collections: [],
      recovery_rate: [],
    },
    alerts: [],
  };
}

export function createEmptyOperationsData(): OperationsData {
  return {
    generated_at: new Date().toISOString(),
    pipeline: {
      ingested: { count: 0, conversion_rate: 0, avg_time_in_stage: "N/A" },
      enriched: { count: 0, conversion_rate: 0, avg_time_in_stage: "N/A" },
      scored: { count: 0, conversion_rate: 0, avg_time_in_stage: "N/A" },
      contacted: { count: 0, conversion_rate: 0, avg_time_in_stage: "N/A" },
      negotiating: { count: 0, conversion_rate: 0, avg_time_in_stage: "N/A" },
      payment_pending: { count: 0, conversion_rate: 0, avg_time_in_stage: "N/A" },
      resolved: { count: 0, conversion_rate: 0, avg_time_in_stage: "N/A" },
    },
    channels: {
      sms: { attempts: 0, responses: 0, conversions: 0, response_rate: 0, conversion_rate: 0, cost_per_contact: 0 },
      email: { attempts: 0, responses: 0, conversions: 0, response_rate: 0, conversion_rate: 0, cost_per_contact: 0 },
      voice: { attempts: 0, responses: 0, conversions: 0, response_rate: 0, conversion_rate: 0, cost_per_contact: 0 },
      digital: { attempts: 0, responses: 0, conversions: 0, response_rate: 0, conversion_rate: 0, cost_per_contact: 0 },
    },
    queues: {
      contact_queue: { depth: 0, processing_rate: 0, estimated_clear_time: "clear" },
      payment_queue: { depth: 0, processing_rate: 0, estimated_clear_time: "clear" },
      enrichment_queue: { depth: 0, processing_rate: 0, estimated_clear_time: "clear" },
    },
    bottlenecks: [],
    throughput: {
      accounts_per_hour: 0,
      contacts_per_hour: 0,
      resolutions_per_hour: 0,
      payments_per_hour: 0,
      current_capacity_utilization: 0,
    },
  };
}

export function createEmptyComplianceData(): ComplianceData {
  return {
    generated_at: new Date().toISOString(),
    overall_score: {
      score: 100,
      rating: "No Data",
      trend: "stable",
      components: { fdcpa: 100, tcpa: 100, regulation_f: 100, state_laws: 100 },
    },
    audit_readiness: {
      overall_readiness: "empty",
      score: 0,
      checklist: {},
      last_audit: "",
      next_scheduled: "",
    },
    violations: {
      total_30d: 0,
      total_90d: 0,
      by_type: {},
      by_severity: {},
      recent: [],
    },
    state_compliance: {
      fully_compliant: 0,
      requires_attention: 0,
      attention_states: [],
      details: {},
    },
    regulation_status: {},
  };
}

export function createEmptyTokenizationData(): TokenizationData {
  return {
    generated_at: new Date().toISOString(),
    portfolio_summary: {
      total_face_value: 0,
      total_nav: 0,
      total_pools: 0,
      active_tranches: 0,
      total_investors: 0,
      avg_yield: 0,
      default_rate: 0,
    },
    pools: [],
    tranches: {},
    investor_metrics: {
      total_invested: 0,
      distributions_ytd: 0,
      realized_yield_ytd: 0,
      investor_retention: 0,
      new_investors_30d: 0,
      pending_redemptions: 0,
    },
    secondary_market: {
      volume_30d: 0,
      avg_discount: 0,
      bid_ask_spread: 0,
      active_listings: 0,
      recent_trades: [],
    },
  };
}

export function createEmptyHealth(): { system_health: SystemHealth; alerts: Alert[] } {
  return {
    system_health: {
      status: "healthy",
      uptime: "No data yet",
      modules: {
        database: "healthy",
        ingestion: "healthy",
        payment_processing: "healthy",
        compliance: "healthy",
        dashboard: "healthy",
        reporting: "healthy",
      },
      last_incident: "No incidents",
      mttr: "N/A",
    },
    alerts: [],
  };
}

export function createEmptyDashboard(): DashboardData {
  return {
    generated_at: new Date().toISOString(),
    executive: createEmptyExecutiveData(),
    operations: createEmptyOperationsData(),
    compliance: createEmptyComplianceData(),
    tokenization: createEmptyTokenizationData(),
    system_health: createEmptyHealth().system_health,
    alerts: [],
  };
}

export async function fetchDashboard(): Promise<DashboardData> {
  return fetchJson<DashboardData>("/api/v1/dashboard/");
}

export async function fetchExecutive(): Promise<ExecutiveData> {
  return fetchJson<ExecutiveData>("/api/v1/dashboard/executive");
}

export async function fetchOperations(): Promise<OperationsData> {
  return fetchJson<OperationsData>("/api/v1/dashboard/operations");
}

export async function fetchCompliance(): Promise<ComplianceData> {
  return fetchJson<ComplianceData>("/api/v1/dashboard/compliance");
}

export async function fetchTokenization(): Promise<TokenizationData> {
  return fetchJson<TokenizationData>("/api/v1/dashboard/tokenization");
}

export async function fetchSummary(): Promise<SummaryStats> {
  return fetchJson<SummaryStats>("/api/v1/dashboard/summary");
}

export async function fetchHealth(): Promise<{ system_health: SystemHealth; alerts: Alert[] }> {
  return fetchJson<{ system_health: SystemHealth; alerts: Alert[] }>("/api/v1/dashboard/health");
}

export async function fetchAccounts(query: AccountsQuery = {}): Promise<AccountsResponse> {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  });
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<AccountsResponse>(`/api/v1/accounts${suffix}`);
}

export async function fetchAccount(accountId: string): Promise<AccountDetail> {
  return fetchJson<AccountDetail>(`/api/v1/accounts/${accountId}`);
}

export async function updateAccountStatus(accountId: string, status: string, notes?: string) {
  return fetchJson<AccountSummary>(`/api/v1/accounts/${accountId}/status`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes }),
  });
}

export async function logAccountContact(
  accountId: string,
  payload: { channel: string; outcome: string; compliant?: boolean; notes?: string; agent_name?: string }
) {
  return fetchJson<ContactHistoryEntry>(`/api/v1/accounts/${accountId}/contact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function recordAccountPayment(
  accountId: string,
  payload: { amount: number; method: string; status?: string; reference?: string; notes?: string }
) {
  return fetchJson<PaymentHistoryEntry>(`/api/v1/accounts/${accountId}/payment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function uploadPortfolio(file: File): Promise<PortfolioUploadResult> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(apiUrl("/api/v1/portfolios/upload"), {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await response.text() || "Upload failed");
  }
  return response.json() as Promise<PortfolioUploadResult>;
}

