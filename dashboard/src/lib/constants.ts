import {
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  Clock,
  FileText,
  Info,
  Mail,
  MessageSquare,
  Phone,
  Users,
  XCircle,
} from "lucide-react";

export const DEBT_TYPES = [
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
] as const;

export const ACCOUNT_STATUSES = [
  "ingested",
  "enriched",
  "scored",
  "contacted",
  "negotiating",
  "payment_pending",
  "resolved",
] as const;

export const CONTACT_CHANNELS = ["sms", "email", "voice", "mail", "in_person"] as const;

export const PAYMENT_METHODS = ["card", "ach", "check", "cash", "other"] as const;

export const REQUIRED_CSV_COLUMNS = [
  "account_id",
  "debtor_name",
  "balance",
  "original_creditor",
  "debt_type",
  "days_past_due",
  "state",
  "phone",
  "email",
] as const;

export const CHANNEL_ICONS = {
  sms: MessageSquare,
  email: Mail,
  voice: Phone,
  mail: FileText,
  in_person: Users,
} as const;

export const CHANNEL_COLORS = {
  sms: "bg-blue-500",
  email: "bg-green-500",
  voice: "bg-purple-500",
  mail: "bg-orange-500",
  in_person: "bg-cyan-500",
} as const;

export const QUEUE_LABELS = {
  high_priority: "High Priority",
  standard: "Standard",
  low_priority: "Low Priority",
  aging: "Aging",
} as const;

export const QUEUE_ICONS = {
  high_priority: AlertCircle,
  standard: Clock,
  low_priority: CheckCircle,
  aging: AlertTriangle,
} as const;

export const PIPELINE_STAGES = {
  ingested: { label: "Ingested", color: "bg-slate-500" },
  enriched: { label: "Enriched", color: "bg-blue-500" },
  scored: { label: "Scored", color: "bg-indigo-500" },
  contacted: { label: "Contacted", color: "bg-purple-500" },
  negotiating: { label: "Negotiating", color: "bg-amber-500" },
  payment_pending: { label: "Payment Pending", color: "bg-orange-500" },
  resolved: { label: "Resolved", color: "bg-green-500" },
} as const;

export const ALERT_ICONS = {
  critical: XCircle,
  high: AlertCircle,
  warning: AlertTriangle,
  info: Info,
} as const;

export const STATUS_ICONS = {
  healthy: CheckCircle,
  degraded: AlertTriangle,
  down: XCircle,
} as const;

export type DebtType = (typeof DEBT_TYPES)[number];
export type AccountStatus = (typeof ACCOUNT_STATUSES)[number];
export type ContactChannel = (typeof CONTACT_CHANNELS)[number];
export type PaymentMethod = (typeof PAYMENT_METHODS)[number];
