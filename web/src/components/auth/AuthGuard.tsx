"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/authStore";

const PUBLIC_PATHS = ["/login", "/signup"];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, loadFromStorage } = useAuthStore();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    loadFromStorage();
  }, [loadFromStorage]);

  // Still loading — show spinner
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  const isPublicPage = PUBLIC_PATHS.includes(pathname);

  // Not authenticated + not on a public page → redirect to login
  if (!isAuthenticated && !isPublicPage) {
    router.replace("/login");
    return null;
  }

  // Authenticated + on login/signup → redirect to dashboard
  if (isAuthenticated && isPublicPage) {
    router.replace("/");
    return null;
  }

  return <>{children}</>;
}
