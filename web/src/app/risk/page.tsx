"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, RotateCcw, ShieldAlert } from "lucide-react";
import { useState } from "react";
import ChartContainer from "@/components/shared/ChartContainer";
import { StatCardSkeleton } from "@/components/shared/LoadingSkeleton";
import StatCard from "@/components/shared/StatCard";
import {
  useCircuitBreaker,
  useDrawdownStatus,
  useRegime,
  useRiskPresets,
  useRiskStatus,
} from "@/hooks/useRisk";
import { applyRiskPreset, resetCircuitBreaker, updateRiskSettings } from "@/lib/api";
import { cn } from "@/lib/formatters";

function ProgressBar({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const barColor = pct > 80 ? "bg-loss" : pct > 60 ? "bg-warning" : color;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="text-foreground">
          {value.toFixed(1)} / {max}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-background">
        <div
          className={cn("h-full rounded-full transition-all", barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function SliderField({
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="text-foreground">
          {value}
          {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-accent"
      />
    </div>
  );
}

export default function RiskPage() {
  const queryClient = useQueryClient();
  const { data: riskStatus, isLoading: riskLoading } = useRiskStatus();
  const { data: drawdown } = useDrawdownStatus();
  const { data: circuitBreaker } = useCircuitBreaker();
  const { data: regime } = useRegime();
  useRiskPresets();

  const rs = riskStatus as Record<string, unknown> | undefined;
  const dd = drawdown as Record<string, unknown> | undefined;
  const cb = circuitBreaker as Record<string, unknown> | undefined;

  const [formValues, setFormValues] = useState<Record<string, number | boolean>>({});

  const getVal = (key: string, fallback: number) => {
    if (key in formValues) return formValues[key] as number;
    return (rs?.[key] as number) ?? fallback;
  };

  const updateMutation = useMutation({
    mutationFn: (settings: Record<string, unknown>) => updateRiskSettings(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk-status"] });
      setFormValues({});
    },
  });

  const presetMutation = useMutation({
    mutationFn: (level: string) => applyRiskPreset(level),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["risk-status"] });
      setFormValues({});
    },
  });

  const resetMutation = useMutation({
    mutationFn: () => resetCircuitBreaker(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["circuit-breaker"] }),
  });

  const handleApply = () => {
    if (Object.keys(formValues).length > 0) {
      updateMutation.mutate(formValues);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Risk Management</h1>

      {/* Status cards */}
      <div className="grid grid-cols-4 gap-4">
        {riskLoading ? (
          Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)
        ) : (
          <>
            <StatCard
              title="Volatility Regime"
              value={(
                ((regime as Record<string, unknown>)?.regime as string) || "medium"
              ).toUpperCase()}
              icon={Activity}
            />
            <StatCard
              title="Circuit Breaker"
              value={cb?.tripped ? "TRIPPED" : "OK"}
              icon={AlertTriangle}
              trend={cb?.tripped ? "down" : "up"}
            />
            <StatCard
              title="Open Positions"
              value={`${dd?.positions_used || 0} / ${dd?.positions_limit || 0}`}
              icon={ShieldAlert}
            />
            <StatCard
              title="Max Position"
              value={`${rs?.max_position_pct || 0}%`}
              subtitle="Per-trade limit"
            />
          </>
        )}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Drawdown monitor */}
        <ChartContainer title="Drawdown Monitor" subtitle="Real-time risk utilization">
          <div className="space-y-4">
            <ProgressBar
              label="Daily Loss"
              value={(dd?.daily_pct as number) || 0}
              max={(dd?.daily_limit as number) || 3}
              color="bg-accent"
            />
            <ProgressBar
              label="Weekly Drawdown"
              value={(dd?.weekly_pct as number) || 0}
              max={(dd?.weekly_limit as number) || 5}
              color="bg-accent"
            />
            <ProgressBar
              label="Position Count"
              value={(dd?.positions_used as number) || 0}
              max={(dd?.positions_limit as number) || 10}
              color="bg-accent"
            />
          </div>
        </ChartContainer>

        {/* Circuit breaker */}
        <ChartContainer title="Circuit Breaker" subtitle="Emergency stop status">
          <div className="space-y-4">
            <div
              className={cn(
                "flex items-center gap-3 rounded-lg p-4",
                cb?.tripped
                  ? "bg-loss/10 border border-loss/30"
                  : "bg-profit/10 border border-profit/30",
              )}
            >
              <div
                className={cn(
                  "h-3 w-3 rounded-full",
                  cb?.tripped ? "bg-loss animate-pulse" : "bg-profit",
                )}
              />
              <div>
                <p className="text-sm font-medium">{cb?.tripped ? "TRIPPED" : "Normal"}</p>
                <p className="text-xs text-muted">
                  {cb?.tripped
                    ? "Trading halted — drawdown exceeded threshold"
                    : "All systems operational"}
                </p>
              </div>
            </div>
            {cb?.tripped === true && (
              <button
                type="button"
                onClick={() => resetMutation.mutate()}
                className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover"
              >
                <RotateCcw size={14} />
                Reset Circuit Breaker
              </button>
            )}
          </div>
        </ChartContainer>
      </div>

      {/* Risk settings form */}
      <ChartContainer
        title="Risk Parameters"
        subtitle="Adjust position sizing and loss limits"
        actions={
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleApply}
              disabled={Object.keys(formValues).length === 0}
              className="rounded-lg bg-accent px-4 py-1.5 text-xs text-white hover:bg-accent-hover disabled:opacity-50"
            >
              Apply Changes
            </button>
          </div>
        }
      >
        <div className="space-y-6">
          {/* Preset buttons */}
          <div className="flex gap-2">
            {["conservative", "moderate", "aggressive", "very_aggressive"].map((level) => (
              <button
                type="button"
                key={level}
                onClick={() => presetMutation.mutate(level)}
                className="rounded-lg border border-border px-3 py-1.5 text-xs capitalize text-muted hover:bg-card-hover hover:text-foreground"
              >
                {level.replace("_", " ")}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-6">
            <SliderField
              label="Max Position %"
              value={getVal("max_position_pct", 2)}
              min={0.5}
              max={20}
              step={0.5}
              unit="%"
              onChange={(v) => setFormValues({ ...formValues, max_position_pct: v })}
            />
            <SliderField
              label="Max Sector Exposure %"
              value={getVal("max_sector_exposure_pct", 20)}
              min={5}
              max={50}
              step={5}
              unit="%"
              onChange={(v) => setFormValues({ ...formValues, max_sector_exposure_pct: v })}
            />
            <SliderField
              label="Daily Loss Limit %"
              value={getVal("daily_loss_limit_pct", 3)}
              min={1}
              max={15}
              step={0.5}
              unit="%"
              onChange={(v) => setFormValues({ ...formValues, daily_loss_limit_pct: v })}
            />
            <SliderField
              label="Weekly Drawdown Limit %"
              value={getVal("weekly_drawdown_limit_pct", 5)}
              min={1}
              max={20}
              step={1}
              unit="%"
              onChange={(v) => setFormValues({ ...formValues, weekly_drawdown_limit_pct: v })}
            />
            <SliderField
              label="Max Open Positions"
              value={getVal("max_open_positions", 10)}
              min={1}
              max={30}
              step={1}
              unit=""
              onChange={(v) => setFormValues({ ...formValues, max_open_positions: v })}
            />
            <SliderField
              label="Stop Loss %"
              value={getVal("stop_loss_pct", 5)}
              min={1}
              max={20}
              step={0.5}
              unit="%"
              onChange={(v) => setFormValues({ ...formValues, stop_loss_pct: v })}
            />
            <SliderField
              label="Trailing Stop %"
              value={getVal("trailing_stop_pct", 3)}
              min={1}
              max={15}
              step={0.5}
              unit="%"
              onChange={(v) => setFormValues({ ...formValues, trailing_stop_pct: v })}
            />
            <SliderField
              label="Max Correlation"
              value={getVal("max_correlation", 0.7)}
              min={0.1}
              max={1}
              step={0.05}
              unit=""
              onChange={(v) => setFormValues({ ...formValues, max_correlation: v })}
            />
          </div>
        </div>
      </ChartContainer>
    </div>
  );
}
