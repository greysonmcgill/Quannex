"use client";

import { SystemHealth } from "@/lib/api";
import { getStatusColor } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  Activity,
  Clock,
} from "lucide-react";

interface SystemHealthProps {
  health: SystemHealth;
}

export function SystemHealthComponent({ health }: SystemHealthProps) {
  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case "healthy":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "degraded":
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      default:
        return <XCircle className="h-4 w-4 text-red-500" />;
    }
  };

  return (
    <div className="space-y-4">
      {/* Overall Status */}
      <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
        <div className="flex items-center gap-3">
          <Activity className="h-5 w-5 text-primary" />
          <div>
            <p className="font-medium">System Status</p>
            <p className="text-sm text-muted-foreground">
              Uptime: {health.uptime}
            </p>
          </div>
        </div>
        <Badge
          variant={health.status === "healthy" ? "success" : "warning"}
          className="uppercase"
        >
          {health.status}
        </Badge>
      </div>

      {/* Module Status */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        {Object.entries(health.modules).map(([module, status]) => (
          <div
            key={module}
            className="flex items-center gap-2 p-2 bg-muted/30 rounded"
          >
            {getStatusIcon(status)}
            <span className="text-sm capitalize">
              {module.replace("_", " ")}
            </span>
          </div>
        ))}
      </div>

      {/* Incident Info */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground pt-2 border-t">
        <div className="flex items-center gap-1">
          <Clock className="h-4 w-4" />
          <span>Last incident: {health.last_incident}</span>
        </div>
        <div>MTTR: {health.mttr}</div>
      </div>
    </div>
  );
}
