"use client";

import { Alert } from "@/lib/api";
import { cn, getSeverityColor } from "@/lib/utils";
import { AlertTriangle, AlertCircle, Info, XCircle } from "lucide-react";

interface AlertListProps {
  alerts: Alert[];
  maxItems?: number;
}

export function AlertList({ alerts, maxItems = 5 }: AlertListProps) {
  const displayAlerts = alerts.slice(0, maxItems);

  const getAlertIcon = (severity: string) => {
    switch (severity) {
      case "critical":
        return <XCircle className="h-4 w-4" />;
      case "high":
        return <AlertCircle className="h-4 w-4" />;
      case "warning":
        return <AlertTriangle className="h-4 w-4" />;
      default:
        return <Info className="h-4 w-4" />;
    }
  };

  if (alerts.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground">
        <Info className="h-5 w-5 mr-2" />
        No active alerts
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {displayAlerts.map((alert, index) => (
        <div
          key={index}
          className={cn(
            "flex items-start gap-3 p-3 rounded-lg border",
            getSeverityColor(alert.severity)
          )}
        >
          <div className="mt-0.5">{getAlertIcon(alert.severity)}</div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium">{alert.message}</p>
            {alert.recommendation && (
              <p className="text-xs opacity-80 mt-1">{alert.recommendation}</p>
            )}
            {alert.source && (
              <p className="text-xs opacity-60 mt-1">Source: {alert.source}</p>
            )}
          </div>
        </div>
      ))}
      {alerts.length > maxItems && (
        <p className="text-xs text-muted-foreground text-center py-2">
          +{alerts.length - maxItems} more alerts
        </p>
      )}
    </div>
  );
}
