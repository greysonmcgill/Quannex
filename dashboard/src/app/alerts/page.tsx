"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn, getSeverityColor } from "@/lib/utils";
import { fetchDashboard, Alert, DashboardData } from "@/lib/api";
import {
  Bell,
  AlertTriangle,
  AlertCircle,
  Info,
  XCircle,
  CheckCircle2,
  Filter,
  Clock,
} from "lucide-react";

interface AlertWithTimestamp extends Alert {
  timestamp?: string;
  acknowledged?: boolean;
}

const mockAlerts: AlertWithTimestamp[] = [
  {
    severity: "warning",
    source: "operations",
    message: "Contact queue depth elevated - 15,000 accounts pending",
    recommendation: "Consider scaling outreach capacity",
    timestamp: "2026-02-17T10:30:00Z",
    acknowledged: false,
  },
  {
    severity: "info",
    source: "compliance",
    message: "New regulation effective in California on 2026-03-01",
    recommendation: "Review and update compliance rules",
    timestamp: "2026-02-17T09:15:00Z",
    acknowledged: false,
  },
  {
    severity: "warning",
    source: "tokenization",
    message: "Pool BNPL-2026-Q1 approaching capacity limit",
    recommendation: "Consider creating new pool or expanding limits",
    timestamp: "2026-02-16T16:45:00Z",
    acknowledged: true,
  },
  {
    severity: "info",
    source: "executive",
    message: "Weekly ROI report available",
    timestamp: "2026-02-16T08:00:00Z",
    acknowledged: true,
  },
];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertWithTimestamp[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  const loadData = async () => {
    try {
      const data = await fetchDashboard();
      const timestampedAlerts: AlertWithTimestamp[] = data.alerts.map((a) => ({
        ...a,
        timestamp: new Date().toISOString(),
        acknowledged: false,
      }));
      setAlerts(timestampedAlerts.length > 0 ? timestampedAlerts : mockAlerts);
    } catch (error) {
      setAlerts(mockAlerts);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

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

  const filteredAlerts = alerts.filter((alert) => {
    if (filter === "all") return true;
    if (filter === "active") return !alert.acknowledged;
    if (filter === "acknowledged") return alert.acknowledged;
    return alert.severity === filter;
  });

  const alertCounts = {
    total: alerts.length,
    critical: alerts.filter((a) => a.severity === "critical").length,
    warning: alerts.filter((a) => a.severity === "warning").length,
    info: alerts.filter((a) => a.severity === "info").length,
    active: alerts.filter((a) => !a.acknowledged).length,
  };

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
        title="Alerts"
        alertCount={alertCounts.active}
        lastUpdated={new Date().toLocaleString()}
        onRefresh={loadData}
      />

      <div className="p-6 space-y-6">
        {/* Alert Summary */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card
            className={cn(
              "cursor-pointer transition-colors",
              filter === "all" && "ring-2 ring-primary"
            )}
            onClick={() => setFilter("all")}
          >
            <CardContent className="p-4 text-center">
              <Bell className="h-6 w-6 mx-auto mb-2 text-primary" />
              <p className="text-2xl font-bold">{alertCounts.total}</p>
              <p className="text-sm text-muted-foreground">Total Alerts</p>
            </CardContent>
          </Card>
          <Card
            className={cn(
              "cursor-pointer transition-colors",
              filter === "active" && "ring-2 ring-primary"
            )}
            onClick={() => setFilter("active")}
          >
            <CardContent className="p-4 text-center">
              <AlertCircle className="h-6 w-6 mx-auto mb-2 text-blue-500" />
              <p className="text-2xl font-bold">{alertCounts.active}</p>
              <p className="text-sm text-muted-foreground">Active</p>
            </CardContent>
          </Card>
          <Card
            className={cn(
              "cursor-pointer transition-colors",
              filter === "critical" && "ring-2 ring-primary"
            )}
            onClick={() => setFilter("critical")}
          >
            <CardContent className="p-4 text-center">
              <XCircle className="h-6 w-6 mx-auto mb-2 text-red-500" />
              <p className="text-2xl font-bold">{alertCounts.critical}</p>
              <p className="text-sm text-muted-foreground">Critical</p>
            </CardContent>
          </Card>
          <Card
            className={cn(
              "cursor-pointer transition-colors",
              filter === "warning" && "ring-2 ring-primary"
            )}
            onClick={() => setFilter("warning")}
          >
            <CardContent className="p-4 text-center">
              <AlertTriangle className="h-6 w-6 mx-auto mb-2 text-yellow-500" />
              <p className="text-2xl font-bold">{alertCounts.warning}</p>
              <p className="text-sm text-muted-foreground">Warnings</p>
            </CardContent>
          </Card>
          <Card
            className={cn(
              "cursor-pointer transition-colors",
              filter === "info" && "ring-2 ring-primary"
            )}
            onClick={() => setFilter("info")}
          >
            <CardContent className="p-4 text-center">
              <Info className="h-6 w-6 mx-auto mb-2 text-blue-500" />
              <p className="text-2xl font-bold">{alertCounts.info}</p>
              <p className="text-sm text-muted-foreground">Info</p>
            </CardContent>
          </Card>
        </div>

        {/* Alert List */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Bell className="h-5 w-5" />
                Alert History
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm">
                  <Filter className="h-4 w-4 mr-2" />
                  Filter
                </Button>
                <Button variant="outline" size="sm">
                  Mark All Read
                </Button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {filteredAlerts.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-500" />
                <p className="text-lg font-medium">No alerts to display</p>
                <p className="text-sm">All systems operating normally</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredAlerts.map((alert, index) => (
                  <div
                    key={`${alert.severity}-${alert.message.slice(0, 20)}-${index}`}
                    className={cn(
                      "flex items-start gap-4 p-4 rounded-lg border transition-colors",
                      getSeverityColor(alert.severity),
                      alert.acknowledged && "opacity-60"
                    )}
                  >
                    <div className="mt-0.5">{getAlertIcon(alert.severity)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge
                          variant={
                            alert.severity === "critical"
                              ? "error"
                              : alert.severity === "warning"
                              ? "warning"
                              : "secondary"
                          }
                        >
                          {alert.severity}
                        </Badge>
                        {alert.source && (
                          <Badge variant="outline">{alert.source}</Badge>
                        )}
                        {alert.acknowledged && (
                          <Badge variant="secondary">Acknowledged</Badge>
                        )}
                      </div>
                      <p className="font-medium">{alert.message}</p>
                      {alert.recommendation && (
                        <p className="text-sm opacity-80 mt-1">
                          {alert.recommendation}
                        </p>
                      )}
                      {alert.timestamp && (
                        <p className="text-xs opacity-60 mt-2 flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {new Date(alert.timestamp).toLocaleString()}
                        </p>
                      )}
                    </div>
                    {!alert.acknowledged && (
                      <Button variant="ghost" size="sm">
                        Acknowledge
                      </Button>
                    )}
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
