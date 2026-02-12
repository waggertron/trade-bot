import { create } from "zustand";

interface UIState {
  sidebarCollapsed: boolean;
  selectedSymbol: string;
  toggleSidebar: () => void;
  setSelectedSymbol: (symbol: string) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  selectedSymbol: "BTC/USD",
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSelectedSymbol: (symbol) => set({ selectedSymbol: symbol }),
}));
