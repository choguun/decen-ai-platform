import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "../globals.css"; // Go up one directory to find globals.css in src/
import { Providers } from "./providers"; // Assuming providers.tsx is in the same dir
import { cn } from "@/lib/utils"; // Import cn utility from shadcn setup
import { Toaster } from "@/components/ui/sonner"; // Ensure Toaster is imported here

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" }); // Added variable for Tailwind

export const metadata: Metadata = {
  title: "VeriFAI Platform", // Updated title
  description: "Decentralized AI Platform with Filecoin & FVM Provenance",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning> {/* Added suppressHydrationWarning for Wagmi/Next */} 
      <body
        className={cn(
          "min-h-screen bg-background font-sans antialiased",
          inter.variable
        )}
      >
        {/* Wrap children with Providers */}
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
