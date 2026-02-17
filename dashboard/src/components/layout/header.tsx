"use client";

import { Bell, RefreshCw, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface HeaderProps {
  title: string;
  alertCount?: number;
  lastUpdated?: string;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export function Header({
  title,
  alertCount = 0,
  lastUpdated,
  onRefresh,
  isRefreshing,
}: HeaderProps) {
  return (
    <header className="sticky top-0 z-30 h-16 bg-background/95 backdrop-blur border-b flex items-center justify-between px-6">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {lastUpdated && (
          <p className="text-xs text-muted-foreground">
            Last updated: {lastUpdated}
          </p>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* Refresh */}
        {onRefresh && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isRefreshing}
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${isRefreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        )}

        {/* Alerts */}
        <Button variant="outline" size="icon" className="relative">
          <Bell className="h-4 w-4" />
          {alertCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center text-xs"
            >
              {alertCount > 9 ? "9+" : alertCount}
            </Badge>
          )}
        </Button>

        {/* User */}
        <Button variant="outline" size="icon">
          <User className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
