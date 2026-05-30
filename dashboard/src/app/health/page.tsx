"use client";

import { AlertList } from "@/components/dashboard/alert-list";
import { SystemHealthComponent } from "@/components/dashboard/system-health";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorAlert } from "@/components/ui/error-alert";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { createEmptyHealth, fetchHealth, getApiBase } from "@/lib/api";
import { Activity, Server } from "lucide-react";

export default function HealthPage() {
  const { data, isLoading, isRefreshing, error, refresh } = useDashboardData(
    fetchHealth,
    createEmptyHealth
  );

  if (isLoading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="System Health"
        alertCount={data.alerts.length}
        lastUpdated={new Date().toLocaleString()}
        onRefresh={refresh}
        isRefreshing={isRefreshing}
      />

      <div className="p-6 space-y-6">
        {error && (
          <ErrorAlert
            message="Health data is unavailable right now, so this page is showing the zero-account empty state."
            details={error}
          />
        )}

        <Card>
          <CardHeader>
            <CardTitle>Operational Health</CardTitle>
          </CardHeader>
          <CardContent>
            <SystemHealthComponent health={data.system_health} />
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Active Alerts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <AlertList alerts={data.alerts} maxItems={10} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="h-5 w-5" />
                Backend Endpoint
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p className="text-muted-foreground">
                The dashboard is reading live data from:
              </p>
              <div className="rounded-lg bg-muted/50 p-3 font-mono break-all">{getApiBase()}</div>
              <p className="text-muted-foreground">
                If this backend has zero data, the health page remains live and renders empty-state
                values instead of synthetic metrics.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
