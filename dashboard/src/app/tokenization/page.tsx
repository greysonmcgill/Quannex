"use client";

import { useCallback, useEffect, useState } from "react";
import { KPICard } from "@/components/dashboard/kpi-card";
import { PoolTable } from "@/components/dashboard/pool-table";
import { TrancheChart } from "@/components/dashboard/tranche-chart";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createEmptyTokenizationData, fetchTokenization, TokenizationData } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { BarChart3, Coins, Wallet } from "lucide-react";

export default function TokenizationPage() {
  const [data, setData] = useState<TokenizationData>(createEmptyTokenizationData());
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      setData(await fetchTokenization());
    } catch (err) {
      setData(createEmptyTokenizationData());
      setError(err instanceof Error ? err.message : "Unable to load tokenization view");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Tokenization Dashboard"
        lastUpdated={new Date(data.generated_at).toLocaleString()}
        onRefresh={() => {
          setIsRefreshing(true);
          loadData();
        }}
        isRefreshing={isRefreshing}
      />

      <div className="p-6 space-y-6">
        {error && (
          <Card className="border-yellow-500/30 bg-yellow-500/5">
            <CardContent className="p-4 text-sm text-yellow-700 dark:text-yellow-400">
              Tokenization is currently derived from real account data and may be empty until
              accounts exist. {error}
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-4">
          <KPICard title="Total Face Value" value={formatCurrency(data.portfolio_summary.total_face_value, true)} icon={<Coins className="h-4 w-4" />} />
          <KPICard title="Total NAV" value={formatCurrency(data.portfolio_summary.total_nav, true)} icon={<Wallet className="h-4 w-4" />} />
          <KPICard title="Active Pools" value={data.portfolio_summary.total_pools.toString()} icon={<BarChart3 className="h-4 w-4" />} />
          <KPICard title="Average Yield" value={formatPercent(data.portfolio_summary.avg_yield)} />
          <KPICard title="Active Tranches" value={data.portfolio_summary.active_tranches.toString()} />
          <KPICard title="Default Rate" value={formatPercent(data.portfolio_summary.default_rate)} />
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Derived Tranche Structure</CardTitle>
          </CardHeader>
          <CardContent>
            <TrancheChart tranches={data.tranches} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Debt-Type Pools</CardTitle>
          </CardHeader>
          <CardContent>
            <PoolTable pools={data.pools} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
