'use client' // Mark this as a Client Component

import * as React from 'react'
import { WagmiProvider } from 'wagmi'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { config } from '@/lib/wagmi' // Import your Wagmi config
import { Toaster } from "@/components/ui/sonner" // Import the toaster

// Create a React Query client
const queryClient = new QueryClient()

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster richColors position="top-right" /> {/* Add Toaster for notifications */}
      </QueryClientProvider>
    </WagmiProvider>
  )
} 