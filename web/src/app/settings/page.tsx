"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getConfig, getMode, setMode, getSymbols, updateSymbols } from "@/lib/api";
import ChartContainer from "@/components/shared/ChartContainer";
import { ChartSkeleton } from "@/components/shared/LoadingSkeleton";
import { Settings, AlertTriangle, X, Plus } from "lucide-react";
import { cn } from "@/lib/formatters";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data: config, isLoading } = useQuery({ queryKey: ["config"], queryFn: getConfig });
  const { data: mode } = useQuery({ queryKey: ["mode"], queryFn: getMode });
  const { data: symbols } = useQuery({ queryKey: ["symbols"], queryFn: getSymbols });

  const [showModeWarning, setShowModeWarning] = useState(false);
  const [newStock, setNewStock] = useState("");
  const [newCrypto, setNewCrypto] = useState("");

  const modeMutation = useMutation({
    mutationFn: (m: string) => setMode(m),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["mode"] }),
  });

  const symbolsMutation = useMutation({
    mutationFn: (s: { stocks: string[]; crypto: string[] }) => updateSymbols(s),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["symbols"] }),
  });

  const currentMode = mode?.mode || "paper";
  const stocks = symbols?.stocks || [];
  const crypto = symbols?.crypto || [];

  const handleModeToggle = () => {
    if (currentMode === "paper") {
      setShowModeWarning(true);
    } else {
      modeMutation.mutate("paper");
    }
  };

  const confirmLiveMode = () => {
    modeMutation.mutate("live");
    setShowModeWarning(false);
  };

  const addStock = () => {
    if (newStock.trim() && !stocks.includes(newStock.trim().toUpperCase())) {
      symbolsMutation.mutate({ stocks: [...stocks, newStock.trim().toUpperCase()], crypto });
      setNewStock("");
    }
  };

  const addCrypto = () => {
    if (newCrypto.trim() && !crypto.includes(newCrypto.trim())) {
      symbolsMutation.mutate({ stocks, crypto: [...crypto, newCrypto.trim()] });
      setNewCrypto("");
    }
  };

  const removeStock = (s: string) => symbolsMutation.mutate({ stocks: stocks.filter((x) => x !== s), crypto });
  const removeCrypto = (s: string) => symbolsMutation.mutate({ stocks, crypto: crypto.filter((x) => x !== s) });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Settings</h1>

      {/* Mode toggle */}
      <ChartContainer title="Trading Mode">
        <div className="flex items-center gap-4">
          <button
            onClick={handleModeToggle}
            className={cn(
              "relative h-8 w-16 rounded-full transition-colors",
              currentMode === "live" ? "bg-loss" : "bg-profit"
            )}
          >
            <div className={cn(
              "absolute top-1 h-6 w-6 rounded-full bg-white transition-transform",
              currentMode === "live" ? "translate-x-9" : "translate-x-1"
            )} />
          </button>
          <div>
            <p className="text-sm font-medium">
              {currentMode === "paper" ? "Paper Trading" : "Live Trading"}
            </p>
            <p className="text-xs text-muted">
              {currentMode === "paper"
                ? "Simulated trades with no real money"
                : "CAUTION: Real money at risk"}
            </p>
          </div>
        </div>
      </ChartContainer>

      {/* Live mode warning modal */}
      {showModeWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-loss/30 bg-card p-6">
            <div className="flex items-center gap-3 text-loss">
              <AlertTriangle size={24} />
              <h3 className="text-lg font-semibold">Switch to Live Trading?</h3>
            </div>
            <p className="mt-3 text-sm text-muted">
              Live mode will execute real trades with real money. Make sure your exchange connections
              and risk limits are properly configured.
            </p>
            <div className="mt-6 flex gap-3">
              <button
                onClick={() => setShowModeWarning(false)}
                className="flex-1 rounded-lg border border-border py-2 text-sm text-muted hover:bg-card-hover"
              >
                Cancel
              </button>
              <button
                onClick={confirmLiveMode}
                className="flex-1 rounded-lg bg-loss py-2 text-sm font-medium text-white hover:bg-loss/80"
              >
                Enable Live Mode
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        {/* Stock symbols */}
        <ChartContainer title="Stock Symbols" subtitle="Equity watchlist">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {stocks.map((s) => (
                <span key={s} className="flex items-center gap-1 rounded-lg bg-background px-2.5 py-1 text-sm">
                  {s}
                  <button onClick={() => removeStock(s)} className="text-muted hover:text-loss">
                    <X size={12} />
                  </button>
                </span>
              ))}
              {stocks.length === 0 && <p className="text-xs text-muted">No stocks configured</p>}
            </div>
            <div className="flex gap-2">
              <input
                value={newStock}
                onChange={(e) => setNewStock(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addStock()}
                placeholder="Add symbol..."
                className="flex-1 rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted/50"
              />
              <button onClick={addStock} className="rounded-lg bg-accent px-3 py-1.5 text-sm text-white hover:bg-accent-hover">
                <Plus size={14} />
              </button>
            </div>
          </div>
        </ChartContainer>

        {/* Crypto symbols */}
        <ChartContainer title="Crypto Symbols" subtitle="Cryptocurrency watchlist">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {crypto.map((s) => (
                <span key={s} className="flex items-center gap-1 rounded-lg bg-background px-2.5 py-1 text-sm">
                  {s}
                  <button onClick={() => removeCrypto(s)} className="text-muted hover:text-loss">
                    <X size={12} />
                  </button>
                </span>
              ))}
              {crypto.length === 0 && <p className="text-xs text-muted">No crypto configured</p>}
            </div>
            <div className="flex gap-2">
              <input
                value={newCrypto}
                onChange={(e) => setNewCrypto(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addCrypto()}
                placeholder="Add pair (e.g. BTC/USD)..."
                className="flex-1 rounded-lg border border-border bg-background px-3 py-1.5 text-sm text-foreground placeholder:text-muted/50"
              />
              <button onClick={addCrypto} className="rounded-lg bg-accent px-3 py-1.5 text-sm text-white hover:bg-accent-hover">
                <Plus size={14} />
              </button>
            </div>
          </div>
        </ChartContainer>
      </div>

      {/* Full config display */}
      <ChartContainer title="Full Configuration" subtitle="Read-only view of current settings">
        {isLoading ? (
          <ChartSkeleton height="h-48" />
        ) : (
          <pre className="max-h-96 overflow-auto rounded-lg bg-background p-4 text-xs text-muted">
            {JSON.stringify(config, null, 2)}
          </pre>
        )}
      </ChartContainer>
    </div>
  );
}
