"use client";

import { Pool } from "@/lib/api";
import { formatCurrency, formatPercent, getStatusColor } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

interface PoolTableProps {
  pools: Pool[];
}

export function PoolTable({ pools }: PoolTableProps) {
  if (pools.length === 0) {
    return (
      <div className="py-10 text-center text-sm text-muted-foreground">
        Pools will appear here once accounts have been uploaded and grouped.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b">
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
              Pool ID
            </th>
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
              Asset Class
            </th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
              Face Value
            </th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
              NAV
            </th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
              Recovery
            </th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">
              Yield
            </th>
            <th className="text-center py-3 px-4 text-sm font-medium text-muted-foreground">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {pools.map((pool) => (
            <tr key={pool.pool_id} className="border-b hover:bg-muted/50">
              <td className="py-3 px-4">
                <span className="font-mono text-sm">{pool.pool_id}</span>
              </td>
              <td className="py-3 px-4 text-sm">{pool.asset_class}</td>
              <td className="py-3 px-4 text-right text-sm">
                {formatCurrency(pool.face_value, true)}
              </td>
              <td className="py-3 px-4 text-right text-sm">
                {formatCurrency(pool.nav, true)}
              </td>
              <td className="py-3 px-4 text-right text-sm">
                {formatPercent(pool.recovery_rate)}
              </td>
              <td className="py-3 px-4 text-right text-sm font-medium text-green-500">
                {formatPercent(pool.yield)}
              </td>
              <td className="py-3 px-4 text-center">
                <Badge
                  variant={pool.status === "performing" ? "success" : "warning"}
                >
                  {pool.status}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
