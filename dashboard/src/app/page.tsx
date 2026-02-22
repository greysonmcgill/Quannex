"use client";

import { useEffect, useState, useCallback } from "react";
import { Header } from "@/components/layout/header";
import { KPICard } from "@/components/dashboard/kpi-card";
import { AlertList } from "@/components/dashboard/alert-list";
import { SystemHealthComponent } from "@/components/dashboard/system-health";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { fetchDashboard, DashboardData } from "@/lib/api";
import {
  DollarSign,
  TrendingUp,
  Target,
  CreditCard,
  Users,
  Shield,
  Coins,
  Activity,
} from "lucide-react";

// Mock data for demo
const mockDashboardData: DashboardData = {
  generated_at: new Date().toISOString(),
  executive: {
    generated_at: new Date().toISOString(),
    period: "30d",
    kpis: {
      total_revenue: { value: 2500000, unit: "USD", change: { value: 0.12, direction: "up" } },
      gross_margin: { value: 0.8, unit: "%", change: { value: 0.05, direction: "up" } },
      recovery_rate: { value: 0.49, unit: "%", change: { value: 0.03, direction: "up" } },
      roi: { value: 4.0, unit: "%", change: { value: 0.15, direction: "up" } },
      cost_per_dollar: { value: 0.2, unit: "USD", change: { value: -0.02, direction: "down" } },
    },
    trends: {
      revenue: [],
      collections: [],
      recovery_rate: [],
    },
    alerts: [],
  },
  operations: {
    generated_at: new Date().toISOString(),
    pipeline: {
      ingested: { count: 150000, conversion_rate: 0.95, avg_time_in_stage: "2 minutes" },
      enriched: { count: 142500, conversion_rate: 0.90, avg_time_in_stage: "5 minutes" },
      scored: { count: 128250, conversion_rate: 0.88, avg_time_in_stage: "1 minute" },
      contacted: { count: 112860, conversion_rate: 0.35, avg_time_in_stage: "3 days" },
      negotiating: { count: 39501, conversion_rate: 0.65, avg_time_in_stage: "7 days" },
      payment_pending: { count: 25675, conversion_rate: 0.80, avg_time_in_stage: "14 days" },
      resolved: { count: 73500, conversion_rate: 1.0, avg_time_in_stage: "N/A" },
    },
    channels: {
      sms: { attempts: null, responses: null, conversions: null, response_rate: 0.15, conversion_rate: 0.08, cost_per_contact: 0.02 },
      email: { attempts: null, responses: null, conversions: null, response_rate: 0.12, conversion_rate: 0.05, cost_per_contact: 0.01 },
      voice: { attempts: null, responses: null, conversions: null, response_rate: 0.25, conversion_rate: 0.15, cost_per_contact: 0.15 },
      digital: { attempts: null, responses: null, conversions: null, response_rate: 0.18, conversion_rate: 0.10, cost_per_contact: 0.03 },
    },
    queues: {
      contact_queue: { depth: 15000, processing_rate: 500, estimated_clear_time: "30 minutes" },
      payment_queue: { depth: 2500, processing_rate: 100, estimated_clear_time: "25 minutes" },
      enrichment_queue: { depth: 5000, processing_rate: 1000, estimated_clear_time: "5 minutes" },
    },
    bottlenecks: [],
    throughput: {
      accounts_per_hour: 5000,
      contacts_per_hour: 15000,
      resolutions_per_hour: 500,
      payments_per_hour: 200,
      current_capacity_utilization: 0.72,
    },
  },
  compliance: {
    generated_at: new Date().toISOString(),
    overall_score: { score: 98.5, rating: "Excellent", trend: "stable", components: { fdcpa: 99.2, tcpa: 97.8, regulation_f: 99.0, state_laws: 98.0 } },
    audit_readiness: { overall_readiness: "high", score: 95, checklist: {}, last_audit: "2025-11-15", next_scheduled: "2026-05-15" },
    violations: { total_30d: 3, total_90d: 8, by_type: {}, by_severity: {}, recent: [] },
    state_compliance: { fully_compliant: 47, requires_attention: 3, attention_states: ["CA", "NY", "MA"], details: {} },
    regulation_status: {},
  },
  tokenization: {
    generated_at: new Date().toISOString(),
    portfolio_summary: {
      total_face_value: 25000000,
      total_nav: 18500000,
      total_pools: 12,
      active_tranches: 48,
      total_investors: 156,
      avg_yield: 0.18,
      default_rate: 0.12,
    },
    pools: [],
    tranches: {},
    investor_metrics: { total_invested: 18000000, distributions_ytd: 2500000, realized_yield_ytd: 0.14, investor_retention: 0.95, new_investors_30d: 12, pending_redemptions: 150000 },
    secondary_market: { volume_30d: 500000, avg_discount: 0.05, bid_ask_spread: 0.02, active_listings: 25, recent_trades: [] },
  },
  system_health: {
    status: "healthy",
    uptime: "99.97%",
    modules: {
      ingestion: "healthy",
      shadow_bureau: "healthy",
      empathy_engine: "healthy",
      payment_processing: "healthy",
      tokenization: "healthy",
      reporting: "healthy",
    },
    last_incident: "2026-01-10",
    mttr: "15 minutes",
  },
  alerts: [
    { severity: "warning", source: "operations", message: "Contact queue depth elevated - 15,000 accounts pending", recommendation: "Consider scaling outreach capacity" },
  ],
};

export default function OverviewPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const result = await fetchDashboard();
      setData(result);
    } catch (error) {
      // Use mock data on error
      setData(mockDashboardData);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const dashboardData = data || mockDashboardData;

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Dashboard Overview"
        alertCount={dashboardData.alerts.length}
        lastUpdated={new Date(dashboardData.generated_at).toLocaleString()}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      <div className="p-6 space-y-6">
        {/* Top KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Total Revenue"
            value={formatCurrency(dashboardData.executive.kpis.total_revenue.value)}
            change={dashboardData.executive.kpis.total_revenue.change}
            icon={<DollarSign className="h-4 w-4" />}
          />
          <KPICard
            title="Recovery Rate"
            value={formatPercent(dashboardData.executive.kpis.recovery_rate.value)}
            change={dashboardData.executive.kpis.recovery_rate.change}
            icon={<Target className="h-4 w-4" />}
          />
          <KPICard
            title="ROI"
            value={formatPercent(dashboardData.executive.kpis.roi.value)}
            change={dashboardData.executive.kpis.roi.change}
            icon={<TrendingUp className="h-4 w-4" />}
          />
          <KPICard
            title="Cost per Dollar"
            value={formatCurrency(dashboardData.executive.kpis.cost_per_dollar.value)}
            change={dashboardData.executive.kpis.cost_per_dollar.change}
            icon={<CreditCard className="h-4 w-4" />}
            description="Lower is better"
          />
        </div>

        {/* Secondary KPIs */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Active Accounts"
            value={formatCurrency(
              Object.values(dashboardData.operations.pipeline).reduce(
                (sum, stage) => sum + (stage.count || 0),
                0
              )
            ).replace("$", "")}
            icon={<Users className="h-4 w-4" />}
            description="In pipeline"
          />
          <KPICard
            title="Compliance Score"
            value={`${dashboardData.compliance.overall_score.score}%`}
            icon={<Shield className="h-4 w-4" />}
            description={dashboardData.compliance.overall_score.rating}
          />
          <KPICard
            title="Portfolio NAV"
            value={formatCurrency(dashboardData.tokenization.portfolio_summary.total_nav, true)}
            icon={<Coins className="h-4 w-4" />}
            description={`${dashboardData.tokenization.portfolio_summary.total_pools} active pools`}
          />
          <KPICard
            title="Capacity Utilization"
            value={formatPercent(dashboardData.operations.throughput.current_capacity_utilization)}
            icon={<Activity className="h-4 w-4" />}
            description="Current load"
          />
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* System Health */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>System Health</CardTitle>
            </CardHeader>
            <CardContent>
              <SystemHealthComponent health={dashboardData.system_health} />
            </CardContent>
          </Card>

          {/* Alerts */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Active Alerts</span>
                {dashboardData.alerts.length > 0 && (
                  <span className="text-sm font-normal text-muted-foreground">
                    {dashboardData.alerts.length} active
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <AlertList alerts={dashboardData.alerts} maxItems={5} />
            </CardContent>
          </Card>
        </div>

        {/* Quick Stats Tabs */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="pipeline">
              <TabsList>
                <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
                <TabsTrigger value="compliance">Compliance</TabsTrigger>
                <TabsTrigger value="tokenization">Tokenization</TabsTrigger>
              </TabsList>

              <TabsContent value="pipeline" className="pt-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(dashboardData.operations.pipeline)
                    .slice(0, 4)
                    .map(([stage, data]) => (
                      <div key={stage} className="p-4 bg-muted/50 rounded-lg">
                        <p className="text-sm text-muted-foreground capitalize">
                          {stage.replace("_", " ")}
                        </p>
                        <p className="text-2xl font-bold">
                          {(data.count || 0).toLocaleString()}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatPercent(data.conversion_rate)} conversion
                        </p>
                      </div>
                    ))}
                </div>
              </TabsContent>

              <TabsContent value="compliance" className="pt-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(
                    dashboardData.compliance.overall_score.components
                  ).map(([regulation, score]) => (
                    <div key={regulation} className="p-4 bg-muted/50 rounded-lg">
                      <p className="text-sm text-muted-foreground uppercase">
                        {regulation.replace("_", " ")}
                      </p>
                      <p className="text-2xl font-bold">{score}%</p>
                      <p className="text-xs text-green-500">Compliant</p>
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="tokenization" className="pt-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <p className="text-sm text-muted-foreground">Face Value</p>
                    <p className="text-2xl font-bold">
                      {formatCurrency(
                        dashboardData.tokenization.portfolio_summary
                          .total_face_value,
                        true
                      )}
                    </p>
                  </div>
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <p className="text-sm text-muted-foreground">Total NAV</p>
                    <p className="text-2xl font-bold">
                      {formatCurrency(
                        dashboardData.tokenization.portfolio_summary.total_nav,
                        true
                      )}
                    </p>
                  </div>
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <p className="text-sm text-muted-foreground">Avg Yield</p>
                    <p className="text-2xl font-bold text-green-500">
                      {formatPercent(
                        dashboardData.tokenization.portfolio_summary.avg_yield
                      )}
                    </p>
                  </div>
                  <div className="p-4 bg-muted/50 rounded-lg">
                    <p className="text-sm text-muted-foreground">Investors</p>
                    <p className="text-2xl font-bold">
                      {dashboardData.tokenization.portfolio_summary.total_investors}
                    </p>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
