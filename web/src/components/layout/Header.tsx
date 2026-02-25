"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Activity, LogOut, Pause, Play, Power, User } from "lucide-react";
import { useSystemStatus } from "@/hooks/useSystem";
import { killSwitch, pauseTrading, resumeTrading } from "@/lib/api";
import { cn } from "@/lib/formatters";
import { useAuthStore } from "@/stores/authStore";

export default function Header() {
  const { data: status } = useSystemStatus();
  const { user, logout } = useAuthStore();
  const queryClient = useQueryClient();
  const isPaused = (status as Record<string, unknown>)?.is_paused as boolean | undefined;
  const mode = ((status as Record<string, unknown>)?.mode as string) || "paper";

  const handlePauseResume = async () => {
    if (isPaused) {
      await resumeTrading();
    } else {
      await pauseTrading();
    }
    queryClient.invalidateQueries({ queryKey: ["system-status"] });
  };

  const handleKill = async () => {
    if (confirm("Kill switch: halt all trading and cancel orders?")) {
      await killSwitch();
      queryClient.invalidateQueries({ queryKey: ["system-status"] });
    }
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-card/80 px-6 backdrop-blur">
      <div className="flex items-center gap-3">
        <Activity size={16} className="text-accent" />
        <span className="text-sm text-muted">
          Mode:{" "}
          <span className={cn("font-medium", mode === "paper" ? "text-warning" : "text-loss")}>
            {mode.toUpperCase()}
          </span>
        </span>
        {isPaused !== undefined && (
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-medium",
              isPaused ? "bg-warning/20 text-warning" : "bg-profit/20 text-profit",
            )}
          >
            {isPaused ? "PAUSED" : "RUNNING"}
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handlePauseResume}
          className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted transition-colors hover:bg-card-hover hover:text-foreground"
        >
          {isPaused ? <Play size={14} /> : <Pause size={14} />}
          {isPaused ? "Resume" : "Pause"}
        </button>
        <button
          type="button"
          onClick={handleKill}
          className="flex items-center gap-1.5 rounded-lg border border-loss/50 px-3 py-1.5 text-xs text-loss transition-colors hover:bg-loss/10"
        >
          <Power size={14} />
          Kill
        </button>

        {user && (
          <div className="flex items-center gap-2 border-l border-border pl-3">
            <User size={14} className="text-muted" />
            <span className="text-xs text-muted">{user.name || user.email}</span>
            <button
              type="button"
              onClick={logout}
              className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-muted transition-colors hover:text-foreground"
              title="Sign out"
            >
              <LogOut size={14} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
