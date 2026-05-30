import { Card, CardContent } from "@/components/ui/card";

interface ErrorAlertProps {
  message: string;
  details?: string;
}

export function ErrorAlert({ message, details }: ErrorAlertProps) {
  return (
    <Card className="border-yellow-500/30 bg-yellow-500/5">
      <CardContent className="p-4 text-sm text-yellow-700 dark:text-yellow-400">
        {message}
        {details && ` ${details}`}
      </CardContent>
    </Card>
  );
}
