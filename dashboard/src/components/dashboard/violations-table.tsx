"use client";

import { Violation } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface ViolationsTableProps {
  violations: Violation[];
}

export function ViolationsTable({ violations }: ViolationsTableProps) {
  const getSeverityVariant = (severity: string): "error" | "warning" | "secondary" => {
    switch (severity.toLowerCase()) {
      case "critical":
        return "error";
      case "major":
        return "warning";
      default:
        return "secondary";
    }
  };

  if (violations.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No violations recorded
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b">
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
              ID
            </th>
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
              Date
            </th>
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
              Type
            </th>
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
              Description
            </th>
            <th className="text-center py-3 px-4 text-sm font-medium text-muted-foreground">
              Severity
            </th>
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">
              Resolution
            </th>
          </tr>
        </thead>
        <tbody>
          {violations.map((violation) => (
            <tr key={violation.id} className="border-b hover:bg-muted/50">
              <td className="py-3 px-4">
                <span className="font-mono text-sm">{violation.id}</span>
              </td>
              <td className="py-3 px-4 text-sm">{violation.date}</td>
              <td className="py-3 px-4 text-sm capitalize">{violation.type}</td>
              <td className="py-3 px-4 text-sm max-w-xs truncate">
                {violation.description}
              </td>
              <td className="py-3 px-4 text-center">
                <Badge variant={getSeverityVariant(violation.severity)}>
                  {violation.severity}
                </Badge>
              </td>
              <td className="py-3 px-4 text-sm text-muted-foreground">
                {violation.resolution}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
