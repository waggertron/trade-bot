"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertCircle,
  BarChart3,
  Brain,
  Minus,
  Target,
  ToggleLeft,
  ToggleRight,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import { useCallback, useState } from "react";
import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import ChartContainer from "@/components/shared/ChartContainer";
import DataTable from "@/components/shared/DataTable";
import { ChartSkeleton, TableSkeleton } from "@/components/shared/LoadingSkeleton";
import { useConsensus, useStrategies } from "@/hooks/useStrategies";
import { useSignals } from "@/hooks/useTrades";
import { getStrategySignals, updateStrategyEnabled, updateStrategyWeight } from "@/lib/api";
import { chartAxisTick, seriesColors, themeColors } from "@/lib/chartTheme";
import { cn, formatPercent, formatTimeAgo } from "@/lib/formatters";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StrategyData {
  name: string;
  type: string;
  enabled: boolean;
  weight: number;
  description?: string;
  recent_signals?: SignalData[];
  total_trades?: number;
  win_rate?: number;
}

interface SignalData {
  id: string;
  symbol: string;
  direction: "buy" | "sell" | "hold";
  confidence: number;
  strategy: string;
  reasoning: string;
  timestamp: string;
}

interface ConsensusVote {
  strategy: string;
  symbol: string;
  confidence: number;
  direction: string;
}

interface ConsensusData {
  votes?: ConsensusVote[];
  symbols?: string[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SYMBOL_COLORS = seriesColors;

const DIRECTION_STYLES: Record<string, string> = {
  buy: "bg-profit/15 text-profit",
  sell: "bg-loss/15 text-loss",
  hold: "bg-warning/15 text-warning",
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DirectionBadge({ direction }: { direction: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        DIRECTION_STYLES[direction] ?? "bg-border text-muted",
      )}
    >
      {direction === "buy" && <TrendingUp size={12} />}
      {direction === "sell" && <TrendingDown size={12} />}
      {direction === "hold" && <Minus size={12} />}
      {direction}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded-full bg-border">
        <div
          className={cn(
            "h-full rounded-full",
            pct >= 70 ? "bg-profit" : pct >= 40 ? "bg-warning" : "bg-loss",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-muted">{pct}%</span>
    </div>
  );
}

function TypeBadge({ type }: { type: string }) {
  return (
    <span className="rounded-md bg-accent/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-accent">
      {type}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Strategy Card
// ---------------------------------------------------------------------------

function StrategyCard({
  strategy,
  isSelected,
  latestSignal,
  onSelect,
  onToggle,
  onWeightChange,
}: {
  strategy: StrategyData;
  isSelected: boolean;
  latestSignal?: SignalData;
  onSelect: () => void;
  onToggle: () => void;
  onWeightChange: (weight: number) => void;
}) {
  const [localWeight, setLocalWeight] = useState(strategy.weight);
  const [isToggling, setIsToggling] = useState(false);

  const handleWeightChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const w = parseFloat(e.target.value);
    setLocalWeight(w);
  }, []);

  const handleWeightCommit = useCallback(() => {
    if (localWeight !== strategy.weight) {
      onWeightChange(localWeight);
    }
  }, [localWeight, strategy.weight, onWeightChange]);

  const handleToggle = useCallback(
    async (e: React.MouseEvent) => {
      e.stopPropagation();
      setIsToggling(true);
      try {
        await onToggle();
      } finally {
        setIsToggling(false);
      }
    },
    [onToggle],
  );

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-xl border bg-card p-4 text-left transition-all hover:border-accent/40",
        isSelected ? "border-accent ring-1 ring-accent/30" : "border-border",
      )}
    >
      {/* Header row */}
      <div className="mb-3 flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Brain size={16} className={strategy.enabled ? "text-accent" : "text-muted"} />
          <h3 className="text-sm font-medium text-foreground">{strategy.name}</h3>
        </div>
        <TypeBadge type={strategy.type} />
      </div>

      {/* Toggle */}
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs text-muted">{strategy.enabled ? "Enabled" : "Disabled"}</span>
        <button
          type="button"
          onClick={handleToggle}
          className={cn(
            "transition-colors",
            isToggling && "opacity-50",
            strategy.enabled ? "text-profit" : "text-muted",
          )}
        >
          {strategy.enabled ? <ToggleRight size={28} /> : <ToggleLeft size={28} />}
        </button>
      </div>

      {/* Weight slider */}
      <div className="mb-3">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-xs text-muted">Weight</span>
          <span className="text-xs tabular-nums text-foreground">{localWeight.toFixed(2)}</span>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={localWeight}
          onChange={handleWeightChange}
          onMouseUp={handleWeightCommit}
          onTouchEnd={handleWeightCommit}
          onClick={(e) => e.stopPropagation()}
          className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-border accent-accent"
        />
      </div>

      {/* Current signal */}
      {latestSignal && (
        <div className="mb-3 flex items-center gap-2">
          <Activity size={12} className="text-muted" />
          <span className="text-xs text-muted">Signal:</span>
          <DirectionBadge direction={latestSignal.direction} />
          <ConfidenceBar value={latestSignal.confidence} />
        </div>
      )}

      {/* Mini stats */}
      <div className="flex items-center gap-4 border-t border-border/50 pt-3">
        <div className="flex items-center gap-1">
          <BarChart3 size={12} className="text-muted" />
          <span className="text-xs text-muted">Trades:</span>
          <span className="text-xs tabular-nums text-foreground">{strategy.total_trades ?? 0}</span>
        </div>
        <div className="flex items-center gap-1">
          <Target size={12} className="text-muted" />
          <span className="text-xs text-muted">Win:</span>
          <span
            className={cn(
              "text-xs tabular-nums",
              (strategy.win_rate ?? 0) >= 50 ? "text-profit" : "text-loss",
            )}
          >
            {formatPercent(strategy.win_rate ?? 0, 1)}
          </span>
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Consensus Radar
// ---------------------------------------------------------------------------

function ConsensusRadar({
  consensus,
  isLoading,
}: {
  consensus: ConsensusData | undefined;
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <ChartContainer title="Strategy Consensus" subtitle="Votes per symbol">
        <ChartSkeleton height="h-80" />
      </ChartContainer>
    );
  }

  const votes = consensus?.votes;
  if (!votes || votes.length === 0) {
    return (
      <ChartContainer title="Strategy Consensus" subtitle="Votes per symbol">
        <div className="flex h-80 items-center justify-center">
          <p className="text-sm text-muted">No consensus data available</p>
        </div>
      </ChartContainer>
    );
  }

  // Derive unique strategies and symbols from votes
  const strategyNames = Array.from(new Set(votes.map((v) => v.strategy)));
  const symbols = consensus?.symbols ?? Array.from(new Set(votes.map((v) => v.symbol)));

  // Build radar data: one entry per strategy with confidence per symbol
  const radarData = strategyNames.map((name) => {
    const entry: Record<string, string | number> = { strategy: name };
    for (const sym of symbols) {
      const vote = votes.find((v) => v.strategy === name && v.symbol === sym);
      entry[sym] = vote ? Math.round(vote.confidence * 100) : 0;
    }
    return entry;
  });

  return (
    <ChartContainer title="Strategy Consensus" subtitle="Confidence by strategy per symbol">
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="70%">
            <PolarGrid stroke={themeColors.border} />
            <PolarAngleAxis dataKey="strategy" tick={chartAxisTick} />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ ...chartAxisTick, fontSize: 10 }}
              tickCount={5}
            />
            {symbols.map((sym, i) => (
              <Radar
                key={sym}
                name={sym}
                dataKey={sym}
                stroke={SYMBOL_COLORS[i % SYMBOL_COLORS.length]}
                fill={SYMBOL_COLORS[i % SYMBOL_COLORS.length]}
                fillOpacity={0.15}
                strokeWidth={2}
              />
            ))}
            <Legend wrapperStyle={{ fontSize: 12, color: themeColors.muted }} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </ChartContainer>
  );
}

// ---------------------------------------------------------------------------
// Strategy Detail Section
// ---------------------------------------------------------------------------

function StrategyDetail({
  strategy,
  signals,
  isLoadingSignals,
}: {
  strategy: StrategyData;
  signals: SignalData[];
  isLoadingSignals: boolean;
}) {
  // Compute per-strategy performance stats
  const totalTrades = strategy.total_trades ?? 0;
  const buys = signals.filter((s) => s.direction === "buy").length;
  const sells = signals.filter((s) => s.direction === "sell").length;

  const signalColumns = [
    {
      key: "timestamp",
      header: "Time",
      render: (row: SignalData) => (
        <span className="text-xs text-muted">{formatTimeAgo(row.timestamp)}</span>
      ),
    },
    {
      key: "symbol",
      header: "Symbol",
      render: (row: SignalData) => (
        <span className="text-xs font-medium text-foreground">{row.symbol}</span>
      ),
    },
    {
      key: "direction",
      header: "Direction",
      render: (row: SignalData) => <DirectionBadge direction={row.direction} />,
    },
    {
      key: "confidence",
      header: "Confidence",
      render: (row: SignalData) => <ConfidenceBar value={row.confidence} />,
    },
    {
      key: "reasoning",
      header: "Reasoning",
      render: (row: SignalData) => (
        <span className="line-clamp-2 max-w-xs text-xs text-muted">{row.reasoning}</span>
      ),
    },
  ];

  return (
    <div className="rounded-xl border border-border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border p-4">
        <div className="flex items-center gap-3">
          <Brain size={18} className="text-accent" />
          <div>
            <h3 className="text-sm font-medium text-foreground">{strategy.name}</h3>
            {strategy.description && <p className="text-xs text-muted">{strategy.description}</p>}
          </div>
        </div>
        <TypeBadge type={strategy.type} />
      </div>

      {/* Performance stats row */}
      <div className="grid grid-cols-3 gap-4 border-b border-border p-4">
        <div>
          <p className="text-xs text-muted">Total Trades</p>
          <p className="text-lg font-semibold tabular-nums text-foreground">{totalTrades}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Buy Signals</p>
          <p className="text-lg font-semibold tabular-nums text-profit">{buys}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Sell Signals</p>
          <p className="text-lg font-semibold tabular-nums text-loss">{sells}</p>
        </div>
      </div>

      {/* Signal history table */}
      <div className="p-4">
        <h4 className="mb-3 text-xs font-medium text-muted">Signal History</h4>
        {isLoadingSignals ? (
          <TableSkeleton rows={5} />
        ) : (
          <DataTable
            columns={signalColumns}
            data={signals}
            emptyMessage="No signals recorded for this strategy"
            maxRows={20}
          />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function StrategiesPage() {
  const queryClient = useQueryClient();
  const {
    data: rawStrategies,
    isLoading: isLoadingStrategies,
    error: strategiesError,
  } = useStrategies();
  const { data: rawConsensus, isLoading: isLoadingConsensus } = useConsensus();
  const { data: rawSignals } = useSignals({ limit: 100 });

  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);
  const [detailSignals, setDetailSignals] = useState<SignalData[]>([]);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [_mutatingStrategies, setMutatingStrategies] = useState<Set<string>>(new Set());

  // Cast raw data
  const strategies = (rawStrategies ?? []) as unknown as StrategyData[];
  const consensus = rawConsensus as unknown as ConsensusData | undefined;
  const signals = (rawSignals ?? []) as unknown as SignalData[];

  // Build a map of latest signal per strategy
  const latestSignalByStrategy: Record<string, SignalData> = {};
  for (const sig of signals) {
    if (
      !latestSignalByStrategy[sig.strategy] ||
      new Date(sig.timestamp) > new Date(latestSignalByStrategy[sig.strategy].timestamp)
    ) {
      latestSignalByStrategy[sig.strategy] = sig;
    }
  }

  const handleSelectStrategy = useCallback(
    async (name: string) => {
      setSelectedStrategy((prev) => (prev === name ? null : name));
      if (selectedStrategy === name) return; // deselecting
      setIsLoadingDetail(true);
      try {
        const data = await getStrategySignals(name);
        setDetailSignals(data as unknown as SignalData[]);
      } catch {
        setDetailSignals([]);
      } finally {
        setIsLoadingDetail(false);
      }
    },
    [selectedStrategy],
  );

  const handleToggle = useCallback(
    async (name: string, currentEnabled: boolean) => {
      setMutatingStrategies((prev) => new Set(prev).add(name));
      try {
        await updateStrategyEnabled(name, !currentEnabled);
        await queryClient.invalidateQueries({ queryKey: ["strategies"] });
      } finally {
        setMutatingStrategies((prev) => {
          const next = new Set(prev);
          next.delete(name);
          return next;
        });
      }
    },
    [queryClient],
  );

  const handleWeightChange = useCallback(
    async (name: string, weight: number) => {
      setMutatingStrategies((prev) => new Set(prev).add(name));
      try {
        await updateStrategyWeight(name, weight);
        await queryClient.invalidateQueries({ queryKey: ["strategies"] });
      } finally {
        setMutatingStrategies((prev) => {
          const next = new Set(prev);
          next.delete(name);
          return next;
        });
      }
    },
    [queryClient],
  );

  // Selected strategy object
  const selectedStrategyData = strategies.find((s) => s.name === selectedStrategy);

  // ----- Loading state -----
  if (isLoadingStrategies) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Strategies</h1>
          <p className="text-sm text-muted">
            Manage trading strategies, weights, and view consensus signals
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-56 animate-pulse rounded-xl border border-border bg-card" />
          ))}
        </div>
        <ChartSkeleton height="h-80" />
      </div>
    );
  }

  // ----- Error state -----
  if (strategiesError) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Strategies</h1>
          <p className="text-sm text-muted">
            Manage trading strategies, weights, and view consensus signals
          </p>
        </div>
        <div className="flex flex-col items-center justify-center rounded-xl border border-loss/30 bg-loss/5 py-16">
          <AlertCircle size={32} className="mb-3 text-loss" />
          <p className="text-sm font-medium text-loss">Failed to load strategies</p>
          <p className="mt-1 text-xs text-muted">{strategiesError.message}</p>
        </div>
      </div>
    );
  }

  // ----- Empty state -----
  if (strategies.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Strategies</h1>
          <p className="text-sm text-muted">
            Manage trading strategies, weights, and view consensus signals
          </p>
        </div>
        <div className="flex flex-col items-center justify-center rounded-xl border border-border bg-card py-16">
          <Brain size={32} className="mb-3 text-muted" />
          <p className="text-sm text-muted">No strategies configured</p>
          <p className="mt-1 text-xs text-muted">
            Add strategies to your trading bot configuration to see them here
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-lg font-semibold text-foreground">Strategies</h1>
        <p className="text-sm text-muted">
          Manage trading strategies, weights, and view consensus signals
        </p>
      </div>

      {/* Strategy cards grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {strategies.map((s) => (
          <StrategyCard
            key={s.name}
            strategy={s}
            isSelected={selectedStrategy === s.name}
            latestSignal={
              latestSignalByStrategy[s.name] ??
              (s.recent_signals && s.recent_signals.length > 0 ? s.recent_signals[0] : undefined)
            }
            onSelect={() => handleSelectStrategy(s.name)}
            onToggle={() => handleToggle(s.name, s.enabled)}
            onWeightChange={(w) => handleWeightChange(s.name, w)}
          />
        ))}
      </div>

      {/* Consensus radar chart */}
      <ConsensusRadar consensus={consensus} isLoading={isLoadingConsensus} />

      {/* Per-strategy detail section */}
      {selectedStrategyData && (
        <StrategyDetail
          strategy={selectedStrategyData}
          signals={detailSignals}
          isLoadingSignals={isLoadingDetail}
        />
      )}
    </div>
  );
}
