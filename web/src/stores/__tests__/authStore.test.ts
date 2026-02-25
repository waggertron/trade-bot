import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "../authStore";

const mockUser = {
  id: "user-1",
  email: "test@example.com",
  name: "Test User",
  is_active: true,
  is_verified: false,
};

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("useAuthStore", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    useAuthStore.setState({
      user: null,
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

  it("setAuth stores user in memory", () => {
    useAuthStore.getState().setAuth(mockUser);
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user?.email).toBe("test@example.com");
    expect(state.isLoading).toBe(false);
  });

  it("logout clears state and calls logout API", async () => {
    mockFetch.mockResolvedValueOnce({ ok: true });
    useAuthStore.getState().setAuth(mockUser);
    await useAuthStore.getState().logout();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(mockFetch).toHaveBeenCalledWith("/api/auth/logout", {
      method: "POST",
      credentials: "include",
    });
  });

  it("logout clears state even if API call fails", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    useAuthStore.getState().setAuth(mockUser);
    await useAuthStore.getState().logout();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
  });

  it("checkAuth sets authenticated when /me succeeds", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockUser),
    });
    await useAuthStore.getState().checkAuth();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user?.id).toBe("user-1");
    expect(state.isLoading).toBe(false);
  });

  it("checkAuth sets unauthenticated when /me fails", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 401 });
    await useAuthStore.getState().checkAuth();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
  });

  it("checkAuth handles network error gracefully", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    await useAuthStore.getState().checkAuth();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
  });
});
