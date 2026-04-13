"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createEmptyDashboard, fetchDashboard, Alert } from "@/lib/api";
import { cn, getSeverityColor } from "@/lib/utils";
import { AlertCircle, AlertTriangle, Bell, Info, XCircle } from "lucide-react";

interface AlertWithTimestamp extends Alert {
  timestamp: string;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertWithTimestamp[]>([]);
  const [filter, setFilter] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const dashboard = await fetchDashboard();
      setAlerts(
        dashboard.alerts.map((alert) => ({
          ...alert,
          timestamp: dashboard.generated_at,
        }))
      );
    } catch (err) {
      setAlerts(createEmptyDashboard().alerts.map((alert) => ({ ...alert, timestamp: new Date().toISOString() })));
      setError(err instanceof Error ? err.message : "Unable to load alerts");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const filteredAlerts = useMemo(() => {
    if (filter === "all") return alerts;
    return alerts.filter((alert) => alert.severity === filter || alert.source === filter);
  }, [alerts, filter]);

  const getAlertIcon = (severity: string) => {
    switch (severity) {
      case "critical":
        return <XCircle className="h-5 w-5" />;
      case "high":
        return <AlertCircle className="h-5 w-5" />;
      case "warning":
        return <AlertTriangle className="h-5 w-5" />;
      default:
        return <Info className="h-5 w-5" />;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const sources = Array.from(new Set(alerts.map((alert) => alert.source).filter(Boolean))) as string[];

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Alerts"
        alertCount={alerts.length}
        lastUpdated={new Date().toLocaleString()}
        onRefresh={loadData}
      />

      <div className="p-6 space-y-6">
        {error && (
          <Card className="border-yellow-500/30 bg-yellow-500/5">
            <CardContent className="p-4 text-sm text-yellow-700 dark:text-yellow-400">
              Alerts could not be loaded, so the page is currently empty. {error}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Bell className="h-5 w-5" />
                Alert Stream
              </span>
              <div className="flex flex-wrap gap-2">
                <Button variant={filter === "all" ? "default" : "outline"} size="sm" onClick={() => setFilter("all")}>
                  All
                </Button>
                <Button variant={filter === "warning" ? "default" : "outline"} size="sm" onClick={() => setFilter("warning")}>
                  Warning
                </Button>
                {sources.map((source) => (
                  <Button key={source} variant={filter === source ? "default" : "outline"} size="sm" onClick={() => setFilter(source)}>
                    {source}
                  </Button>
                ))}
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {filteredAlerts.length === 0 ? (
              <div className="py-12 text-center text-muted-foreground">
                No alerts are active right now.
              </div>
            ) : (
              <div className="space-y-3">
                {filteredAlerts.map((alert, index) => (
                  <div
                    key={`${alert.severity}-${alert.message}-${index}`}
                    className={cn("rounded-lg border p-4", getSeverityColor(alert.severity))}
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5">{getAlertIcon(alert.severity)}</div>
                      <div className="flex-1 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline">{alert.severity}</Badge>
                          {alert.source && <Badge variant="secondary">{alert.source}</Badge>}
                          <span className="text-xs opacity-70">
                            {new Date(alert.timestamp).toLocaleString()}
                          </span>
                        </div>
                        <p className="font-medium">{alert.message}</p>
                        {alert.recommendation && (
                          <p className="text-sm opacity-80">{alert.recommendation}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
