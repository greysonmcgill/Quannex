"use client";

import { useEffect, useState, useCallback } from "react";
import { Header } from "@/components/layout/header";
import { KPICard } from "@/components/dashboard/kpi-card";
import { AlertList } from "@/components/dashboard/alert-list";
import { RevenueChart } from "@/components/dashboard/revenue-chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { fetchExecutive, ExecutiveData } from "@/lib/api";
import {
  DollarSign,
  TrendingUp,
  Target,
  CreditCard,
  BarChart3,
  PieChart,
} from "lucide-react";

const mockExecutiveData: ExecutiveData = {
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
    revenue: [
      ["2026-02-01", 75000],
      ["2026-02-02", 82000],
      ["2026-02-03", 78000],
      ["2026-02-04", 95000],
      ["2026-02-05", 88000],
      ["2026-02-06", 92000],
      ["2026-02-07", 105000],
      ["2026-02-08", 98000],
      ["2026-02-09", 110000],
      ["2026-02-10", 115000],
      ["2026-02-11", 108000],
      ["2026-02-12", 120000],
      ["2026-02-13", 125000],
      ["2026-02-14", 118000],
    ],
    collections: [
      ["2026-02-01", 65000],
      ["2026-02-02", 72000],
      ["2026-02-03", 68000],
      ["2026-02-04", 85000],
      ["2026-02-05", 78000],
      ["2026-02-06", 82000],
      ["2026-02-07", 95000],
      ["2026-02-08", 88000],
      ["2026-02-09", 100000],
      ["2026-02-10", 105000],
      ["2026-02-11", 98000],
      ["2026-02-12", 110000],
      ["2026-02-13", 115000],
      ["2026-02-14", 108000],
    ],
    recovery_rate: [
      ["2026-02-01", 0.45],
      ["2026-02-02", 0.46],
      ["2026-02-03", 0.47],
      ["2026-02-04", 0.46],
      ["2026-02-05", 0.48],
      ["2026-02-06", 0.47],
      ["2026-02-07", 0.49],
      ["2026-02-08", 0.48],
      ["2026-02-09", 0.49],
      ["2026-02-10", 0.50],
      ["2026-02-11", 0.49],
      ["2026-02-12", 0.51],
      ["2026-02-13", 0.50],
      ["2026-02-14", 0.49],
    ],
  },
  alerts: [
    { severity: "warning", metric: "roi", message: "ROI trending below target this week", recommendation: "Review settlement acceptance rates" },
  ],
};

export default function ExecutivePage() {
  const [data, setData] = useState<ExecutiveData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const result = await fetchExecutive();
      setData(result);
    } catch (error) {
      setData(mockExecutiveData);
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

  const execData = data || mockExecutiveData;

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Executive Dashboard"
        alertCount={execData.alerts.length}
        lastUpdated={new Date(execData.generated_at).toLocaleString()}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      <div className="p-6 space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <KPICard
            title="Total Revenue"
            value={formatCurrency(execData.kpis.total_revenue.value)}
            change={execData.kpis.total_revenue.change}
            icon={<DollarSign className="h-4 w-4" />}
          />
          <KPICard
            title="Gross Margin"
            value={formatPercent(execData.kpis.gross_margin.value)}
            change={execData.kpis.gross_margin.change}
            icon={<PieChart className="h-4 w-4" />}
          />
          <KPICard
            title="Recovery Rate"
            value={formatPercent(execData.kpis.recovery_rate.value)}
            change={execData.kpis.recovery_rate.change}
            icon={<Target className="h-4 w-4" />}
          />
          <KPICard
            title="ROI"
            value={formatPercent(execData.kpis.roi.value)}
            change={execData.kpis.roi.change}
            icon={<TrendingUp className="h-4 w-4" />}
          />
          <KPICard
            title="Cost per Dollar"
            value={formatCurrency(execData.kpis.cost_per_dollar.value)}
            change={execData.kpis.cost_per_dollar.change}
            icon={<CreditCard className="h-4 w-4" />}
            description="Target: < $0.25"
          />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Revenue Trend
              </CardTitle>
            </CardHeader>
            <CardContent>
              <RevenueChart data={execData.trends.revenue} type="area" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-5 w-5" />
                Collections Trend
              </CardTitle>
            </CardHeader>
            <CardContent>
              <RevenueChart data={execData.trends.collections} type="line" />
            </CardContent>
          </Card>
        </div>

        {/* Additional Metrics */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Financial Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Total Collected</p>
                  <p className="text-2xl font-bold">
                    {formatCurrency(execData.kpis.total_revenue.value * 0.8, true)}
                  </p>
                  <p className="text-xs text-green-500">+12% vs last period</p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Total Costs</p>
                  <p className="text-2xl font-bold">
                    {formatCurrency(execData.kpis.total_revenue.value * 0.2, true)}
                  </p>
                  <p className="text-xs text-green-500">-5% vs last period</p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Net Profit</p>
                  <p className="text-2xl font-bold">
                    {formatCurrency(execData.kpis.total_revenue.value * 0.6, true)}
                  </p>
                  <p className="text-xs text-green-500">+18% vs last period</p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Portfolio Value</p>
                  <p className="text-2xl font-bold">$5M</p>
                  <p className="text-xs text-muted-foreground">Face value</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Executive Alerts</CardTitle>
            </CardHeader>
            <CardContent>
              <AlertList alerts={execData.alerts} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
