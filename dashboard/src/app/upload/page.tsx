"use client";

import { useMemo, useState } from "react";
import { Header } from "@/components/layout/header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PortfolioUploadResult, uploadPortfolio } from "@/lib/api";
import { formatPercent } from "@/lib/utils";
import { FileUp, UploadCloud } from "lucide-react";

const REQUIRED_COLUMNS = [
  "account_id",
  "debtor_name",
  "balance",
  "original_creditor",
  "debt_type",
  "days_past_due",
  "state",
  "phone",
  "email",
];

interface PreviewRow {
  [key: string]: string;
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewRow[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<PortfolioUploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const previewHeaders = useMemo(
    () => Array.from(new Set(preview.flatMap((row) => Object.keys(row)))),
    [preview]
  );

  const handleFileSelection = async (selectedFile: File | null) => {
    setFile(selectedFile);
    setResult(null);
    setError(null);

    if (!selectedFile) {
      setPreview([]);
      return;
    }

    try {
      const text = await selectedFile.text();
      setPreview(parseCsvPreview(text));
    } catch (err) {
      setPreview([]);
      setError(err instanceof Error ? err.message : "Unable to preview CSV");
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    try {
      setIsUploading(true);
      setError(null);
      setResult(await uploadPortfolio(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Header title="Upload Portfolio" lastUpdated={new Date().toLocaleString()} />

      <div className="p-6 space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>CSV Import</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className={`rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
                dragActive ? "border-primary bg-primary/5" : "border-muted-foreground/20"
              }`}
              onDragOver={(event) => {
                event.preventDefault();
                setDragActive(true);
              }}
              onDragLeave={() => setDragActive(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragActive(false);
                handleFileSelection(event.dataTransfer.files?.[0] || null);
              }}
            >
              <UploadCloud className="h-10 w-10 mx-auto mb-3 text-primary" />
              <p className="font-medium">Drag and drop a portfolio CSV</p>
              <p className="text-sm text-muted-foreground mt-1">
                Required columns: {REQUIRED_COLUMNS.join(", ")}
              </p>
              <div className="mt-4">
                <label className="inline-flex">
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    className="hidden"
                    onChange={(event) => handleFileSelection(event.target.files?.[0] || null)}
                  />
                  <span className="inline-flex h-10 items-center justify-center rounded-md border px-4 text-sm font-medium cursor-pointer hover:bg-accent">
                    Choose CSV
                  </span>
                </label>
              </div>
            </div>

            {file && (
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border p-4">
                <div className="flex items-center gap-3">
                  <FileUp className="h-5 w-5 text-primary" />
                  <div>
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                </div>
                <Button onClick={handleUpload} disabled={isUploading}>
                  {isUploading ? "Importing..." : "Import Portfolio"}
                </Button>
              </div>
            )}

            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-400">
                {error}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Validation Preview</CardTitle>
          </CardHeader>
          <CardContent>
            {preview.length === 0 ? (
              <div className="py-10 text-center text-sm text-muted-foreground">
                Select a CSV to preview the first few rows before import.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      {previewHeaders.map((header) => (
                        <th key={header} className="text-left py-3 px-3 font-medium text-muted-foreground">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.map((row, index) => (
                      <tr key={index} className="border-b">
                        {previewHeaders.map((header) => (
                          <td key={header} className="py-3 px-3">
                            {row[header] || "—"}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {result && (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <Card className="xl:col-span-2">
              <CardHeader>
                <CardTitle>Import Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <SummaryStat label="Portfolio" value={result.portfolio_name} />
                  <SummaryStat label="Rows Received" value={String(result.received_rows)} />
                  <SummaryStat label="Imported" value={String(result.imported_rows)} />
                  <SummaryStat label="Rejected" value={String(result.rejected_rows)} />
                </div>

                <div className="space-y-2">
                  <p className="font-medium">Debt Mix</p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(result.debt_mix).map(([debtType, count]) => (
                      <Badge key={debtType} variant="secondary">
                        {debtType}: {count}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="font-medium">Top Imported Accounts</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2">Account</th>
                          <th className="text-left py-2">Type</th>
                          <th className="text-left py-2">Balance</th>
                          <th className="text-left py-2">Recovery</th>
                          <th className="text-left py-2">Channels</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.accounts.map((account) => (
                          <tr key={account.account_id} className="border-b">
                            <td className="py-2">{account.account_id}</td>
                            <td className="py-2 capitalize">{account.debt_type.replace("_", " ")}</td>
                            <td className="py-2">${account.balance.toFixed(2)}</td>
                            <td className="py-2">{formatPercent(account.recovery_probability)}</td>
                            <td className="py-2">{account.optimal_channels.join(", ")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Rejected Rows</CardTitle>
              </CardHeader>
              <CardContent>
                {result.row_errors.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No row-level validation errors.</div>
                ) : (
                  <div className="space-y-3">
                    {result.row_errors.slice(0, 12).map((row) => (
                      <div key={`${row.row_number}-${row.account_id ?? "missing"}`} className="rounded-lg border p-3">
                        <p className="font-medium">
                          Row {row.row_number}
                          {row.account_id ? ` · ${row.account_id}` : ""}
                        </p>
                        <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                          {row.errors.map((message) => (
                            <li key={message}>• {message}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted/50 p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold mt-1">{value}</p>
    </div>
  );
}

function parseCsvPreview(text: string): PreviewRow[] {
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];

  const headers = splitCsvLine(lines[0]);
  return lines.slice(1, 7).map((line) => {
    const values = splitCsvLine(line);
    return headers.reduce<PreviewRow>((row, header, index) => {
      row[header] = values[index] ?? "";
      return row;
    }, {});
  });
}

function splitCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (char === "," && !inQuotes) {
      values.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }
  values.push(current.trim());
  return values;
}
