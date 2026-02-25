import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "../authStore";

const mockUser = {
  id: "user-1",
  email: "test@example.com",
  name: "Test User",
  is_active: true,
  is_verified: false,
};

// Mock localStorage
const storage: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, value: string) => {
    storage[key] = value;
  },
  removeItem: (key: string) => {
    delete storage[key];
  },
});

describe("useAuthStore", () => {
  beforeEach(() => {
    // Clear storage and reset store
    for (const key of Object.keys(storage)) delete storage[key];
    useAuthStore.setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: true,
    });
  });

  it("starts unauthenticated with isLoading true", () => {
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.isLoading).toBe(true);
  });

  it("setAuth stores user and tokens", () => {
    useAuthStore.getState().setAuth(mockUser, "access-123", "refresh-456");
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user?.email).toBe("test@example.com");
    expect(state.accessToken).toBe("access-123");
    expect(state.refreshToken).toBe("refresh-456");
    expect(state.isLoading).toBe(false);
  });

  it("setAuth persists to localStorage", () => {
    useAuthStore.getState().setAuth(mockUser, "access-123", "refresh-456");
    expect(storage.trade_bot_access_token).toBe("access-123");
    expect(storage.trade_bot_refresh_token).toBe("refresh-456");
    expect(JSON.parse(storage.trade_bot_user).email).toBe("test@example.com");
  });

  it("logout clears state and localStorage", () => {
    useAuthStore.getState().setAuth(mockUser, "access-123", "refresh-456");
    useAuthStore.getState().logout();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(storage.trade_bot_access_token).toBeUndefined();
    expect(storage.trade_bot_refresh_token).toBeUndefined();
  });

  it("loadFromStorage restores auth state", () => {
    storage.trade_bot_access_token = "stored-access";
    storage.trade_bot_refresh_token = "stored-refresh";
    storage.trade_bot_user = JSON.stringify(mockUser);

    useAuthStore.getState().loadFromStorage();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user?.id).toBe("user-1");
    expect(state.accessToken).toBe("stored-access");
    expect(state.isLoading).toBe(false);
  });

  it("loadFromStorage handles missing tokens", () => {
    useAuthStore.getState().loadFromStorage();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
  });

  it("loadFromStorage handles corrupted user JSON", () => {
    storage.trade_bot_access_token = "token";
    storage.trade_bot_refresh_token = "refresh";
    storage.trade_bot_user = "not-json{{{";

    useAuthStore.getState().loadFromStorage();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
  });

  it("setAccessToken updates token in state and storage", () => {
    useAuthStore.getState().setAuth(mockUser, "old-token", "refresh-456");
    useAuthStore.getState().setAccessToken("new-token");
    expect(useAuthStore.getState().accessToken).toBe("new-token");
    expect(storage.trade_bot_access_token).toBe("new-token");
  });
});
