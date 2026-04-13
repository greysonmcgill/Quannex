"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  fetchAccounts,
  fetchAccountStats,
  AccountListItem,
  AccountListResponse,
  AccountStats,
} from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  Filter,
  Users,
  DollarSign,
  TrendingUp,
  Clock,
} from "lucide-react";

const STATUS_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "new", label: "New" },
  { value: "ingested", label: "Ingested" },
  { value: "scored", label: "Scored" },
  { value: "contacted", label: "Contacted" },
  { value: "negotiating", label: "Negotiating" },
  { value: "payment_pending", label: "Payment Pending" },
  { value: "payment_plan", label: "Payment Plan" },
  { value: "settled", label: "Settled" },
  { value: "paid_in_full", label: "Paid in Full" },
  { value: "disputed", label: "Disputed" },
  { value: "uncollectable", label: "Uncollectable" },
];

const DEBT_TYPE_OPTIONS = [
  { value: "", label: "All Types" },
  { value: "payday", label: "Payday" },
  { value: "personal_micro", label: "Personal Micro" },
  { value: "buy_now_pay_later", label: "BNPL" },
  { value: "medical", label: "Medical" },
  { value: "utility", label: "Utility" },
  { value: "telecom", label: "Telecom" },
  { value: "auto_micro", label: "Auto Micro" },
  { value: "student_micro", label: "Student Micro" },
  { value: "retail_credit", label: "Retail Credit" },
  { value: "subscription", label: "Subscription" },
];

const STATE_OPTIONS = [
  { value: "", label: "All States" },
  ...["CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI"].map((s) => ({
    value: s,
    label: s,
  })),
];

export default function AccountsPage() {
  const router = useRouter();
  const [accounts, setAccounts] = useState<AccountListItem[]>([]);
  const [stats, setStats] = useState<AccountStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [totalBalance, setTotalBalance] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  // Filters
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [debtType, setDebtType] = useState("");
  const [state, setState] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState("desc");

  const loadAccounts = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetchAccounts({
        page,
        page_size: pageSize,
        search: search || undefined,
        status: status || undefined,
        debt_type: debtType || undefined,
        state: state || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setAccounts(response.accounts);
      setTotal(response.total);
      setTotalBalance(response.total_balance);
    } catch (error) {
      console.error("Failed to load accounts:", error);
      setAccounts([]);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, search, status, debtType, state, sortBy, sortOrder]);

  const loadStats = useCallback(async () => {
    try {
      const response = await fetchAccountStats();
      setStats(response);
    } catch (error) {
      console.error("Failed to load stats:", error);
    }
  }, []);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadAccounts();
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case "settled":
      case "paid_in_full":
        return "bg-green-100 text-green-800";
      case "payment_pending":
      case "payment_plan":
        return "bg-blue-100 text-blue-800";
      case "negotiating":
      case "contacted":
        return "bg-yellow-100 text-yellow-800";
      case "disputed":
      case "uncollectable":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Accounts"
        subtitle={`${total.toLocaleString()} accounts | ${formatCurrency(totalBalance)} total balance`}
      />

      <main className="container mx-auto px-4 py-6">
        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Accounts</p>
                    <p className="text-2xl font-bold">{stats.total_accounts.toLocaleString()}</p>
                  </div>
                  <Users className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Balance</p>
                    <p className="text-2xl font-bold">{formatCurrency(stats.total_balance)}</p>
                  </div>
                  <DollarSign className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Avg Recovery Prob</p>
                    <p className="text-2xl font-bold">{formatPercent(stats.avg_recovery_probability)}</p>
                  </div>
                  <TrendingUp className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Avg Days Past Due</p>
                    <p className="text-2xl font-bold">{stats.avg_days_past_due}</p>
                  </div>
                  <Clock className="h-8 w-8 text-muted-foreground" />
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filters */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <form onSubmit={handleSearch} className="flex flex-wrap gap-4">
              <div className="flex-1 min-w-[200px]">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by name or account ID..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={debtType} onValueChange={setDebtType}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Debt Type" />
                </SelectTrigger>
                <SelectContent>
                  {DEBT_TYPE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={state} onValueChange={setState}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue placeholder="State" />
                </SelectTrigger>
                <SelectContent>
                  {STATE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button type="submit">
                <Filter className="mr-2 h-4 w-4" />
                Filter
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Accounts Table */}
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-muted">
                  <tr>
                    <th
                      className="text-left py-3 px-4 font-medium cursor-pointer hover:bg-muted/80"
                      onClick={() => toggleSort("debtor_name")}
                    >
                      <div className="flex items-center gap-1">
                        Name
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </th>
                    <th
                      className="text-left py-3 px-4 font-medium cursor-pointer hover:bg-muted/80"
                      onClick={() => toggleSort("current_balance")}
                    >
                      <div className="flex items-center gap-1">
                        Balance
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </th>
                    <th className="text-left py-3 px-4 font-medium">Type</th>
                    <th className="text-left py-3 px-4 font-medium">Status</th>
                    <th className="text-left py-3 px-4 font-medium">State</th>
                    <th
                      className="text-left py-3 px-4 font-medium cursor-pointer hover:bg-muted/80"
                      onClick={() => toggleSort("recovery_probability")}
                    >
                      <div className="flex items-center gap-1">
                        Recovery %
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </th>
                    <th
                      className="text-left py-3 px-4 font-medium cursor-pointer hover:bg-muted/80"
                      onClick={() => toggleSort("days_past_due")}
                    >
                      <div className="flex items-center gap-1">
                        DPD
                        <ArrowUpDown className="h-3 w-3" />
                      </div>
                    </th>
                    <th className="text-left py-3 px-4 font-medium">Contacts</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoading ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-muted-foreground">
                        Loading accounts...
                      </td>
                    </tr>
                  ) : accounts.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-muted-foreground">
                        No accounts found. Try adjusting your filters or{" "}
                        <a href="/upload" className="text-primary underline">
                          upload a portfolio
                        </a>
                        .
                      </td>
                    </tr>
                  ) : (
                    accounts.map((account) => (
                      <tr
                        key={account.id}
                        className="border-t hover:bg-muted/50 cursor-pointer"
                        onClick={() => router.push(`/accounts/${account.id}`)}
                      >
                        <td className="py-3 px-4">
                          <div>
                            <p className="font-medium">{account.debtor_name}</p>
                            <p className="text-sm text-muted-foreground">
                              {account.external_account_id}
                            </p>
                          </div>
                        </td>
                        <td className="py-3 px-4 font-mono">
                          {formatCurrency(account.current_balance)}
                        </td>
                        <td className="py-3 px-4">
                          <span className="text-sm capitalize">
                            {account.debt_type.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${getStatusBadgeClass(
                              account.status
                            )}`}
                          >
                            {account.status.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td className="py-3 px-4">{account.state || "-"}</td>
                        <td className="py-3 px-4">
                          {account.recovery_probability !== null
                            ? formatPercent(account.recovery_probability)
                            : "-"}
                        </td>
                        <td className="py-3 px-4">{account.days_past_due}</td>
                        <td className="py-3 px-4">{account.contact_attempts}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t">
                <div className="text-sm text-muted-foreground">
                  Showing {(page - 1) * pageSize + 1} to{" "}
                  {Math.min(page * pageSize, total)} of {total} accounts
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(page - 1)}
                    disabled={page === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-sm">
                    Page {page} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(page + 1)}
                    disabled={page === totalPages}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
