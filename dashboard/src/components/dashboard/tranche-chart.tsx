"use client";

import { TrancheData } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";

interface TrancheChartProps {
  tranches: Record<string, TrancheData>;
}

const trancheColors: Record<string, string> = {
  senior: "bg-blue-500",
  mezzanine: "bg-yellow-500",
  junior: "bg-orange-500",
  equity: "bg-red-500",
};

const trancheLabels: Record<string, string> = {
  senior: "Senior",
  mezzanine: "Mezzanine",
  junior: "Junior",
  equity: "Equity",
};

export function TrancheChart({ tranches }: TrancheChartProps) {
  const totalValue = Object.values(tranches).reduce(
    (sum, t) => sum + t.total_value,
    0
  );

  return (
    <div className="space-y-4">
      {/* Stacked bar */}
      <div className="h-8 flex rounded-lg overflow-hidden">
        {Object.entries(tranches).map(([name, data]) => {
          const width = (data.total_value / totalValue) * 100;
          return (
            <div
              key={name}
              className={`${trancheColors[name]} transition-all duration-500 flex items-center justify-center`}
              style={{ width: `${width}%` }}
            >
              {width > 10 && (
                <span className="text-xs text-white font-medium">
                  {formatPercent(width / 100, 0)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend and details */}
      <div className="grid grid-cols-2 gap-4">
        {Object.entries(tranches).map(([name, data]) => (
          <div
            key={name}
            className="flex items-start gap-3 p-3 bg-muted/50 rounded-lg"
          >
            <div
              className={`w-3 h-3 rounded-full mt-1 ${trancheColors[name]}`}
            />
            <div className="flex-1">
              <div className="flex justify-between items-center">
                <span className="font-medium">{trancheLabels[name]}</span>
                <span className="text-xs bg-muted px-2 py-0.5 rounded">
                  {data.rating}
                </span>
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                {formatCurrency(data.total_value, true)}
              </div>
              <div className="flex gap-4 mt-2 text-xs">
                <span>
                  Yield:{" "}
                  <span className="text-green-500 font-medium">
                    {formatPercent(data.avg_yield)}
                  </span>
                </span>
                <span>
                  Default:{" "}
                  <span className="text-red-500 font-medium">
                    {formatPercent(data.default_rate)}
                  </span>
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
