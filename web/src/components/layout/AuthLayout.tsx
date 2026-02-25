"use client";

import { usePathname } from "next/navigation";
import AuthGuard from "@/components/auth/AuthGuard";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import WebSocketProvider from "@/components/layout/WebSocketProvider";
import NotificationProvider from "@/components/notifications/NotificationProvider";

const AUTH_PAGES = ["/login", "/signup"];

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAuthPage = AUTH_PAGES.includes(pathname);

  return (
    <AuthGuard>
      {isAuthPage ? (
        // Auth pages render without sidebar/header
        <>{children}</>
      ) : (
        // Dashboard pages get the full chrome
        <>
          <Sidebar />
          <div className="pl-56 transition-all duration-200">
            <Header />
            <main className="p-8">{children}</main>
          </div>
          <WebSocketProvider />
          <NotificationProvider />
        </>
      )}
    </AuthGuard>
  );
}
