"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertList } from "@/components/dashboard/alert-list";
import { SystemHealthComponent } from "@/components/dashboard/system-health";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createEmptyHealth, fetchHealth, getApiBase, SystemHealth, Alert } from "@/lib/api";
import { Activity, Server } from "lucide-react";

interface HealthData {
  system_health: SystemHealth;
  alerts: Alert[];
}

export default function HealthPage() {
  const [data, setData] = useState<HealthData>(createEmptyHealth());
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      setData(await fetchHealth());
    } catch (err) {
      setData(createEmptyHealth());
      setError(err instanceof Error ? err.message : "Unable to load health data");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

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
        title="System Health"
        alertCount={data.alerts.length}
        lastUpdated={new Date().toLocaleString()}
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
              Health data is unavailable right now, so this page is showing the zero-account empty
              state. {error}
            </CardContent>
          </Card>
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
