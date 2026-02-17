"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, getChangeColor } from "@/lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KPICardProps {
  title: string;
  value: string;
  change?: {
    value: number;
    direction: string;
  };
  icon?: React.ReactNode;
  description?: string;
  className?: string;
}

export function KPICard({
  title,
  value,
  change,
  icon,
  description,
  className,
}: KPICardProps) {
  const ChangeIcon =
    change?.direction === "up"
      ? TrendingUp
      : change?.direction === "down"
      ? TrendingDown
      : Minus;

  return (
    <Card className={cn("relative overflow-hidden", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        {icon && <div className="text-muted-foreground">{icon}</div>}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {change && (
          <div
            className={cn(
              "flex items-center gap-1 text-xs mt-1",
              getChangeColor(change.direction)
            )}
          >
            <ChangeIcon className="h-3 w-3" />
            <span>
              {(change.value * 100).toFixed(1)}%{" "}
              {change.direction === "up" ? "increase" : change.direction === "down" ? "decrease" : "no change"}
            </span>
          </div>
        )}
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}
