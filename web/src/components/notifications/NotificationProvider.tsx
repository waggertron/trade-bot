"use client";

import { useEffect } from "react";
import { X } from "lucide-react";
import { useNotificationStore } from "@/stores/notificationStore";
import { cn } from "@/lib/formatters";

const typeStyles = {
  info: "border-accent/50 bg-accent/10",
  success: "border-profit/50 bg-profit/10",
  warning: "border-warning/50 bg-warning/10",
  error: "border-loss/50 bg-loss/10",
};

export default function NotificationProvider() {
  const { notifications, dismiss } = useNotificationStore();

  // Auto-dismiss after 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      notifications.forEach((n) => {
        if (now - n.timestamp > 5000) dismiss(n.id);
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [notifications, dismiss]);

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {notifications.slice(-5).map((n) => (
        <div
          key={n.id}
          className={cn(
            "flex items-start gap-3 rounded-lg border p-3 shadow-lg backdrop-blur",
            typeStyles[n.type]
          )}
        >
          <div className="flex-1">
            <p className="text-sm font-medium text-foreground">{n.title}</p>
            {n.message && <p className="mt-0.5 text-xs text-muted">{n.message}</p>}
          </div>
          <button onClick={() => dismiss(n.id)} className="text-muted hover:text-foreground">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
