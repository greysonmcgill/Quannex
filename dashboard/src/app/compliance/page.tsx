"use client";

import { useEffect, useState, useCallback } from "react";
import { Header } from "@/components/layout/header";
import { KPICard } from "@/components/dashboard/kpi-card";
import { ComplianceGauge } from "@/components/dashboard/compliance-gauge";
import { ViolationsTable } from "@/components/dashboard/violations-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { formatPercent } from "@/lib/utils";
import { fetchCompliance, ComplianceData } from "@/lib/api";
import {
  Shield,
  AlertTriangle,
  CheckCircle2,
  FileCheck,
  MapPin,
  Clock,
} from "lucide-react";

const mockComplianceData: ComplianceData = {
  generated_at: new Date().toISOString(),
  overall_score: {
    score: 98.5,
    rating: "Excellent",
    trend: "stable",
    components: {
      fdcpa: 99.2,
      tcpa: 97.8,
      regulation_f: 99.0,
      state_laws: 98.0,
    },
  },
  audit_readiness: {
    overall_readiness: "high",
    score: 95,
    checklist: {
      interaction_logs: { status: "complete", coverage: 100 },
      consent_records: { status: "complete", coverage: 100 },
      disclosure_delivery: { status: "complete", coverage: 99.8 },
      dispute_handling: { status: "complete", coverage: 100 },
      call_recordings: { status: "complete", coverage: 98.5 },
    },
    last_audit: "2025-11-15",
    next_scheduled: "2026-05-15",
  },
  violations: {
    total_30d: 3,
    total_90d: 8,
    by_type: {
      timing: 1,
      disclosure: 1,
      frequency: 1,
    },
    by_severity: {
      critical: 0,
      major: 1,
      minor: 2,
    },
    recent: [
      {
        id: "V001",
        date: "2026-01-15",
        type: "timing",
        description: "Contact attempt at 8:58 PM (within 2 min of cutoff)",
        severity: "minor",
        resolution: "System clock sync adjusted",
      },
      {
        id: "V002",
        date: "2026-01-12",
        type: "disclosure",
        description: "Mini-Miranda missing from voicemail",
        severity: "major",
        resolution: "Script template updated",
      },
      {
        id: "V003",
        date: "2026-01-08",
        type: "frequency",
        description: "8th contact attempt in 7-day period",
        severity: "minor",
        resolution: "Contact governor recalibrated",
      },
    ],
  },
  state_compliance: {
    fully_compliant: 47,
    requires_attention: 3,
    attention_states: ["CA", "NY", "MA"],
    details: {
      CA: { status: "compliant", license_expiry: "2026-06-30" },
      NY: { status: "review", note: "New regulation effective 2026-03-01" },
      MA: { status: "compliant", license_expiry: "2026-04-15" },
    },
  },
  regulation_status: {
    fdcpa: {
      status: "compliant",
      last_review: "2026-01-01",
      automation_coverage: 100,
    },
    tcpa: {
      status: "compliant",
      consent_rate: 99.5,
      dnc_compliance: 100,
    },
    regulation_f: {
      status: "compliant",
      "7_in_7_compliance": 100,
      model_notice_usage: 100,
    },
    cfpb_guidance: {
      status: "monitoring",
      pending_changes: 2,
    },
  },
};

export default function CompliancePage() {
  const [data, setData] = useState<ComplianceData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const result = await fetchCompliance();
      setData(result);
    } catch (error) {
      setData(mockComplianceData);
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

  const complianceData = data || mockComplianceData;

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Compliance Dashboard"
        alertCount={complianceData.violations.total_30d}
        lastUpdated={new Date(complianceData.generated_at).toLocaleString()}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      <div className="p-6 space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title="Overall Compliance"
            value={`${complianceData.overall_score.score}%`}
            icon={<Shield className="h-4 w-4" />}
            description={complianceData.overall_score.rating}
          />
          <KPICard
            title="Audit Readiness"
            value={`${complianceData.audit_readiness.score}%`}
            icon={<FileCheck className="h-4 w-4" />}
            description={complianceData.audit_readiness.overall_readiness}
          />
          <KPICard
            title="Violations (30d)"
            value={complianceData.violations.total_30d.toString()}
            icon={<AlertTriangle className="h-4 w-4" />}
            description={`${complianceData.violations.total_90d} in 90 days`}
          />
          <KPICard
            title="States Compliant"
            value={`${complianceData.state_compliance.fully_compliant}/50`}
            icon={<MapPin className="h-4 w-4" />}
            description={`${complianceData.state_compliance.requires_attention} need attention`}
          />
        </div>

        {/* Compliance Score and Regulation Status */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Overall Compliance Score</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center">
              <ComplianceGauge
                score={complianceData.overall_score.score}
                rating={complianceData.overall_score.rating}
                size="lg"
              />
              <div className="mt-6 w-full space-y-3">
                {Object.entries(complianceData.overall_score.components).map(
                  ([regulation, score]) => (
                    <div key={regulation}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="uppercase">{regulation.replace("_", " ")}</span>
                        <span>{score}%</span>
                      </div>
                      <Progress value={score} className="h-2" />
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Regulation Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(complianceData.regulation_status).map(
                  ([regulation, status]) => (
                    <div
                      key={regulation}
                      className="p-4 bg-muted/50 rounded-lg"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium uppercase">
                          {regulation.replace("_", " ")}
                        </span>
                        <Badge
                          variant={
                            status.status === "compliant" ? "success" : "warning"
                          }
                        >
                          {status.status}
                        </Badge>
                      </div>
                      <div className="space-y-1 text-sm text-muted-foreground">
                        {status.automation_coverage !== undefined && (
                          <p>Automation: {status.automation_coverage}%</p>
                        )}
                        {status.consent_rate !== undefined && (
                          <p>Consent Rate: {status.consent_rate}%</p>
                        )}
                        {status.dnc_compliance !== undefined && (
                          <p>DNC Compliance: {status.dnc_compliance}%</p>
                        )}
                        {status["7_in_7_compliance"] !== undefined && (
                          <p>7-in-7 Compliance: {status["7_in_7_compliance"]}%</p>
                        )}
                        {status.pending_changes !== undefined && (
                          <p>Pending Changes: {status.pending_changes}</p>
                        )}
                        {status.last_review && (
                          <p>Last Review: {status.last_review}</p>
                        )}
                      </div>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Audit Readiness */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileCheck className="h-5 w-5" />
              Audit Readiness Checklist
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              {Object.entries(complianceData.audit_readiness.checklist).map(
                ([item, data]) => (
                  <div
                    key={item}
                    className="p-4 bg-muted/50 rounded-lg text-center"
                  >
                    <CheckCircle2 className="h-8 w-8 mx-auto text-green-500 mb-2" />
                    <p className="font-medium text-sm capitalize">
                      {item.replace("_", " ")}
                    </p>
                    <p className="text-2xl font-bold text-green-500">
                      {data.coverage}%
                    </p>
                    <Badge variant="success" className="mt-2">
                      {data.status}
                    </Badge>
                  </div>
                )
              )}
            </div>
            <div className="flex items-center gap-6 mt-6 pt-6 border-t text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                <span>Last Audit: {complianceData.audit_readiness.last_audit}</span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                <span>Next Scheduled: {complianceData.audit_readiness.next_scheduled}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Violations */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Recent Violations
              </div>
              <div className="flex gap-2">
                {Object.entries(complianceData.violations.by_severity).map(
                  ([severity, count]) => (
                    <Badge
                      key={severity}
                      variant={
                        severity === "critical"
                          ? "error"
                          : severity === "major"
                          ? "warning"
                          : "secondary"
                      }
                    >
                      {severity}: {count}
                    </Badge>
                  )
                )}
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ViolationsTable violations={complianceData.violations.recent} />
          </CardContent>
        </Card>

        {/* State Compliance */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MapPin className="h-5 w-5" />
              State Compliance Overview
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-6 bg-green-500/10 rounded-lg border border-green-500/20">
                <div className="text-4xl font-bold text-green-500">
                  {complianceData.state_compliance.fully_compliant}
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  States Fully Compliant
                </p>
              </div>
              <div className="p-6 bg-yellow-500/10 rounded-lg border border-yellow-500/20">
                <div className="text-4xl font-bold text-yellow-500">
                  {complianceData.state_compliance.requires_attention}
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  States Requiring Attention
                </p>
                <div className="flex gap-2 mt-3">
                  {complianceData.state_compliance.attention_states.map(
                    (state) => (
                      <Badge key={state} variant="warning">
                        {state}
                      </Badge>
                    )
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
