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
