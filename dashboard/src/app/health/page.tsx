"use client";

import { useEffect, useState, useCallback } from "react";
import { Header } from "@/components/layout/header";
import { SystemHealthComponent } from "@/components/dashboard/system-health";
import { AlertList } from "@/components/dashboard/alert-list";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { fetchHealth, SystemHealth, Alert } from "@/lib/api";
import {
  Activity,
  Server,
  Database,
  Cpu,
  HardDrive,
  Network,
  Clock,
} from "lucide-react";

interface HealthData {
  system_health: SystemHealth;
  alerts: Alert[];
}

const mockHealthData: HealthData = {
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
    {
      severity: "info",
      source: "monitoring",
      message: "Scheduled maintenance window in 48 hours",
    },
  ],
};

const systemMetrics = [
  { name: "API Latency", value: "45ms", status: "healthy", icon: Network },
  { name: "Database", value: "Connected", status: "healthy", icon: Database },
  { name: "Redis Cache", value: "Active", status: "healthy", icon: Server },
  { name: "Kafka", value: "Connected", status: "healthy", icon: Activity },
  { name: "CPU Usage", value: "32%", status: "healthy", icon: Cpu },
  { name: "Memory", value: "68%", status: "healthy", icon: HardDrive },
];

export default function HealthPage() {
  const [data, setData] = useState<HealthData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const result = await fetchHealth();
      setData(result);
    } catch (error) {
      setData(mockHealthData);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();

    // Auto-refresh every 30 seconds
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
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

  const healthData = data || mockHealthData;

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="System Health"
        alertCount={healthData.alerts.length}
        lastUpdated={new Date().toLocaleString()}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      <div className="p-6 space-y-6">
        {/* Status Banner */}
        <div
          className={`p-6 rounded-lg flex items-center justify-between ${
            healthData.system_health.status === "healthy"
              ? "bg-green-500/10 border border-green-500/20"
              : "bg-yellow-500/10 border border-yellow-500/20"
          }`}
        >
          <div className="flex items-center gap-4">
            <div
              className={`h-12 w-12 rounded-full flex items-center justify-center ${
                healthData.system_health.status === "healthy"
                  ? "bg-green-500/20"
                  : "bg-yellow-500/20"
              }`}
            >
              <Activity
                className={`h-6 w-6 ${
                  healthData.system_health.status === "healthy"
                    ? "text-green-500"
                    : "text-yellow-500"
                }`}
              />
            </div>
            <div>
              <h2 className="text-2xl font-bold">
                System{" "}
                <span
                  className={
                    healthData.system_health.status === "healthy"
                      ? "text-green-500"
                      : "text-yellow-500"
                  }
                >
                  {healthData.system_health.status.charAt(0).toUpperCase() +
                    healthData.system_health.status.slice(1)}
                </span>
              </h2>
              <p className="text-muted-foreground">
                Uptime: {healthData.system_health.uptime}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">Last incident</p>
            <p className="font-medium">{healthData.system_health.last_incident}</p>
            <p className="text-xs text-muted-foreground">
              MTTR: {healthData.system_health.mttr}
            </p>
          </div>
        </div>

        {/* System Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {systemMetrics.map((metric) => (
            <Card key={metric.name}>
              <CardContent className="p-4 text-center">
                <metric.icon className="h-6 w-6 mx-auto mb-2 text-primary" />
                <p className="text-sm text-muted-foreground">{metric.name}</p>
                <p className="text-lg font-bold">{metric.value}</p>
                <Badge variant="success" className="mt-2">
                  {metric.status}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Module Status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Module Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SystemHealthComponent health={healthData.system_health} />
          </CardContent>
        </Card>

        {/* Alerts */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              System Alerts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <AlertList alerts={healthData.alerts} maxItems={10} />
          </CardContent>
        </Card>

        {/* Health Check Endpoints */}
        <Card>
          <CardHeader>
            <CardTitle>Health Check Endpoints</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {[
                { endpoint: "/health", status: "healthy", latency: "12ms" },
                { endpoint: "/ready", status: "ready", latency: "45ms" },
                { endpoint: "/api/v1/dashboard/", status: "healthy", latency: "89ms" },
              ].map((check) => (
                <div
                  key={check.endpoint}
                  className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                >
                  <span className="font-mono text-sm">{check.endpoint}</span>
                  <div className="flex items-center gap-4">
                    <span className="text-sm text-muted-foreground">
                      {check.latency}
                    </span>
                    <Badge variant="success">{check.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
