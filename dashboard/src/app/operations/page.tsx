"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { KPICard } from "@/components/dashboard/kpi-card";
import { PipelineFunnel } from "@/components/dashboard/pipeline-funnel";
import { ChannelMetricsComponent } from "@/components/dashboard/channel-metrics";
import { QueueStatusComponent } from "@/components/dashboard/queue-status";
import { AlertList } from "@/components/dashboard/alert-list";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatNumber, formatPercent } from "@/lib/utils";
import { fetchOperations, OperationsData, Alert } from "@/lib/api";
import {
  Users,
  MessageSquare,
  CheckCircle2,
  Clock,
  Activity,
  Layers,
} from "lucide-react";

const mockOperationsData: OperationsData = {
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
    sms: { attempts: 250000, responses: 37500, conversions: 20000, response_rate: 0.15, conversion_rate: 0.08, cost_per_contact: 0.02 },
    email: { attempts: 500000, responses: 60000, conversions: 25000, response_rate: 0.12, conversion_rate: 0.05, cost_per_contact: 0.01 },
    voice: { attempts: 75000, responses: 18750, conversions: 11250, response_rate: 0.25, conversion_rate: 0.15, cost_per_contact: 0.15 },
    digital: { attempts: 100000, responses: 18000, conversions: 10000, response_rate: 0.18, conversion_rate: 0.10, cost_per_contact: 0.03 },
  },
  queues: {
    contact_queue: { depth: 15000, processing_rate: 500, estimated_clear_time: "30 minutes" },
    payment_queue: { depth: 2500, processing_rate: 100, estimated_clear_time: "25 minutes" },
    enrichment_queue: { depth: 5000, processing_rate: 1000, estimated_clear_time: "5 minutes" },
  },
  bottlenecks: [
    { location: "contact_queue", severity: "warning", issue: "Queue depth elevated - 15,000 accounts pending", recommendation: "Scale outreach capacity" },
  ],
  throughput: {
    accounts_per_hour: 5000,
    contacts_per_hour: 15000,
    resolutions_per_hour: 500,
    payments_per_hour: 200,
    current_capacity_utilization: 0.72,
  },
};

export default function OperationsPage() {
  const [data, setData] = useState<OperationsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const result = await fetchOperations();
      setData(result);
    } catch (error) {
      setData(mockOperationsData);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

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

  const opsData = data || mockOperationsData;
  const bottleneckAlerts: Alert[] = opsData.bottlenecks.map((b) => ({
    severity: b.severity,
    source: "operations",
    message: b.issue,
    recommendation: b.recommendation,
  }));

  const totalAccounts = Object.values(opsData.pipeline).reduce(
    (sum, stage) => sum + (stage.count || 0),
    0
  );

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Operations Dashboard"
        alertCount={opsData.bottlenecks.length}
        lastUpdated={new Date(opsData.generated_at).toLocaleString()}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      <div className="p-6 space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <KPICard
            title="Accounts in Pipeline"
            value={formatNumber(totalAccounts)}
            icon={<Users className="h-4 w-4" />}
          />
          <KPICard
            title="Accounts/Hour"
            value={formatNumber(opsData.throughput.accounts_per_hour)}
            icon={<Activity className="h-4 w-4" />}
          />
          <KPICard
            title="Contacts/Hour"
            value={formatNumber(opsData.throughput.contacts_per_hour)}
            icon={<MessageSquare className="h-4 w-4" />}
          />
          <KPICard
            title="Resolutions/Hour"
            value={formatNumber(opsData.throughput.resolutions_per_hour)}
            icon={<CheckCircle2 className="h-4 w-4" />}
          />
          <KPICard
            title="Capacity Utilization"
            value={formatPercent(opsData.throughput.current_capacity_utilization)}
            icon={<Layers className="h-4 w-4" />}
            description="Target: 75-85%"
          />
        </div>

        {/* Pipeline and Queues */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                Pipeline Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <PipelineFunnel pipeline={opsData.pipeline} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                Queue Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <QueueStatusComponent queues={opsData.queues} />

              {opsData.bottlenecks.length > 0 && (
                <div className="mt-6 pt-6 border-t">
                  <h4 className="font-medium mb-3">Active Bottlenecks</h4>
                  <AlertList alerts={bottleneckAlerts} />
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Channel Performance */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Channel Performance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ChannelMetricsComponent channels={opsData.channels} />
          </CardContent>
        </Card>

        {/* Throughput Details */}
        <Card>
          <CardHeader>
            <CardTitle>Throughput Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="p-4 bg-muted/50 rounded-lg text-center">
                <p className="text-3xl font-bold text-primary">
                  {formatNumber(opsData.throughput.accounts_per_hour)}
                </p>
                <p className="text-sm text-muted-foreground">Accounts/Hour</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg text-center">
                <p className="text-3xl font-bold text-blue-500">
                  {formatNumber(opsData.throughput.contacts_per_hour)}
                </p>
                <p className="text-sm text-muted-foreground">Contacts/Hour</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg text-center">
                <p className="text-3xl font-bold text-green-500">
                  {formatNumber(opsData.throughput.resolutions_per_hour)}
                </p>
                <p className="text-sm text-muted-foreground">Resolutions/Hour</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg text-center">
                <p className="text-3xl font-bold text-purple-500">
                  {formatNumber(opsData.throughput.payments_per_hour)}
                </p>
                <p className="text-sm text-muted-foreground">Payments/Hour</p>
              </div>
              <div className="p-4 bg-muted/50 rounded-lg text-center">
                <p className="text-3xl font-bold text-orange-500">
                  {formatPercent(opsData.throughput.current_capacity_utilization)}
                </p>
                <p className="text-sm text-muted-foreground">Capacity Used</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
