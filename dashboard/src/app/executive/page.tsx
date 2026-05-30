"use client";

import { AlertList } from "@/components/dashboard/alert-list";
import { KPICard } from "@/components/dashboard/kpi-card";
import { RevenueChart } from "@/components/dashboard/revenue-chart";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorAlert } from "@/components/ui/error-alert";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { createEmptyExecutiveData, fetchExecutive } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import {
  CreditCard,
  DollarSign,
  PieChart,
  Target,
  TrendingUp,
} from "lucide-react";

export default function ExecutivePage() {
  const { data, isLoading, isRefreshing, error, refresh } = useDashboardData(
    fetchExecutive,
    createEmptyExecutiveData
  );

  if (isLoading) {
    return <LoadingSpinner />;
  }

  const totalRevenue = data.kpis.total_revenue.value;
  const grossMargin = data.kpis.gross_margin.value;
  const totalCosts = totalRevenue > 0 ? totalRevenue * Math.max(0, 1 - grossMargin) : 0;
  const netProfit = totalRevenue - totalCosts;

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Executive Dashboard"
        alertCount={data.alerts.length}
        lastUpdated={new Date(data.generated_at).toLocaleString()}
        onRefresh={refresh}
        isRefreshing={isRefreshing}
      />

      <div className="p-6 space-y-6">
        {error && (
          <ErrorAlert
            message="The executive dashboard is showing empty-state metrics because the backend request failed."
            details={error}
          />
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
          <KPICard
            title="Total Revenue"
            value={formatCurrency(data.kpis.total_revenue.value)}
            change={data.kpis.total_revenue.change}
            icon={<DollarSign className="h-4 w-4" />}
          />
          <KPICard
            title="Gross Margin"
            value={formatPercent(data.kpis.gross_margin.value)}
            change={data.kpis.gross_margin.change}
            icon={<PieChart className="h-4 w-4" />}
          />
          <KPICard
            title="Recovery Rate"
            value={formatPercent(data.kpis.recovery_rate.value)}
            change={data.kpis.recovery_rate.change}
            icon={<Target className="h-4 w-4" />}
          />
          <KPICard
            title="ROI"
            value={formatPercent(data.kpis.roi.value)}
            change={data.kpis.roi.change}
            icon={<TrendingUp className="h-4 w-4" />}
          />
          <KPICard
            title="Cost per Dollar"
            value={formatCurrency(data.kpis.cost_per_dollar.value)}
            change={data.kpis.cost_per_dollar.change}
            icon={<CreditCard className="h-4 w-4" />}
          />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Revenue Trend</CardTitle>
            </CardHeader>
            <CardContent>
              {data.trends.revenue.length > 0 ? (
                <RevenueChart data={data.trends.revenue} type="area" />
              ) : (
                <div className="text-sm text-muted-foreground py-16 text-center">
                  Revenue trend will populate as payments are recorded.
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Collections Trend</CardTitle>
            </CardHeader>
            <CardContent>
              {data.trends.collections.length > 0 ? (
                <RevenueChart data={data.trends.collections} type="line" />
              ) : (
                <div className="text-sm text-muted-foreground py-16 text-center">
                  Collections trend will appear once payment history exists.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle>Financial Snapshot</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="rounded-lg bg-muted/50 p-4">
                <p className="text-sm text-muted-foreground">Revenue</p>
                <p className="text-2xl font-bold">{formatCurrency(totalRevenue, true)}</p>
              </div>
              <div className="rounded-lg bg-muted/50 p-4">
                <p className="text-sm text-muted-foreground">Estimated Costs</p>
                <p className="text-2xl font-bold">{formatCurrency(totalCosts, true)}</p>
              </div>
              <div className="rounded-lg bg-muted/50 p-4">
                <p className="text-sm text-muted-foreground">Net Profit</p>
                <p className="text-2xl font-bold">{formatCurrency(netProfit, true)}</p>
              </div>
              <div className="rounded-lg bg-muted/50 p-4">
                <p className="text-sm text-muted-foreground">Recovery Trend</p>
                <p className="text-2xl font-bold">{formatPercent(data.kpis.recovery_rate.value)}</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Executive Alerts</CardTitle>
            </CardHeader>
            <CardContent>
              <AlertList alerts={data.alerts} maxItems={5} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
