"use client";

import { cn } from "@/lib/utils";

interface ComplianceGaugeProps {
  score: number;
  rating: string;
  size?: "sm" | "md" | "lg";
}

export function ComplianceGauge({
  score,
  rating,
  size = "md",
}: ComplianceGaugeProps) {
  const sizeClasses = {
    sm: "w-24 h-24",
    md: "w-32 h-32",
    lg: "w-40 h-40",
  };

  const textSizeClasses = {
    sm: "text-lg",
    md: "text-2xl",
    lg: "text-3xl",
  };

  const strokeWidth = size === "sm" ? 6 : size === "md" ? 8 : 10;
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const getScoreColor = (score: number) => {
    if (score >= 95) return "stroke-green-500";
    if (score >= 85) return "stroke-yellow-500";
    if (score >= 70) return "stroke-orange-500";
    return "stroke-red-500";
  };

  return (
    <div className={cn("relative", sizeClasses[size])}>
      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
        {/* Background circle */}
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-muted"
        />
        {/* Score circle */}
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          className={cn("transition-all duration-1000", getScoreColor(score))}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("font-bold", textSizeClasses[size])}>{score}</span>
        <span className="text-xs text-muted-foreground uppercase tracking-wide">
          {rating}
        </span>
      </div>
    </div>
  );
}
