"use client";

import { useCallback, useEffect, useState } from "react";
import { ComplianceGauge } from "@/components/dashboard/compliance-gauge";
import { KPICard } from "@/components/dashboard/kpi-card";
import { ViolationsTable } from "@/components/dashboard/violations-table";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { createEmptyComplianceData, ComplianceData, fetchCompliance } from "@/lib/api";
import { FileCheck, MapPin, Shield, AlertTriangle } from "lucide-react";

export default function CompliancePage() {
  const [data, setData] = useState<ComplianceData>(createEmptyComplianceData());
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      setData(await fetchCompliance());
    } catch (err) {
      setData(createEmptyComplianceData());
      setError(err instanceof Error ? err.message : "Unable to load compliance dashboard");
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
        title="Compliance Dashboard"
        alertCount={data.violations.total_30d}
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
              Compliance data is currently unavailable, so this page is showing an empty state.
              {` ${error}`}
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <KPICard title="Overall Compliance" value={`${data.overall_score.score.toFixed(1)}%`} icon={<Shield className="h-4 w-4" />} description={data.overall_score.rating} />
          <KPICard title="Audit Readiness" value={`${data.audit_readiness.score.toFixed(1)}%`} icon={<FileCheck className="h-4 w-4" />} description={data.audit_readiness.overall_readiness} />
          <KPICard title="Violations (30d)" value={data.violations.total_30d.toString()} icon={<AlertTriangle className="h-4 w-4" />} />
          <KPICard title="States Compliant" value={`${data.state_compliance.fully_compliant}`} icon={<MapPin className="h-4 w-4" />} description={`${data.state_compliance.requires_attention} need review`} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Compliance Score</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex justify-center">
                <ComplianceGauge
                  score={data.overall_score.score}
                  rating={data.overall_score.rating}
                  size="lg"
                />
              </div>
              <div className="space-y-3">
                {Object.entries(data.overall_score.components).map(([name, score]) => (
                  <div key={name}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span className="uppercase">{name.replace("_", " ")}</span>
                      <span>{score}%</span>
                    </div>
                    <Progress value={score} className="h-2" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle>Regulation Status</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.keys(data.regulation_status).length > 0 ? (
                Object.entries(data.regulation_status).map(([name, status]) => (
                  <div key={name} className="rounded-lg bg-muted/50 p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium uppercase">{name.replace("_", " ")}</span>
                      <Badge variant={status.status === "compliant" ? "success" : "warning"}>
                        {status.status}
                      </Badge>
                    </div>
                    <div className="text-sm text-muted-foreground space-y-1">
                      {Object.entries(status).map(([key, value]) =>
                        key === "status" ? null : (
                          <div key={key} className="flex justify-between gap-3">
                            <span>{key.replace(/_/g, " ")}</span>
                            <span>{String(value)}</span>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-sm text-muted-foreground py-12 text-center col-span-full">
                  Regulation status will populate as compliance events are recorded.
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Recent Compliance Events</CardTitle>
          </CardHeader>
          <CardContent>
            <ViolationsTable violations={data.violations.recent} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
