import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";

export const metadata: Metadata = {
  title: "OmniVigil — Smart Predictive Maintenance",
  description: "Cloud-native predictive maintenance platform powered by AI for real-time monitoring, anomaly detection, and automated work orders.",
  keywords: "predictive maintenance, IoT, AI, anomaly detection, industry 4.0",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="th">
      <body suppressHydrationWarning>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
