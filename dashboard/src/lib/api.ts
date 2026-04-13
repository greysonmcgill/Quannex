const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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

// API Functions
export async function fetchDashboard(): Promise<DashboardData> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/`);
  if (!res.ok) throw new Error("Failed to fetch dashboard");
  return res.json();
}

export async function fetchExecutive(): Promise<ExecutiveData> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/executive`);
  if (!res.ok) throw new Error("Failed to fetch executive dashboard");
  return res.json();
}

export async function fetchOperations(): Promise<OperationsData> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/operations`);
  if (!res.ok) throw new Error("Failed to fetch operations dashboard");
  return res.json();
}

export async function fetchCompliance(): Promise<ComplianceData> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/compliance`);
  if (!res.ok) throw new Error("Failed to fetch compliance dashboard");
  return res.json();
}

export async function fetchTokenization(): Promise<TokenizationData> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/tokenization`);
  if (!res.ok) throw new Error("Failed to fetch tokenization dashboard");
  return res.json();
}

export async function fetchSummary(): Promise<SummaryStats> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/summary`);
  if (!res.ok) throw new Error("Failed to fetch summary");
  return res.json();
}

export async function fetchHealth(): Promise<{
  system_health: SystemHealth;
  alerts: Alert[];
}> {
  const res = await fetch(`${API_BASE}/api/v1/dashboard/health`);
  if (!res.ok) throw new Error("Failed to fetch health");
  return res.json();
}

// ==================== Account Types ====================

export interface AccountListItem {
  id: string;
  external_account_id: string | null;
  debtor_name: string;
  current_balance: number;
  original_balance: number;
  debt_type: string;
  status: string;
  state: string | null;
  days_past_due: number;
  recovery_probability: number | null;
  contact_attempts: number;
  last_contact_date: string | null;
  created_at: string;
}

export interface AccountListResponse {
  accounts: AccountListItem[];
  total: number;
  page: number;
  page_size: number;
  total_balance: number;
}

export interface AccountStats {
  total_accounts: number;
  total_balance: number;
  avg_balance: number;
  avg_recovery_probability: number;
  avg_days_past_due: number;
  by_status: Record<string, number>;
  by_debt_type: Record<string, number>;
  by_state: Record<string, number>;
}

export interface ContactAttemptDetail {
  id: string;
  channel: string;
  direction: string;
  outcome: string;
  duration_seconds: number | null;
  response_received: boolean;
  cost: number;
  created_at: string;
}

export interface PaymentDetail {
  id: string;
  amount: number;
  payment_method: string;
  status: string;
  is_settlement: boolean;
  is_payment_plan: boolean;
  processed_at: string | null;
  created_at: string;
}

export interface ComplianceEventDetail {
  id: string;
  event_type: string;
  severity: string;
  description: string;
  resolution: string | null;
  regulation: string | null;
  created_at: string;
}

export interface AccountDetail {
  id: string;
  external_account_id: string | null;
  portfolio_id: string | null;
  debtor_name: string;
  debtor_first_name: string | null;
  debtor_last_name: string | null;
  phone: string | null;
  phone_valid: boolean;
  email: string | null;
  email_valid: boolean;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  original_creditor: string | null;
  current_creditor: string | null;
  debt_type: string;
  original_balance: number;
  current_balance: number;
  days_past_due: number;
  status: string;
  status_changed_at: string;
  recovery_probability: number | null;
  settlement_threshold: number | null;
  optimal_channels: string[] | null;
  do_not_call: boolean;
  do_not_email: boolean;
  bankruptcy_flag: boolean;
  disputed: boolean;
  total_payments: number;
  contact_attempts: number;
  successful_contacts: number;
  last_contact_date: string | null;
  contact_history: ContactAttemptDetail[];
  payment_history: PaymentDetail[];
  compliance_events: ComplianceEventDetail[];
  created_at: string;
  updated_at: string;
}

// ==================== Portfolio Types ====================

export interface PortfolioResponse {
  id: string;
  name: string;
  client_id: string | null;
  total_accounts: number;
  total_balance: number;
  upload_status: string;
  valid_rows: number;
  invalid_rows: number;
  created_at: string;
}

export interface PortfolioListResponse {
  portfolios: PortfolioResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface ValidationError {
  row: number;
  field: string;
  error: string;
  value: string | null;
}

export interface UploadSummary {
  portfolio_id: string;
  portfolio_name: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  total_balance: number;
  accounts_by_status: Record<string, number>;
  accounts_by_debt_type: Record<string, number>;
  errors: ValidationError[];
}

// ==================== Account API Functions ====================

export interface AccountFilters {
  page?: number;
  page_size?: number;
  status?: string;
  debt_type?: string;
  state?: string;
  min_balance?: number;
  max_balance?: number;
  search?: string;
  sort_by?: string;
  sort_order?: string;
}

export async function fetchAccounts(
  filters: AccountFilters = {}
): Promise<AccountListResponse> {
  const params = new URLSearchParams();
  if (filters.page) params.set("page", filters.page.toString());
  if (filters.page_size) params.set("page_size", filters.page_size.toString());
  if (filters.status) params.set("status", filters.status);
  if (filters.debt_type) params.set("debt_type", filters.debt_type);
  if (filters.state) params.set("state", filters.state);
  if (filters.min_balance) params.set("min_balance", filters.min_balance.toString());
  if (filters.max_balance) params.set("max_balance", filters.max_balance.toString());
  if (filters.search) params.set("search", filters.search);
  if (filters.sort_by) params.set("sort_by", filters.sort_by);
  if (filters.sort_order) params.set("sort_order", filters.sort_order);

  const res = await fetch(`${API_BASE}/api/v1/accounts?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch accounts");
  return res.json();
}

export async function fetchAccountStats(): Promise<AccountStats> {
  const res = await fetch(`${API_BASE}/api/v1/accounts/stats`);
  if (!res.ok) throw new Error("Failed to fetch account stats");
  return res.json();
}

export async function fetchAccount(id: string): Promise<AccountDetail> {
  const res = await fetch(`${API_BASE}/api/v1/accounts/${id}`);
  if (!res.ok) throw new Error("Failed to fetch account");
  return res.json();
}

export async function updateAccountStatus(
  id: string,
  status: string,
  notes?: string
): Promise<{ account_id: string; old_status: string; new_status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/accounts/${id}/status`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes }),
  });
  if (!res.ok) throw new Error("Failed to update account status");
  return res.json();
}

export async function logContactAttempt(
  id: string,
  data: {
    channel: string;
    direction?: string;
    outcome: string;
    contact_target?: string;
    duration_seconds?: number;
    message_content?: string;
    response_content?: string;
    cost?: number;
  }
): Promise<{ contact_id: string; account_id: string }> {
  const res = await fetch(`${API_BASE}/api/v1/accounts/${id}/contact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to log contact attempt");
  return res.json();
}

export async function recordPayment(
  id: string,
  data: {
    amount: number;
    payment_method: string;
    is_settlement?: boolean;
    is_payment_plan?: boolean;
    payment_plan_installment?: number;
    transaction_id?: string;
  }
): Promise<{ payment_id: string; account_id: string; new_balance: number }> {
  const res = await fetch(`${API_BASE}/api/v1/accounts/${id}/payment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to record payment");
  return res.json();
}

// ==================== Portfolio API Functions ====================

export async function fetchPortfolios(
  page: number = 1,
  page_size: number = 20
): Promise<PortfolioListResponse> {
  const res = await fetch(
    `${API_BASE}/api/v1/portfolios?page=${page}&page_size=${page_size}`
  );
  if (!res.ok) throw new Error("Failed to fetch portfolios");
  return res.json();
}

export async function fetchPortfolio(id: string): Promise<PortfolioResponse> {
  const res = await fetch(`${API_BASE}/api/v1/portfolios/${id}`);
  if (!res.ok) throw new Error("Failed to fetch portfolio");
  return res.json();
}

export async function uploadPortfolio(
  file: File,
  portfolioName?: string,
  clientId?: string
): Promise<UploadSummary> {
  const formData = new FormData();
  formData.append("file", file);

  const params = new URLSearchParams();
  if (portfolioName) params.set("portfolio_name", portfolioName);
  if (clientId) params.set("client_id", clientId);

  const url = `${API_BASE}/api/v1/portfolios/upload${params.toString() ? "?" + params.toString() : ""}`;

  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(error.detail || "Failed to upload portfolio");
  }

  return res.json();
}

export async function deletePortfolio(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/portfolios/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete portfolio");
}
