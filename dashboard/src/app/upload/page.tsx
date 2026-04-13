"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { uploadPortfolio, UploadSummary, ValidationError } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import {
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
} from "lucide-react";

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [portfolioName, setPortfolioName] = useState("");
  const [clientId, setClientId] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile?.name.endsWith(".csv")) {
      setFile(droppedFile);
      setError(null);
    } else {
      setError("Please upload a CSV file");
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (selectedFile.name.endsWith(".csv")) {
        setFile(selectedFile);
        setError(null);
      } else {
        setError("Please upload a CSV file");
      }
    }
  }, []);

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);

    try {
      const result = await uploadPortfolio(
        file,
        portfolioName || undefined,
        clientId || undefined
      );
      setUploadResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setUploadResult(null);
    setError(null);
    setPortfolioName("");
    setClientId("");
  };

  return (
    <div className="min-h-screen bg-background">
      <Header
        title="Portfolio Upload"
        subtitle="Import accounts from CSV"
      />

      <main className="container mx-auto px-4 py-6 max-w-4xl">
        {!uploadResult ? (
          <>
            {/* Upload Card */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle>Upload Portfolio CSV</CardTitle>
                <CardDescription>
                  Drag and drop a CSV file or click to browse. The file should contain
                  account data with columns: account_id, debtor_name, balance, original_creditor,
                  debt_type, days_past_due, state, phone, email.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {/* Drop Zone */}
                <div
                  className={`
                    border-2 border-dashed rounded-lg p-8 text-center transition-colors
                    ${isDragOver ? "border-primary bg-primary/5" : "border-muted-foreground/25"}
                    ${file ? "bg-muted/50" : ""}
                  `}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  {file ? (
                    <div className="flex flex-col items-center gap-4">
                      <FileSpreadsheet className="h-12 w-12 text-primary" />
                      <div>
                        <p className="font-medium">{file.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {(file.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                      <Button variant="outline" onClick={() => setFile(null)}>
                        Remove
                      </Button>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-4">
                      <Upload className="h-12 w-12 text-muted-foreground" />
                      <div>
                        <p className="font-medium">Drop your CSV file here</p>
                        <p className="text-sm text-muted-foreground">
                          or click to browse
                        </p>
                      </div>
                      <Input
                        type="file"
                        accept=".csv"
                        onChange={handleFileSelect}
                        className="max-w-xs"
                      />
                    </div>
                  )}
                </div>

                {/* Options */}
                <div className="grid grid-cols-2 gap-4 mt-6">
                  <div>
                    <Label htmlFor="portfolioName">Portfolio Name (optional)</Label>
                    <Input
                      id="portfolioName"
                      placeholder="e.g., Q1 2026 Medical Portfolio"
                      value={portfolioName}
                      onChange={(e) => setPortfolioName(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="clientId">Client ID (optional)</Label>
                    <Input
                      id="clientId"
                      placeholder="e.g., client-001"
                      value={clientId}
                      onChange={(e) => setClientId(e.target.value)}
                    />
                  </div>
                </div>

                {/* Error */}
                {error && (
                  <div className="mt-4 p-4 bg-destructive/10 text-destructive rounded-lg flex items-center gap-2">
                    <XCircle className="h-5 w-5" />
                    {error}
                  </div>
                )}

                {/* Upload Button */}
                <div className="mt-6 flex justify-end">
                  <Button
                    onClick={handleUpload}
                    disabled={!file || isUploading}
                    className="min-w-32"
                  >
                    {isUploading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Upload className="mr-2 h-4 w-4" />
                        Upload
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* CSV Format Guide */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">CSV Format Guide</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2 pr-4">Column</th>
                        <th className="text-left py-2 pr-4">Required</th>
                        <th className="text-left py-2">Description</th>
                      </tr>
                    </thead>
                    <tbody className="text-muted-foreground">
                      <tr className="border-b">
                        <td className="py-2 pr-4 font-mono">account_id</td>
                        <td className="py-2 pr-4">Yes</td>
                        <td className="py-2">Unique identifier for the account</td>
                      </tr>
                      <tr className="border-b">
                        <td className="py-2 pr-4 font-mono">debtor_name</td>
                        <td className="py-2 pr-4">Yes</td>
                        <td className="py-2">Full name of the debtor</td>
                      </tr>
                      <tr className="border-b">
                        <td className="py-2 pr-4 font-mono">balance</td>
                        <td className="py-2 pr-4">Yes</td>
                        <td className="py-2">Current balance owed (e.g., 1234.56)</td>
                      </tr>
                      <tr className="border-b">
                        <td className="py-2 pr-4 font-mono">original_creditor</td>
                        <td className="py-2 pr-4">No</td>
                        <td className="py-2">Name of original creditor</td>
                      </tr>
                      <tr className="border-b">
                        <td className="py-2 pr-4 font-mono">debt_type</td>
                        <td className="py-2 pr-4">No</td>
                        <td className="py-2">Type: payday, bnpl, medical, telecom, utility, subscription, etc.</td>
                      </tr>
                      <tr className="border-b">
                        <td className="py-2 pr-4 font-mono">days_past_due</td>
                        <td className="py-2 pr-4">No</td>
                        <td className="py-2">Days since last payment</td>
                      </tr>
                      <tr className="border-b">
                        <td className="py-2 pr-4 font-mono">state</td>
                        <td className="py-2 pr-4">No</td>
                        <td className="py-2">2-letter US state code</td>
                      </tr>
                      <tr className="border-b">
                        <td className="py-2 pr-4 font-mono">phone</td>
                        <td className="py-2 pr-4">No</td>
                        <td className="py-2">Phone number (any format)</td>
                      </tr>
                      <tr>
                        <td className="py-2 pr-4 font-mono">email</td>
                        <td className="py-2 pr-4">No</td>
                        <td className="py-2">Email address</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </>
        ) : (
          /* Upload Result */
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {uploadResult.invalid_rows === 0 ? (
                  <CheckCircle2 className="h-6 w-6 text-green-500" />
                ) : (
                  <AlertTriangle className="h-6 w-6 text-yellow-500" />
                )}
                Upload Complete
              </CardTitle>
              <CardDescription>
                Portfolio: {uploadResult.portfolio_name}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Summary Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Total Rows</p>
                  <p className="text-2xl font-bold">{uploadResult.total_rows}</p>
                </div>
                <div className="bg-green-500/10 rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Valid Accounts</p>
                  <p className="text-2xl font-bold text-green-600">{uploadResult.valid_rows}</p>
                </div>
                <div className={`rounded-lg p-4 ${uploadResult.invalid_rows > 0 ? "bg-red-500/10" : "bg-muted"}`}>
                  <p className="text-sm text-muted-foreground">Invalid Rows</p>
                  <p className={`text-2xl font-bold ${uploadResult.invalid_rows > 0 ? "text-red-600" : ""}`}>
                    {uploadResult.invalid_rows}
                  </p>
                </div>
                <div className="bg-muted rounded-lg p-4">
                  <p className="text-sm text-muted-foreground">Total Balance</p>
                  <p className="text-2xl font-bold">{formatCurrency(uploadResult.total_balance)}</p>
                </div>
              </div>

              {/* Breakdown */}
              <div className="grid md:grid-cols-2 gap-6 mb-6">
                <div>
                  <h4 className="font-medium mb-2">By Status</h4>
                  <div className="space-y-1">
                    {Object.entries(uploadResult.accounts_by_status).map(([status, count]) => (
                      <div key={status} className="flex justify-between text-sm">
                        <span className="text-muted-foreground capitalize">{status.replace(/_/g, " ")}</span>
                        <span>{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h4 className="font-medium mb-2">By Debt Type</h4>
                  <div className="space-y-1">
                    {Object.entries(uploadResult.accounts_by_debt_type).map(([type, count]) => (
                      <div key={type} className="flex justify-between text-sm">
                        <span className="text-muted-foreground capitalize">{type.replace(/_/g, " ")}</span>
                        <span>{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Errors */}
              {uploadResult.errors.length > 0 && (
                <div className="mb-6">
                  <h4 className="font-medium mb-2 flex items-center gap-2">
                    <XCircle className="h-4 w-4 text-red-500" />
                    Validation Errors ({uploadResult.errors.length})
                  </h4>
                  <div className="max-h-48 overflow-y-auto border rounded-lg">
                    <table className="w-full text-sm">
                      <thead className="bg-muted sticky top-0">
                        <tr>
                          <th className="text-left py-2 px-3">Row</th>
                          <th className="text-left py-2 px-3">Field</th>
                          <th className="text-left py-2 px-3">Error</th>
                          <th className="text-left py-2 px-3">Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {uploadResult.errors.map((err, i) => (
                          <tr key={i} className="border-t">
                            <td className="py-2 px-3">{err.row}</td>
                            <td className="py-2 px-3 font-mono">{err.field}</td>
                            <td className="py-2 px-3 text-red-600">{err.error}</td>
                            <td className="py-2 px-3 text-muted-foreground">{err.value || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex justify-end gap-4">
                <Button variant="outline" onClick={handleReset}>
                  Upload Another
                </Button>
                <Button onClick={() => router.push("/accounts")}>
                  View Accounts
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  );
}
