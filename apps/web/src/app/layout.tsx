import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Shell } from "@/components/shell";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Helm — the CFO that checks before it pays",
  description: "Helm releases a payment only if the forecast says the business stays above its minimum cash balance.",
};

// Apply the saved theme before first paint to avoid a flash.
const themeInit = `try{var t=localStorage.getItem("helm-theme");if(t==="dark")document.documentElement.dataset.theme="dark"}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
