"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { KPICard } from "@/components/dashboard/kpi-card";
import { PoolTable } from "@/components/dashboard/pool-table";
import { TrancheChart } from "@/components/dashboard/tranche-chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { fetchTokenization, TokenizationData } from "@/lib/api";
import {
  Coins,
  TrendingUp,
  Users,
  BarChart3,
  ArrowUpDown,
  Wallet,
} from "lucide-react";

const mockTokenizationData: TokenizationData = {
  generated_at: new Date().toISOString(),
  portfolio_summary: {
    total_face_value: 25000000,
    total_nav: 18500000,
    total_pools: 12,
    active_tranches: 48,
    total_investors: 156,
    avg_yield: 0.18,
    default_rate: 0.12,
  },
  pools: [
    {
      pool_id: "BNPL-2026-Q1",
      asset_class: "BNPL Subprime",
      face_value: 5000000,
      nav: 3750000,
      recovery_rate: 0.52,
      yield: 0.22,
      status: "performing",
    },
    {
      pool_id: "SUB-2026-Q1",
      asset_class: "Subscriptions",
      face_value: 2000000,
      nav: 1400000,
      recovery_rate: 0.48,
      yield: 0.19,
      status: "performing",
    },
    {
      pool_id: "MIXED-2025-Q4",
      asset_class: "Mixed Micro",
      face_value: 3500000,
      nav: 2450000,
      recovery_rate: 0.45,
      yield: 0.17,
      status: "performing",
    },
    {
      pool_id: "MED-2025-Q4",
      asset_class: "Medical Debt",
      face_value: 4000000,
      nav: 2800000,
      recovery_rate: 0.42,
      yield: 0.16,
      status: "performing",
    },
    {
      pool_id: "UTIL-2025-Q3",
      asset_class: "Utility Arrears",
      face_value: 1500000,
      nav: 1050000,
      recovery_rate: 0.55,
      yield: 0.21,
      status: "performing",
    },
  ],
  tranches: {
    senior: {
      total_value: 12000000,
      avg_yield: 0.10,
      default_rate: 0.02,
      rating: "AA",
    },
    mezzanine: {
      total_value: 5000000,
      avg_yield: 0.18,
      default_rate: 0.08,
      rating: "BBB",
    },
    junior: {
      total_value: 2000000,
      avg_yield: 0.28,
      default_rate: 0.15,
      rating: "BB",
    },
    equity: {
      total_value: 1000000,
      avg_yield: 0.42,
      default_rate: 0.25,
      rating: "NR",
    },
  },
  investor_metrics: {
    total_invested: 18000000,
    distributions_ytd: 2500000,
    realized_yield_ytd: 0.14,
    investor_retention: 0.95,
    new_investors_30d: 12,
    pending_redemptions: 150000,
  },
  secondary_market: {
    volume_30d: 500000,
    avg_discount: 0.05,
    bid_ask_spread: 0.02,
    active_listings: 25,
    recent_trades: [
      { date: "2026-02-15", tranche: "BNPL-2026-Q1-M", amount: 50000, price: 0.97 },
      { date: "2026-02-14", tranche: "SUB-2026-Q1-S", amount: 100000, price: 0.99 },
      { date: "2026-02-13", tranche: "MIXED-2025-Q4-J", amount: 25000, price: 0.92 },
      { date: "2026-02-12", tranche: "BNPL-2026-Q1-S", amount: 75000, price: 0.995 },
    ],
  },
};

export default function TokenizationPage() {
  const [data, setData] = useState<TokenizationData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const result = await fetchTokenization();
      setData(result);
    } catch (error) {
      setData(mockTokenizationData);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const tokenData = data || mockTokenizationData;

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Tokenization Dashboard"
        lastUpdated={new Date(tokenData.generated_at).toLocaleString()}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      <div className="p-6 space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
          <KPICard
            title="Total Face Value"
            value={formatCurrency(tokenData.portfolio_summary.total_face_value, true)}
            icon={<Coins className="h-4 w-4" />}
          />
          <KPICard
            title="Total NAV"
            value={formatCurrency(tokenData.portfolio_summary.total_nav, true)}
            icon={<Wallet className="h-4 w-4" />}
          />
          <KPICard
            title="Active Pools"
            value={tokenData.portfolio_summary.total_pools.toString()}
            icon={<BarChart3 className="h-4 w-4" />}
          />
          <KPICard
            title="Average Yield"
            value={formatPercent(tokenData.portfolio_summary.avg_yield)}
            icon={<TrendingUp className="h-4 w-4" />}
          />
          <KPICard
            title="Total Investors"
            value={tokenData.portfolio_summary.total_investors.toString()}
            icon={<Users className="h-4 w-4" />}
          />
          <KPICard
            title="Default Rate"
            value={formatPercent(tokenData.portfolio_summary.default_rate)}
            icon={<ArrowUpDown className="h-4 w-4" />}
            description="Portfolio average"
          />
        </div>

        {/* Tranche Structure */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              Tranche Structure
            </CardTitle>
          </CardHeader>
          <CardContent>
            <TrancheChart tranches={tokenData.tranches} />
          </CardContent>
        </Card>

        {/* Pool Performance */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Coins className="h-5 w-5" />
              Pool Performance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <PoolTable pools={tokenData.pools} />
          </CardContent>
        </Card>

        {/* Investor Metrics and Secondary Market */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Investor Metrics
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Total Invested</p>
                  <p className="text-2xl font-bold">
                    {formatCurrency(tokenData.investor_metrics.total_invested, true)}
                  </p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Distributions YTD</p>
                  <p className="text-2xl font-bold text-green-500">
                    {formatCurrency(tokenData.investor_metrics.distributions_ytd, true)}
                  </p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Realized Yield YTD</p>
                  <p className="text-2xl font-bold text-green-500">
                    {formatPercent(tokenData.investor_metrics.realized_yield_ytd)}
                  </p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Retention Rate</p>
                  <p className="text-2xl font-bold">
                    {formatPercent(tokenData.investor_metrics.investor_retention)}
                  </p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">New Investors (30d)</p>
                  <p className="text-2xl font-bold text-blue-500">
                    +{tokenData.investor_metrics.new_investors_30d}
                  </p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Pending Redemptions</p>
                  <p className="text-2xl font-bold text-orange-500">
                    {formatCurrency(tokenData.investor_metrics.pending_redemptions, true)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ArrowUpDown className="h-5 w-5" />
                Secondary Market
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Volume (30d)</p>
                  <p className="text-2xl font-bold">
                    {formatCurrency(tokenData.secondary_market.volume_30d, true)}
                  </p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Avg Discount</p>
                  <p className="text-2xl font-bold">
                    {formatPercent(tokenData.secondary_market.avg_discount)}
                  </p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Bid-Ask Spread</p>
                  <p className="text-2xl font-bold">
                    {formatPercent(tokenData.secondary_market.bid_ask_spread)}
                  </p>
                </div>
                <div className="p-4 bg-muted/50 rounded-lg">
                  <p className="text-sm text-muted-foreground">Active Listings</p>
                  <p className="text-2xl font-bold">
                    {tokenData.secondary_market.active_listings}
                  </p>
                </div>
              </div>

              <div className="border-t pt-4">
                <h4 className="font-medium mb-3">Recent Trades</h4>
                <div className="space-y-2">
                  {tokenData.secondary_market.recent_trades.map((trade, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-2 bg-muted/30 rounded"
                    >
                      <div>
                        <span className="font-mono text-sm">{trade.tranche}</span>
                        <span className="text-xs text-muted-foreground ml-2">
                          {trade.date}
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="font-medium">
                          {formatCurrency(trade.amount)}
                        </span>
                        <Badge
                          variant={trade.price >= 0.98 ? "success" : "warning"}
                          className="ml-2"
                        >
                          {formatPercent(trade.price, 1)}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
