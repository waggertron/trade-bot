"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Cpu, Database, Layers, Play, Target } from "lucide-react";
import { useState } from "react";
import ChartContainer from "@/components/shared/ChartContainer";
import DataTable from "@/components/shared/DataTable";
import {
  getFeatureCatalog,
  getFeatureStatus,
  getMLModels,
  getPredictions,
  triggerTraining,
} from "@/lib/api";
import { cn } from "@/lib/formatters";

const tabs = ["Feature Catalog", "Models", "Predictions"] as const;
type Tab = (typeof tabs)[number];

export default function MLPage() {
  const [activeTab, setActiveTab] = useState<Tab>("Feature Catalog");
  const { data: catalog } = useQuery({ queryKey: ["feature-catalog"], queryFn: getFeatureCatalog });
  const { data: featureStatus } = useQuery({
    queryKey: ["feature-status"],
    queryFn: getFeatureStatus,
  });
  const { data: models } = useQuery({ queryKey: ["ml-models"], queryFn: getMLModels });
  const { data: predictions } = useQuery({ queryKey: ["ml-predictions"], queryFn: getPredictions });

  const trainMutation = useMutation({ mutationFn: triggerTraining });

  const catalogData = (catalog || {}) as Record<string, string[]>;
  const modelList = (models || []) as Record<string, unknown>[];
  const predData = (predictions || {}) as Record<string, unknown>;
  const status = (featureStatus || {}) as Record<string, unknown>;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">ML & Features</h1>

      {/* Status bar */}
      <div className="grid grid-cols-4 gap-4">
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4">
          <Database size={18} className="text-accent" />
          <div>
            <p className="text-xs text-muted">Feature Engine</p>
            <p className="text-sm font-medium capitalize">{(status.status as string) || "idle"}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4">
          <Layers size={18} className="text-accent" />
          <div>
            <p className="text-xs text-muted">Features Available</p>
            <p className="text-sm font-medium">{Object.values(catalogData).flat().length}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card p-4">
          <Cpu size={18} className="text-accent" />
          <div>
            <p className="text-xs text-muted">Trained Models</p>
            <p className="text-sm font-medium">{modelList.length}</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => trainMutation.mutate()}
          disabled={trainMutation.isPending}
          className="flex items-center justify-center gap-2 rounded-xl border border-accent bg-accent/10 p-4 text-sm font-medium text-accent hover:bg-accent/20 disabled:opacity-50"
        >
          {trainMutation.isPending ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          ) : (
            <Play size={16} />
          )}
          {trainMutation.isPending ? "Training..." : "Train Models"}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-lg bg-card p-1">
        {tabs.map((tab) => (
          <button
            type="button"
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "rounded-md px-4 py-2 text-sm transition-colors",
              activeTab === tab ? "bg-accent text-white" : "text-muted hover:text-foreground",
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "Feature Catalog" && (
        <div className="grid grid-cols-2 gap-4">
          {Object.entries(catalogData).map(([category, features]) => (
            <ChartContainer
              key={category}
              title={category}
              subtitle={`${features.length} features`}
            >
              <div className="flex flex-wrap gap-2">
                {features.map((f) => (
                  <span key={f} className="rounded-lg bg-background px-2.5 py-1 text-xs text-muted">
                    {f}
                  </span>
                ))}
              </div>
            </ChartContainer>
          ))}
        </div>
      )}

      {activeTab === "Models" && (
        <ChartContainer title="Trained Models">
          {modelList.length === 0 ? (
            <div className="py-16 text-center text-muted">
              <Cpu size={32} className="mx-auto mb-3" />
              <p className="text-sm">No models trained yet</p>
              <p className="mt-1 text-xs">Click &quot;Train Models&quot; to start training</p>
            </div>
          ) : (
            <DataTable
              columns={[
                { key: "name", header: "Model" },
                { key: "type", header: "Type" },
                { key: "accuracy", header: "Accuracy", className: "text-right" },
                { key: "last_trained", header: "Last Trained" },
              ]}
              data={modelList}
              emptyMessage="No models"
            />
          )}
        </ChartContainer>
      )}

      {activeTab === "Predictions" && (
        <ChartContainer title="Latest Predictions" subtitle="By symbol">
          {Object.keys(predData).length === 0 ? (
            <div className="py-16 text-center text-muted">
              <Target size={32} className="mx-auto mb-3" />
              <p className="text-sm">No predictions available</p>
              <p className="mt-1 text-xs">Train models and run predictions to see results</p>
            </div>
          ) : (
            <div className="space-y-3">
              {Object.entries(predData).map(([symbol, pred]) => (
                <div key={symbol} className="rounded-lg bg-background p-4">
                  <p className="text-sm font-medium">{symbol}</p>
                  <pre className="mt-2 text-xs text-muted">{JSON.stringify(pred, null, 2)}</pre>
                </div>
              ))}
            </div>
          )}
        </ChartContainer>
      )}
    </div>
  );
}
