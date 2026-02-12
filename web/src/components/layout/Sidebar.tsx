"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  CandlestickChart,
  Wallet,
  Brain,
  BarChart3,
  ShieldAlert,
  FlaskConical,
  Newspaper,
  Cpu,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useUIStore } from "@/stores/uiStore";
import { cn } from "@/lib/formatters";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/trading", label: "Trading", icon: CandlestickChart },
  { href: "/portfolio", label: "Portfolio", icon: Wallet },
  { href: "/strategies", label: "Strategies", icon: Brain },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/risk", label: "Risk", icon: ShieldAlert },
  { href: "/backtest", label: "Backtest", icon: FlaskConical },
  { href: "/news", label: "News", icon: Newspaper },
  { href: "/ml", label: "ML", icon: Cpu },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 h-screen border-r border-border bg-card transition-all duration-200",
        sidebarCollapsed ? "w-16" : "w-56"
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-border px-4">
        {!sidebarCollapsed && (
          <span className="text-sm font-semibold tracking-wide text-foreground">
            TradeBot
          </span>
        )}
        <button
          onClick={toggleSidebar}
          className="rounded p-1 text-muted hover:bg-card-hover hover:text-foreground"
        >
          {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <nav className="flex flex-col gap-1 p-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                isActive
                  ? "bg-accent/10 text-accent"
                  : "text-muted hover:bg-card-hover hover:text-foreground"
              )}
            >
              <item.icon size={18} />
              {!sidebarCollapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
