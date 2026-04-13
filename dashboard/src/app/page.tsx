"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlertList } from "@/components/dashboard/alert-list";
import { ChannelMetricsComponent } from "@/components/dashboard/channel-metrics";
import { KPICard } from "@/components/dashboard/kpi-card";
import { PipelineFunnel } from "@/components/dashboard/pipeline-funnel";
import { SystemHealthComponent } from "@/components/dashboard/system-health";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createEmptyDashboard, DashboardData, fetchDashboard } from "@/lib/api";
import { formatCurrency, formatNumber, formatPercent } from "@/lib/utils";
import {
  Activity,
  ArrowRight,
  DollarSign,
  FolderUp,
  Shield,
  Users,
} from "lucide-react";

export default function OverviewPage() {
  const [data, setData] = useState<DashboardData>(createEmptyDashboard());
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const result = await fetchDashboard();
      setData(result);
    } catch (err) {
      setData(createEmptyDashboard());
      setError(err instanceof Error ? err.message : "Unable to load dashboard");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const activeAccounts = data.operations.pipeline.ingested?.count || 0;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Dashboard Overview"
        alertCount={data.alerts.length}
        lastUpdated={new Date(data.generated_at).toLocaleString()}
        onRefresh={() => {
          setIsRefreshing(true);
          loadData();
        }}
        isRefreshing={isRefreshing}
      />

      <div className="p-6 space-y-6">
        {error && (
          <Card className="border-yellow-500/30 bg-yellow-500/5">
            <CardContent className="p-4 text-sm text-yellow-700 dark:text-yellow-400">
              Showing an empty-state dashboard because the backend could not be reached. {error}
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <KPICard
            title="Total Revenue"
            value={formatCurrency(data.executive.kpis.total_revenue.value)}
            change={data.executive.kpis.total_revenue.change}
            icon={<DollarSign className="h-4 w-4" />}
          />
          <KPICard
            title="Recovery Rate"
            value={formatPercent(data.executive.kpis.recovery_rate.value)}
            change={data.executive.kpis.recovery_rate.change}
            icon={<Activity className="h-4 w-4" />}
          />
          <KPICard
            title="Active Accounts"
            value={formatNumber(activeAccounts)}
            icon={<Users className="h-4 w-4" />}
            description="Loaded from the operational database"
          />
          <KPICard
            title="Compliance Score"
            value={`${data.compliance.overall_score.score.toFixed(1)}%`}
            icon={<Shield className="h-4 w-4" />}
            description={data.compliance.overall_score.rating}
          />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle>Operational Funnel</CardTitle>
            </CardHeader>
            <CardContent>
              <PipelineFunnel pipeline={data.operations.pipeline} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Live Alerts</CardTitle>
            </CardHeader>
            <CardContent>
              <AlertList alerts={data.alerts} maxItems={6} />
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>System Health</CardTitle>
            </CardHeader>
            <CardContent>
              <SystemHealthComponent health={data.system_health} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Channel Performance</CardTitle>
            </CardHeader>
            <CardContent>
              <ChannelMetricsComponent channels={data.operations.channels} />
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Next Actions</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link href="/upload" className="block">
              <div className="rounded-lg border p-4 h-full hover:bg-muted/50 transition-colors">
                <FolderUp className="h-5 w-5 mb-3 text-primary" />
                <p className="font-medium">Upload a Portfolio</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Import a CSV, validate rows, and auto-score accounts on ingest.
                </p>
                <div className="mt-4 inline-flex items-center text-sm text-primary">
                  Open uploader <ArrowRight className="h-4 w-4 ml-1" />
                </div>
              </div>
            </Link>

            <Link href="/accounts" className="block">
              <div className="rounded-lg border p-4 h-full hover:bg-muted/50 transition-colors">
                <Users className="h-5 w-5 mb-3 text-primary" />
                <p className="font-medium">Review Accounts</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Filter the live book, inspect account details, and record actions.
                </p>
                <div className="mt-4 inline-flex items-center text-sm text-primary">
                  Open accounts <ArrowRight className="h-4 w-4 ml-1" />
                </div>
              </div>
            </Link>

            <div className="rounded-lg border p-4 h-full bg-muted/30">
              <Shield className="h-5 w-5 mb-3 text-primary" />
              <p className="font-medium">Empty State Ready</p>
              <p className="text-sm text-muted-foreground mt-1">
                With zero accounts in the database, the dashboard stays functional and renders
                honest zero-state metrics instead of demo values.
              </p>
              <div className="mt-4">
                <Button variant="outline" size="sm" onClick={loadData}>
                  Refresh Data
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
