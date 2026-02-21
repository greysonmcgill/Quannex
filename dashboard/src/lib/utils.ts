import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number, compact = false): string {
  if (compact) {
    if (value >= 1_000_000) {
      return `$${(value / 1_000_000).toFixed(1)}M`;
    }
    if (value >= 1_000) {
      return `$${(value / 1_000).toFixed(0)}K`;
    }
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: value < 1 ? 2 : 0,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number, decimals = 1): string {
  // If value is already > 1, treat it as a raw percentage
  if (value > 1) {
    return `${value.toFixed(decimals)}%`;
  }
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function getChangeColor(direction: string): string {
  switch (direction) {
    case "up":
      return "text-green-500";
    case "down":
      return "text-red-500";
    default:
      return "text-muted-foreground";
  }
}

export function getSeverityColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case "critical":
      return "bg-red-500/10 border-red-500/20 text-red-500";
    case "high":
      return "bg-orange-500/10 border-orange-500/20 text-orange-500";
    case "warning":
      return "bg-yellow-500/10 border-yellow-500/20 text-yellow-500";
    case "info":
      return "bg-blue-500/10 border-blue-500/20 text-blue-500";
    default:
      return "bg-muted/50 border-muted";
  }
}

export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case "healthy":
    case "performing":
    case "compliant":
      return "text-green-500";
    case "degraded":
    case "warning":
    case "review":
      return "text-yellow-500";
    case "down":
    case "critical":
    case "non_compliant":
      return "text-red-500";
    default:
      return "text-muted-foreground";
  }
}
