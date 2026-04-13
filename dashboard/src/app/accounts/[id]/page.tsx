"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AccountDetail,
  fetchAccount,
  logAccountContact,
  recordAccountPayment,
  updateAccountStatus,
} from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";

const STATUS_OPTIONS = ["scored", "contacted", "negotiating", "payment_pending", "resolved"];
const CONTACT_CHANNELS = ["sms", "email", "voice", "digital", "mail"];
const PAYMENT_METHODS = ["card", "ach", "cash", "check", "digital_wallet", "other"];

export default function AccountDetailPage() {
  const params = useParams<{ id: string }>();
  const accountId = params?.id;
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("scored");
  const [statusNotes, setStatusNotes] = useState("");
  const [contactForm, setContactForm] = useState({
    channel: "sms",
    outcome: "responded",
    compliant: true,
    notes: "",
    agent_name: "Dashboard User",
  });
  const [paymentForm, setPaymentForm] = useState({
    amount: "",
    method: "card",
    status: "completed",
    reference: "",
    notes: "",
  });
  const [isSaving, setIsSaving] = useState(false);

  const loadAccount = useCallback(async () => {
    if (!accountId) return;
    try {
      setError(null);
      const data = await fetchAccount(accountId);
      setAccount(data);
      setStatus(data.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load account");
      setAccount(null);
    } finally {
      setIsLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    loadAccount();
  }, [loadAccount]);

  const handleStatusUpdate = async () => {
    if (!accountId) return;
    try {
      setIsSaving(true);
      await updateAccountStatus(accountId, status, statusNotes || undefined);
      setStatusNotes("");
      await loadAccount();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update status");
    } finally {
      setIsSaving(false);
    }
  };

  const handleContactSubmit = async () => {
    if (!accountId) return;
    try {
      setIsSaving(true);
      await logAccountContact(accountId, contactForm);
      setContactForm((current) => ({ ...current, notes: "" }));
      await loadAccount();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to log contact");
    } finally {
      setIsSaving(false);
    }
  };

  const handlePaymentSubmit = async () => {
    if (!accountId || !paymentForm.amount) return;
    try {
      setIsSaving(true);
      await recordAccountPayment(accountId, {
        ...paymentForm,
        amount: Number(paymentForm.amount),
      });
      setPaymentForm((current) => ({ ...current, amount: "", reference: "", notes: "" }));
      await loadAccount();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to record payment");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!account) {
    return (
      <div className="min-h-screen bg-background">
        <Header title="Account Detail" lastUpdated={new Date().toLocaleString()} />
        <div className="p-6">
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              {error || "Account not found."}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header
        title={`Account ${account.account_id}`}
        lastUpdated={account.updated_at ? new Date(account.updated_at).toLocaleString() : undefined}
        onRefresh={loadAccount}
      />

      <div className="p-6 space-y-6">
        {error && (
          <Card className="border-yellow-500/30 bg-yellow-500/5">
            <CardContent className="p-4 text-sm text-yellow-700 dark:text-yellow-400">
              {error}
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
          <MetricCard label="Balance" value={formatCurrency(account.balance)} />
          <MetricCard label="Original Balance" value={formatCurrency(account.original_balance)} />
          <MetricCard label="Recovery Probability" value={formatPercent(account.recovery_probability)} />
          <MetricCard label="Paid to Date" value={formatCurrency(account.total_paid)} />
          <MetricCard label="Contacts Logged" value={String(account.total_contact_attempts)} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle>Account Summary</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <SummaryLine label="Debtor" value={account.debtor_name} />
              <SummaryLine label="Creditor" value={account.original_creditor} />
              <SummaryLine label="Debt Type" value={account.debt_type.replace("_", " ")} />
              <SummaryLine label="State" value={account.state} />
              <SummaryLine label="Phone" value={account.phone || "—"} />
              <SummaryLine label="Email" value={account.email || "—"} />
              <SummaryLine label="Settlement Threshold" value={formatPercent(account.settlement_threshold)} />
              <div>
                <p className="text-muted-foreground">Status</p>
                <Badge className="mt-1" variant={account.status === "resolved" ? "success" : "outline"}>
                  {account.status}
                </Badge>
              </div>
              <div className="md:col-span-2">
                <p className="text-muted-foreground">Optimal Channels</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {account.optimal_channels.map((channel) => (
                    <Badge key={channel} variant="secondary">
                      {channel}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Update Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                className="w-full rounded-md border bg-background px-3 py-2"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option.replace("_", " ")}
                  </option>
                ))}
              </select>
              <textarea
                value={statusNotes}
                onChange={(event) => setStatusNotes(event.target.value)}
                placeholder="Optional status note"
                className="min-h-[100px] w-full rounded-md border bg-background px-3 py-2"
              />
              <Button onClick={handleStatusUpdate} disabled={isSaving}>
                Save Status
              </Button>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Log Contact Attempt</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <select
                value={contactForm.channel}
                onChange={(event) => setContactForm((current) => ({ ...current, channel: event.target.value }))}
                className="w-full rounded-md border bg-background px-3 py-2"
              >
                {CONTACT_CHANNELS.map((channel) => (
                  <option key={channel} value={channel}>
                    {channel}
                  </option>
                ))}
              </select>
              <input
                value={contactForm.outcome}
                onChange={(event) => setContactForm((current) => ({ ...current, outcome: event.target.value }))}
                className="w-full rounded-md border bg-background px-3 py-2"
                placeholder="Outcome"
              />
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={contactForm.compliant}
                  onChange={(event) => setContactForm((current) => ({ ...current, compliant: event.target.checked }))}
                />
                Mark as compliant
              </label>
              <textarea
                value={contactForm.notes}
                onChange={(event) => setContactForm((current) => ({ ...current, notes: event.target.value }))}
                placeholder="Notes"
                className="min-h-[100px] w-full rounded-md border bg-background px-3 py-2"
              />
              <Button onClick={handleContactSubmit} disabled={isSaving}>
                Save Contact Attempt
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Record Payment</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <input
                value={paymentForm.amount}
                onChange={(event) => setPaymentForm((current) => ({ ...current, amount: event.target.value }))}
                type="number"
                min="0"
                step="0.01"
                placeholder="Amount"
                className="w-full rounded-md border bg-background px-3 py-2"
              />
              <select
                value={paymentForm.method}
                onChange={(event) => setPaymentForm((current) => ({ ...current, method: event.target.value }))}
                className="w-full rounded-md border bg-background px-3 py-2"
              >
                {PAYMENT_METHODS.map((method) => (
                  <option key={method} value={method}>
                    {method}
                  </option>
                ))}
              </select>
              <select
                value={paymentForm.status}
                onChange={(event) => setPaymentForm((current) => ({ ...current, status: event.target.value }))}
                className="w-full rounded-md border bg-background px-3 py-2"
              >
                <option value="completed">completed</option>
                <option value="pending">pending</option>
                <option value="failed">failed</option>
              </select>
              <input
                value={paymentForm.reference}
                onChange={(event) => setPaymentForm((current) => ({ ...current, reference: event.target.value }))}
                placeholder="Reference"
                className="w-full rounded-md border bg-background px-3 py-2"
              />
              <textarea
                value={paymentForm.notes}
                onChange={(event) => setPaymentForm((current) => ({ ...current, notes: event.target.value }))}
                placeholder="Notes"
                className="min-h-[100px] w-full rounded-md border bg-background px-3 py-2"
              />
              <Button onClick={handlePaymentSubmit} disabled={isSaving || !paymentForm.amount}>
                Save Payment
              </Button>
            </CardContent>
          </Card>
        </div>

        <HistorySection title="Contact History">
          {account.contact_history.length === 0 ? (
            <EmptyText text="No contact attempts logged yet." />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-3">When</th>
                  <th className="text-left py-3 px-3">Channel</th>
                  <th className="text-left py-3 px-3">Outcome</th>
                  <th className="text-left py-3 px-3">Compliant</th>
                  <th className="text-left py-3 px-3">Cost</th>
                </tr>
              </thead>
              <tbody>
                {account.contact_history.map((attempt) => (
                  <tr key={attempt.attempt_id} className="border-b">
                    <td className="py-3 px-3">{new Date(attempt.attempted_at).toLocaleString()}</td>
                    <td className="py-3 px-3">{attempt.channel}</td>
                    <td className="py-3 px-3">{attempt.outcome}</td>
                    <td className="py-3 px-3">{attempt.compliant ? "Yes" : "No"}</td>
                    <td className="py-3 px-3">{formatCurrency(attempt.cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </HistorySection>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <HistorySection title="Payments">
            {account.payments.length === 0 ? (
              <EmptyText text="No payments recorded yet." />
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-3">When</th>
                    <th className="text-left py-3 px-3">Amount</th>
                    <th className="text-left py-3 px-3">Method</th>
                    <th className="text-left py-3 px-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {account.payments.map((payment) => (
                    <tr key={payment.payment_id} className="border-b">
                      <td className="py-3 px-3">{new Date(payment.recorded_at).toLocaleString()}</td>
                      <td className="py-3 px-3">{formatCurrency(payment.amount)}</td>
                      <td className="py-3 px-3">{payment.method}</td>
                      <td className="py-3 px-3">{payment.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </HistorySection>

          <HistorySection title="Compliance Events">
            {account.compliance_events.length === 0 ? (
              <EmptyText text="No compliance events recorded for this account." />
            ) : (
              <div className="space-y-3">
                {account.compliance_events.map((event) => (
                  <div key={event.event_id} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-medium">{event.event_type}</p>
                        <p className="text-sm text-muted-foreground">{event.message}</p>
                      </div>
                      <Badge variant={event.resolved ? "success" : "warning"}>{event.severity}</Badge>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {new Date(event.occurred_at).toLocaleString()}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </HistorySection>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="mt-2 text-2xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  );
}

function SummaryLine({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-muted-foreground">{label}</p>
      <p className="mt-1 font-medium">{value}</p>
    </div>
  );
}

function HistorySection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function EmptyText({ text }: { text: string }) {
  return <div className="py-8 text-sm text-muted-foreground text-center">{text}</div>;
}
