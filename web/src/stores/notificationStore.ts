import { create } from "zustand";

export interface Notification {
  id: string;
  type: "info" | "success" | "warning" | "error";
  title: string;
  message?: string;
  timestamp: number;
}

interface NotificationState {
  notifications: Notification[];
  add: (n: Omit<Notification, "id" | "timestamp">) => void;
  dismiss: (id: string) => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  add: (n) =>
    set((s) => ({
      notifications: [
        ...s.notifications,
        {
          ...n,
          id:
            typeof crypto !== "undefined" && crypto.randomUUID
              ? crypto.randomUUID()
              : `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          timestamp: Date.now(),
        },
      ].slice(-20),
    })),
  dismiss: (id) =>
    set((s) => ({
      notifications: s.notifications.filter((n) => n.id !== id),
    })),
}));
