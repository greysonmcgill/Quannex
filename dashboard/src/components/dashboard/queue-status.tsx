"use client";

import { QueueStatus } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { Clock, Layers, Zap } from "lucide-react";

interface QueueStatusProps {
  queues: Record<string, QueueStatus>;
}

const queueLabels: Record<string, string> = {
  contact_queue: "Contact Queue",
  payment_queue: "Payment Queue",
  enrichment_queue: "Enrichment Queue",
};

const queueIcons: Record<string, React.ReactNode> = {
  contact_queue: <Layers className="h-4 w-4" />,
  payment_queue: <Zap className="h-4 w-4" />,
  enrichment_queue: <Clock className="h-4 w-4" />,
};

export function QueueStatusComponent({ queues }: QueueStatusProps) {
  return (
    <div className="space-y-4">
      {Object.entries(queues).map(([name, queue]) => {
        const capacity = queue.processing_rate * 60; // 1 hour capacity
        const utilization = Math.min((queue.depth / capacity) * 100, 100);

        return (
          <div key={name} className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">
                  {queueIcons[name]}
                </span>
                <span className="font-medium">{queueLabels[name] || name}</span>
              </div>
              <span className="text-sm text-muted-foreground">
                {queue.estimated_clear_time}
              </span>
            </div>

            <Progress value={utilization} className="h-2" />

            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Depth: {formatNumber(queue.depth)}</span>
              <span>Rate: {formatNumber(queue.processing_rate)}/min</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
