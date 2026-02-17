"use client";

import { PipelineStage } from "@/lib/api";
import { formatNumber, formatPercent } from "@/lib/utils";

interface PipelineFunnelProps {
  pipeline: Record<string, PipelineStage>;
}

const stageColors: Record<string, string> = {
  ingested: "bg-blue-500",
  enriched: "bg-cyan-500",
  scored: "bg-teal-500",
  contacted: "bg-green-500",
  negotiating: "bg-yellow-500",
  payment_pending: "bg-orange-500",
  resolved: "bg-emerald-500",
};

const stageLabels: Record<string, string> = {
  ingested: "Ingested",
  enriched: "Enriched",
  scored: "Scored",
  contacted: "Contacted",
  negotiating: "Negotiating",
  payment_pending: "Payment Pending",
  resolved: "Resolved",
};

export function PipelineFunnel({ pipeline }: PipelineFunnelProps) {
  const stages = Object.entries(pipeline);
  const maxCount = Math.max(...stages.map(([, data]) => data.count || 0), 1);

  return (
    <div className="space-y-3">
      {stages.map(([stage, data], index) => {
        const width = Math.max(((data.count || 0) / maxCount) * 100, 10);
        return (
          <div key={stage} className="space-y-1">
            <div className="flex justify-between text-sm">
              <span className="font-medium">{stageLabels[stage] || stage}</span>
              <span className="text-muted-foreground">
                {formatNumber(data.count || 0)} accounts
              </span>
            </div>
            <div className="relative">
              <div className="h-8 bg-muted rounded-md overflow-hidden">
                <div
                  className={`h-full ${stageColors[stage] || "bg-primary"} transition-all duration-500 flex items-center justify-end pr-2`}
                  style={{ width: `${width}%` }}
                >
                  <span className="text-xs text-white font-medium">
                    {formatPercent(data.conversion_rate)}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Avg time: {data.avg_time_in_stage}</span>
              <span>Conv: {formatPercent(data.conversion_rate)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
