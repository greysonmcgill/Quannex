"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AccountSummary, AccountsQuery, AccountsResponse, fetchAccounts } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import { Search } from "lucide-react";

const DEBT_TYPES = [
  "",
  "bnpl",
  "medical",
  "telecom",
  "subscription",
  "utility",
  "credit_card",
  "bank",
  "personal_loan",
  "auto",
  "rent",
];
const STATUSES = ["", "scored", "contacted", "negotiating", "payment_pending", "resolved"];

export default function AccountsPage() {
  const [query, setQuery] = useState<AccountsQuery>({ page: 1, page_size: 25 });
  const [searchInput, setSearchInput] = useState("");
  const [data, setData] = useState<AccountsResponse>({
    page: 1,
    page_size: 25,
    total: 0,
    pages: 0,
    items: [],
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAccounts = useCallback(async () => {
    try {
      setError(null);
      setData(await fetchAccounts(query));
    } catch (err) {
      setData({ page: 1, page_size: query.page_size || 25, total: 0, pages: 0, items: [] });
      setError(err instanceof Error ? err.message : "Unable to load accounts");
    } finally {
      setIsLoading(false);
    }
  }, [query]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Accounts"
        lastUpdated={new Date().toLocaleString()}
        onRefresh={loadAccounts}
      />

      <div className="p-6 space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Search & Filters</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <label className="md:col-span-2">
              <span className="text-sm text-muted-foreground">Search</span>
              <div className="mt-1 flex items-center gap-2 rounded-md border px-3">
                <Search className="h-4 w-4 text-muted-foreground" />
                <input
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  placeholder="Account ID, debtor, creditor"
                  className="w-full bg-transparent py-2 outline-none"
                />
              </div>
            </label>

            <label>
              <span className="text-sm text-muted-foreground">Status</span>
              <select
                value={query.status || ""}
                onChange={(event) => setQuery((current) => ({ ...current, page: 1, status: event.target.value || undefined }))}
                className="mt-1 w-full rounded-md border bg-background px-3 py-2"
              >
                {STATUSES.map((status) => (
                  <option key={status || "all"} value={status}>
                    {status ? status.replace("_", " ") : "All statuses"}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="text-sm text-muted-foreground">Debt Type</span>
              <select
                value={query.debt_type || ""}
                onChange={(event) => setQuery((current) => ({ ...current, page: 1, debt_type: event.target.value || undefined }))}
                className="mt-1 w-full rounded-md border bg-background px-3 py-2"
              >
                {DEBT_TYPES.map((type) => (
                  <option key={type || "all"} value={type}>
                    {type ? type.replace("_", " ") : "All debt types"}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="text-sm text-muted-foreground">State</span>
              <input
                value={query.state || ""}
                onChange={(event) => setQuery((current) => ({ ...current, page: 1, state: event.target.value.toUpperCase() || undefined }))}
                maxLength={2}
                className="mt-1 w-full rounded-md border bg-background px-3 py-2"
                placeholder="CA"
              />
            </label>

            <div className="md:col-span-5 flex gap-3">
              <Button onClick={() => setQuery((current) => ({ ...current, page: 1, search: searchInput || undefined }))}>
                Apply Filters
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setSearchInput("");
                  setQuery({ page: 1, page_size: 25 });
                }}
              >
                Reset
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Live Accounts</span>
              <span className="text-sm font-normal text-muted-foreground">
                {data.total} total
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {error && (
              <div className="mb-4 rounded-lg border border-yellow-500/30 bg-yellow-500/5 p-4 text-sm text-yellow-700 dark:text-yellow-400">
                {error}
              </div>
            )}

            {isLoading ? (
              <div className="py-12 text-center text-muted-foreground">Loading accounts...</div>
            ) : data.items.length === 0 ? (
              <div className="py-12 text-center text-muted-foreground">
                No accounts matched the current filters.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-3 px-3">Account</th>
                      <th className="text-left py-3 px-3">Debtor</th>
                      <th className="text-left py-3 px-3">Type</th>
                      <th className="text-left py-3 px-3">State</th>
                      <th className="text-left py-3 px-3">Balance</th>
                      <th className="text-left py-3 px-3">Recovery</th>
                      <th className="text-left py-3 px-3">Status</th>
                      <th className="text-left py-3 px-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((account) => (
                      <AccountRow key={account.account_id} account={account} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {data.pages > 1 && (
              <div className="mt-6 flex items-center justify-between">
                <Button
                  variant="outline"
                  disabled={(query.page || 1) <= 1}
                  onClick={() => setQuery((current) => ({ ...current, page: Math.max((current.page || 1) - 1, 1) }))}
                >
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {data.page} of {Math.max(data.pages, 1)}
                </span>
                <Button
                  variant="outline"
                  disabled={(query.page || 1) >= data.pages}
                  onClick={() => setQuery((current) => ({ ...current, page: (current.page || 1) + 1 }))}
                >
                  Next
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function AccountRow({ account }: { account: AccountSummary }) {
  return (
    <tr className="border-b hover:bg-muted/50">
      <td className="py-3 px-3 font-mono">{account.account_id}</td>
      <td className="py-3 px-3">{account.debtor_name}</td>
      <td className="py-3 px-3 capitalize">{account.debt_type.replace("_", " ")}</td>
      <td className="py-3 px-3">{account.state}</td>
      <td className="py-3 px-3">{formatCurrency(account.balance)}</td>
      <td className="py-3 px-3">{formatPercent(account.recovery_probability)}</td>
      <td className="py-3 px-3">
        <Badge variant={account.status === "resolved" ? "success" : "outline"}>
          {account.status}
        </Badge>
      </td>
      <td className="py-3 px-3">
        <Link href={`/accounts/${account.account_id}`} className="text-primary hover:underline">
          View Detail
        </Link>
      </td>
    </tr>
  );
}
