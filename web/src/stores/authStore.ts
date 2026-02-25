import { create } from "zustand";
import type { User } from "@/lib/schemas";

const TOKEN_KEY = "trade_bot_access_token";
const REFRESH_KEY = "trade_bot_refresh_token";
const USER_KEY = "trade_bot_user";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  setAuth: (user: User, accessToken: string, refreshToken: string) => void;
  setAccessToken: (token: string) => void;
  logout: () => void;
  loadFromStorage: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: true,

  setAuth: (user, accessToken, refreshToken) => {
    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_KEY, refreshToken);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ user, accessToken, refreshToken, isAuthenticated: true, isLoading: false });
  },

  setAccessToken: (token) => {
    localStorage.setItem(TOKEN_KEY, token);
    set({ accessToken: token });
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  loadFromStorage: () => {
    const accessToken = localStorage.getItem(TOKEN_KEY);
    const refreshToken = localStorage.getItem(REFRESH_KEY);
    const userJson = localStorage.getItem(USER_KEY);

    if (accessToken && refreshToken && userJson) {
      try {
        const user = JSON.parse(userJson) as User;
        set({ user, accessToken, refreshToken, isAuthenticated: true, isLoading: false });
        return;
      } catch {
        // Corrupted storage — clear it
      }
    }
    set({ isLoading: false });
  },

  setLoading: (loading) => set({ isLoading: loading }),
}));
