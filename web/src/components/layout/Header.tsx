"use client";

import { Activity, Pause, Play, Power } from "lucide-react";
import { useSystemStatus } from "@/hooks/useSystem";
import { pauseTrading, resumeTrading, killSwitch } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/formatters";

export default function Header() {
  const { data: status } = useSystemStatus();
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
              isPaused ? "bg-warning/20 text-warning" : "bg-profit/20 text-profit"
            )}
          >
            {isPaused ? "PAUSED" : "RUNNING"}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={handlePauseResume}
          className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted transition-colors hover:bg-card-hover hover:text-foreground"
        >
          {isPaused ? <Play size={14} /> : <Pause size={14} />}
          {isPaused ? "Resume" : "Pause"}
        </button>
        <button
          onClick={handleKill}
          className="flex items-center gap-1.5 rounded-lg border border-loss/50 px-3 py-1.5 text-xs text-loss transition-colors hover:bg-loss/10"
        >
          <Power size={14} />
          Kill
        </button>
      </div>
    </header>
  );
}
