import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Header from "@/components/layout/Header";
import Providers from "@/components/layout/Providers";
import Sidebar from "@/components/layout/Sidebar";
import WebSocketProvider from "@/components/layout/WebSocketProvider";
import NotificationProvider from "@/components/notifications/NotificationProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TradeBot Dashboard",
  description: "AI-powered trading bot dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Providers>
          <Sidebar />
          <div className="pl-56 transition-all duration-200">
            <Header />
            <main className="p-8">{children}</main>
          </div>
          <WebSocketProvider />
          <NotificationProvider />
        </Providers>
      </body>
    </html>
  );
}
