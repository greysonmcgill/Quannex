"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertList } from "@/components/dashboard/alert-list";
import { ChannelMetricsComponent } from "@/components/dashboard/channel-metrics";
import { KPICard } from "@/components/dashboard/kpi-card";
import { PipelineFunnel } from "@/components/dashboard/pipeline-funnel";
import { QueueStatusComponent } from "@/components/dashboard/queue-status";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createEmptyOperationsData, fetchOperations, OperationsData } from "@/lib/api";
import { formatNumber, formatPercent } from "@/lib/utils";
import { Activity, CheckCircle2, Layers, MessageSquare, Users } from "lucide-react";

export default function OperationsPage() {
  const [data, setData] = useState<OperationsData>(createEmptyOperationsData());
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      setData(await fetchOperations());
    } catch (err) {
      setData(createEmptyOperationsData());
      setError(err instanceof Error ? err.message : "Unable to load operations dashboard");
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

  const totalAccounts = data.pipeline.ingested?.count || 0;
  const bottleneckAlerts = data.bottlenecks.map((item) => ({
    severity: item.severity,
    source: "operations",
    message: item.issue,
    recommendation: item.recommendation,
  }));

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Operations Dashboard"
        alertCount={bottleneckAlerts.length}
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
              The operations dashboard is showing empty-state data because the API request failed.
              {` ${error}`}
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
          <KPICard title="Accounts in Pipeline" value={formatNumber(totalAccounts)} icon={<Users className="h-4 w-4" />} />
          <KPICard title="Accounts/Hour" value={formatNumber(data.throughput.accounts_per_hour)} icon={<Activity className="h-4 w-4" />} />
          <KPICard title="Contacts/Hour" value={formatNumber(data.throughput.contacts_per_hour)} icon={<MessageSquare className="h-4 w-4" />} />
          <KPICard title="Resolutions/Hour" value={formatNumber(data.throughput.resolutions_per_hour)} icon={<CheckCircle2 className="h-4 w-4" />} />
          <KPICard title="Capacity Utilization" value={formatPercent(data.throughput.current_capacity_utilization)} icon={<Layers className="h-4 w-4" />} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Pipeline Funnel</CardTitle>
            </CardHeader>
            <CardContent>
              <PipelineFunnel pipeline={data.pipeline} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Queue Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <QueueStatusComponent queues={data.queues} />
              <div className="border-t pt-6">
                <AlertList alerts={bottleneckAlerts} maxItems={6} />
              </div>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Channel Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <ChannelMetricsComponent channels={data.channels} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
