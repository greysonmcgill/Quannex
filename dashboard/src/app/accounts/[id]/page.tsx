"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fetchAccount, AccountDetail } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import {
  ArrowLeft,
  Phone,
  Mail,
  MapPin,
  Building2,
  Calendar,
  Clock,
  DollarSign,
  TrendingUp,
  Shield,
  AlertTriangle,
  MessageSquare,
  CreditCard,
  FileText,
} from "lucide-react";

export default function AccountDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAccount() {
      if (!params.id) return;

      setIsLoading(true);
      try {
        const data = await fetchAccount(params.id as string);
        setAccount(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load account");
      } finally {
        setIsLoading(false);
      }
    }

    loadAccount();
  }, [params.id]);

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

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Header title="Loading..." subtitle="Account details" />
        <main className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        </main>
      </div>
    );
  }

  if (error || !account) {
    return (
      <div className="min-h-screen bg-background">
        <Header title="Error" subtitle="Failed to load account" />
        <main className="container mx-auto px-4 py-6">
          <Card>
            <CardContent className="py-8 text-center">
              <AlertTriangle className="h-12 w-12 mx-auto text-destructive mb-4" />
              <p className="text-destructive">{error || "Account not found"}</p>
              <Button className="mt-4" onClick={() => router.push("/accounts")}>
                Back to Accounts
              </Button>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header
        title={account.debtor_name}
        subtitle={`${account.external_account_id || account.id} | ${account.debt_type.replace(/_/g, " ")}`}
      />

      <main className="container mx-auto px-4 py-6">
        {/* Back Button */}
        <Button variant="ghost" className="mb-4" onClick={() => router.push("/accounts")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Accounts
        </Button>

        {/* Overview Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Current Balance</p>
                  <p className="text-2xl font-bold">{formatCurrency(account.current_balance)}</p>
                </div>
                <DollarSign className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Recovery Probability</p>
                  <p className="text-2xl font-bold">
                    {account.recovery_probability !== null
                      ? formatPercent(account.recovery_probability)
                      : "N/A"}
                  </p>
                </div>
                <TrendingUp className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Days Past Due</p>
                  <p className="text-2xl font-bold">{account.days_past_due}</p>
                </div>
                <Clock className="h-8 w-8 text-muted-foreground" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div>
                <p className="text-sm text-muted-foreground">Status</p>
                <span
                  className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium capitalize mt-1 ${getStatusBadgeClass(
                    account.status
                  )}`}
                >
                  {account.status.replace(/_/g, " ")}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content Tabs */}
        <Tabs defaultValue="details" className="space-y-4">
          <TabsList>
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="contacts">
              Contacts ({account.contact_history.length})
            </TabsTrigger>
            <TabsTrigger value="payments">
              Payments ({account.payment_history.length})
            </TabsTrigger>
            <TabsTrigger value="compliance">
              Compliance ({account.compliance_events.length})
            </TabsTrigger>
          </TabsList>

          {/* Details Tab */}
          <TabsContent value="details">
            <div className="grid md:grid-cols-2 gap-6">
              {/* Contact Information */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Contact Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-3">
                    <Phone className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-muted-foreground">Phone</p>
                      <p className={account.phone_valid ? "" : "text-destructive"}>
                        {account.phone || "Not provided"}
                        {!account.phone_valid && account.phone && " (Invalid)"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Mail className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-muted-foreground">Email</p>
                      <p className={account.email_valid ? "" : "text-destructive"}>
                        {account.email || "Not provided"}
                        {!account.email_valid && account.email && " (Invalid)"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <MapPin className="h-5 w-5 text-muted-foreground mt-1" />
                    <div>
                      <p className="text-sm text-muted-foreground">Address</p>
                      <p>
                        {account.address_line1 || "Not provided"}
                        {account.address_line2 && <br />}
                        {account.address_line2}
                        {account.city && (
                          <>
                            <br />
                            {account.city}, {account.state} {account.zip_code}
                          </>
                        )}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Debt Information */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Debt Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-3">
                    <Building2 className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-muted-foreground">Original Creditor</p>
                      <p>{account.original_creditor || "Unknown"}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <DollarSign className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-muted-foreground">Original Balance</p>
                      <p>{formatCurrency(account.original_balance)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <CreditCard className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-muted-foreground">Total Payments</p>
                      <p>{formatCurrency(account.total_payments)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Calendar className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="text-sm text-muted-foreground">Created</p>
                      <p>{new Date(account.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Intelligence Scores */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">AI Intelligence</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">Recovery Probability</p>
                      <p className="text-lg font-semibold">
                        {account.recovery_probability !== null
                          ? formatPercent(account.recovery_probability)
                          : "N/A"}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Settlement Threshold</p>
                      <p className="text-lg font-semibold">
                        {account.settlement_threshold !== null
                          ? formatPercent(account.settlement_threshold)
                          : "N/A"}
                      </p>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Optimal Channels</p>
                    <div className="flex flex-wrap gap-2">
                      {account.optimal_channels?.map((channel) => (
                        <span
                          key={channel}
                          className="px-2 py-1 bg-primary/10 text-primary rounded text-sm capitalize"
                        >
                          {channel}
                        </span>
                      )) || <span className="text-muted-foreground">Not scored</span>}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Compliance Flags */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Compliance Flags</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-3 h-3 rounded-full ${
                          account.do_not_call ? "bg-red-500" : "bg-green-500"
                        }`}
                      />
                      <span className="text-sm">Do Not Call</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-3 h-3 rounded-full ${
                          account.do_not_email ? "bg-red-500" : "bg-green-500"
                        }`}
                      />
                      <span className="text-sm">Do Not Email</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-3 h-3 rounded-full ${
                          account.bankruptcy_flag ? "bg-red-500" : "bg-green-500"
                        }`}
                      />
                      <span className="text-sm">Bankruptcy</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-3 h-3 rounded-full ${
                          account.disputed ? "bg-red-500" : "bg-green-500"
                        }`}
                      />
                      <span className="text-sm">Disputed</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Contacts Tab */}
          <TabsContent value="contacts">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <MessageSquare className="h-5 w-5" />
                  Contact History
                </CardTitle>
              </CardHeader>
              <CardContent>
                {account.contact_history.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    No contact attempts recorded
                  </p>
                ) : (
                  <div className="space-y-4">
                    {account.contact_history.map((contact) => (
                      <div
                        key={contact.id}
                        className="flex items-start gap-4 p-4 border rounded-lg"
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium capitalize">{contact.channel}</span>
                            <span className="text-muted-foreground">-</span>
                            <span className="capitalize">{contact.outcome.replace(/_/g, " ")}</span>
                            {contact.response_received && (
                              <span className="px-2 py-0.5 bg-green-100 text-green-800 rounded text-xs">
                                Responded
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {new Date(contact.created_at).toLocaleString()}
                            {contact.duration_seconds && ` | ${contact.duration_seconds}s`}
                          </p>
                        </div>
                        <div className="text-right">
                          <span className="text-sm text-muted-foreground">
                            Cost: ${contact.cost.toFixed(2)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Payments Tab */}
          <TabsContent value="payments">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <CreditCard className="h-5 w-5" />
                  Payment History
                </CardTitle>
              </CardHeader>
              <CardContent>
                {account.payment_history.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    No payments recorded
                  </p>
                ) : (
                  <div className="space-y-4">
                    {account.payment_history.map((payment) => (
                      <div
                        key={payment.id}
                        className="flex items-start gap-4 p-4 border rounded-lg"
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium">{formatCurrency(payment.amount)}</span>
                            <span className="capitalize text-muted-foreground">
                              via {payment.payment_method}
                            </span>
                            {payment.is_settlement && (
                              <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs">
                                Settlement
                              </span>
                            )}
                            {payment.is_payment_plan && (
                              <span className="px-2 py-0.5 bg-purple-100 text-purple-800 rounded text-xs">
                                Payment Plan
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {payment.processed_at
                              ? new Date(payment.processed_at).toLocaleString()
                              : new Date(payment.created_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="text-right">
                          <span
                            className={`px-2 py-1 rounded text-sm ${
                              payment.status === "completed"
                                ? "bg-green-100 text-green-800"
                                : payment.status === "failed"
                                ? "bg-red-100 text-red-800"
                                : "bg-yellow-100 text-yellow-800"
                            }`}
                          >
                            {payment.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Compliance Tab */}
          <TabsContent value="compliance">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  Compliance Events
                </CardTitle>
              </CardHeader>
              <CardContent>
                {account.compliance_events.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    No compliance events recorded
                  </p>
                ) : (
                  <div className="space-y-4">
                    {account.compliance_events.map((event) => (
                      <div
                        key={event.id}
                        className="flex items-start gap-4 p-4 border rounded-lg"
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium capitalize">
                              {event.event_type.replace(/_/g, " ")}
                            </span>
                            <span
                              className={`px-2 py-0.5 rounded text-xs ${
                                event.severity === "critical"
                                  ? "bg-red-100 text-red-800"
                                  : event.severity === "warning"
                                  ? "bg-yellow-100 text-yellow-800"
                                  : "bg-blue-100 text-blue-800"
                              }`}
                            >
                              {event.severity}
                            </span>
                            {event.regulation && (
                              <span className="text-muted-foreground text-sm">
                                ({event.regulation.toUpperCase()})
                              </span>
                            )}
                          </div>
                          <p className="text-sm">{event.description}</p>
                          {event.resolution && (
                            <p className="text-sm text-green-600 mt-1">
                              Resolution: {event.resolution}
                            </p>
                          )}
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(event.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
