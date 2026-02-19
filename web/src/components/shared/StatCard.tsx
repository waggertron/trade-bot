"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/formatters";

interface StatCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon?: LucideIcon;
  trend?: "up" | "down" | "neutral";
  className?: string;
}

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  className,
}: StatCardProps) {
  return (
    <div className={cn("rounded-xl border border-border bg-card p-5", className)}>
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium text-muted">{title}</p>
        {Icon && <Icon size={16} className="text-muted" />}
      </div>
      <p
        className={cn(
          "mt-3 text-2xl font-semibold tracking-tight",
          trend === "up" && "text-profit",
          trend === "down" && "text-loss",
          !trend && "text-foreground",
        )}
      >
        {value}
      </p>
      {subtitle && (
        <p
          className={cn(
            "mt-1 text-xs",
            trend === "up" && "text-profit",
            trend === "down" && "text-loss",
            !trend && "text-muted",
          )}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}
