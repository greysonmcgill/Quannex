"use client";

import { ChannelMetrics as ChannelMetricsType } from "@/lib/api";
import { formatNumber, formatPercent, formatCurrency } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Mail, MessageSquare, Phone, Globe } from "lucide-react";

interface ChannelMetricsProps {
  channels: Record<string, ChannelMetricsType>;
}

const channelIcons: Record<string, React.ReactNode> = {
  sms: <MessageSquare className="h-5 w-5" />,
  email: <Mail className="h-5 w-5" />,
  voice: <Phone className="h-5 w-5" />,
  digital: <Globe className="h-5 w-5" />,
};

const channelColors: Record<string, string> = {
  sms: "text-green-500",
  email: "text-blue-500",
  voice: "text-purple-500",
  digital: "text-orange-500",
};

export function ChannelMetricsComponent({ channels }: ChannelMetricsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {Object.entries(channels).map(([channel, metrics]) => (
        <Card key={channel}>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <span className={channelColors[channel] || "text-primary"}>
                {channelIcons[channel]}
              </span>
              <span className="capitalize">{channel}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Response Rate</span>
                <span className="font-medium">
                  {formatPercent(metrics.response_rate)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Conversion Rate</span>
                <span className="font-medium">
                  {formatPercent(metrics.conversion_rate)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Cost/Contact</span>
                <span className="font-medium">
                  {formatCurrency(metrics.cost_per_contact)}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
