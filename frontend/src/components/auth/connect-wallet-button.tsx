'use client'

import * as React from 'react'
import { useAccount, useConnect, useSignMessage } from 'wagmi'
import { SiweMessage } from 'siwe'
import axios, { isAxiosError } from 'axios' // For backend calls
import { Button } from '@/components/ui/button'
import { toast } from "sonner"
import { Connector } from 'wagmi' // Import Connector type

// Simple session state (replace with more robust state management if needed)
// In a real app, you might store the JWT token in localStorage/sessionStorage
// or use a state management library and context.
let sessionCache: { address: string; chainId: number; token: string } | null = null

// Get backend URL from environment variable
const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000'

export function ConnectWalletButton() {
  const { address, chainId, isConnected } = useAccount()
  const { connectors, connect } = useConnect()
  const { signMessageAsync } = useSignMessage()
  const [isSigningIn, setIsSigningIn] = React.useState(false)
  const [session, setSession] = React.useState(sessionCache)

  React.useEffect(() => {
    // Check if session exists on component mount (e.g., from previous verification)
    // This is a basic check; real apps would use token storage
    if (sessionCache && sessionCache.address === address && sessionCache.chainId === chainId) {
      setSession(sessionCache)
    } else {
        // Clear session if account changes
        sessionCache = null
        setSession(null)
    }
  }, [address, chainId])

  const handleSignIn = async () => {
    if (!address || !chainId) return
    setIsSigningIn(true)
    const connector = connectors[0] // Assuming MetaMask or first connector
    if (!connector) {
        toast.error("No wallet connector found.")
        setIsSigningIn(false)
        return
    }

    try {
      // 1. Get nonce from backend
      const nonceRes = await axios.get(`${backendUrl}/auth/nonce`)
      const nonce = nonceRes.data.nonce
      if (!nonce) throw new Error("Failed to get nonce from backend.")

      // 2. Create SIWE message
      const message = new SiweMessage({
        domain: window.location.host,
        address,
        statement: 'Sign in with Ethereum to the VeriFAI app.',
        uri: window.location.origin,
        version: '1',
        chainId: chainId,
        nonce: nonce,
      })

      // 3. Sign message
      const signature = await signMessageAsync({ message: message.prepareMessage() })

      // 4. Verify signature with backend
      // Construct a plain object with snake_case keys matching backend expectations
      const messageToSend = {
        domain: message.domain,
        address: message.address,
        statement: message.statement,
        uri: message.uri,
        version: message.version,
        chain_id: message.chainId, // Map to snake_case
        nonce: message.nonce,
        issued_at: message.issuedAt, // Map to snake_case
        // Include other optional fields if needed by backend validation
        // expiration_time: message.expirationTime,
        // not_before: message.notBefore,
        // request_id: message.requestId,
        // resources: message.resources // If you use resources
      };

      const verifyRes = await axios.post(`${backendUrl}/auth/verify`, {
        message: messageToSend, // Send the constructed plain object
        signature,
      })

      // 5. Handle successful verification (store session/token)
       const verifiedAddress = verifyRes.data.address
       const token = verifyRes.data.access_token

      if (verifiedAddress === address && token) {
          // Store session (basic in-memory example)
          sessionCache = { address, chainId, token }
          setSession(sessionCache)
          toast.success(`Signed in as ${address.substring(0, 6)}...${address.substring(address.length - 4)}`)
          // In a real app, store the JWT `token` securely for subsequent requests
          // e.g., localStorage.setItem('authToken', token);
      } else {
          throw new Error("Verification response invalid.")
      }

    } catch (error: unknown) {
      console.error("Sign-in error:", error)
      sessionCache = null
      setSession(null)
      let detail = "An unknown error occurred."
      if (isAxiosError(error)) {
        // Safely access Axios error details
        detail = error.response?.data?.detail || error.message
      } else if (error instanceof Error) {
        detail = error.message
      }
      toast.error(`Sign-in failed: ${detail}`)
    } finally {
      setIsSigningIn(false)
    }
  }

  const handleSignOut = () => {
    sessionCache = null
    setSession(null)
    // No need to call disconnect() here usually, user disconnects from wallet extension
    // If you want to force app state disconnect:
    // disconnect();
    toast.info("Signed out.")
     // Clear token from storage
    // e.g., localStorage.removeItem('authToken');
  }

  if (isConnected) {
    // User wallet is connected
    if (session && session.address === address) {
      // User is signed in (SIWE verified)
      return (
        <div className="flex items-center gap-2">
           <span className="text-sm text-muted-foreground hidden sm:inline">
            {`${address.substring(0, 6)}...${address.substring(address.length - 4)}`}
          </span>
          <Button variant="outline" size="sm" onClick={handleSignOut}>
            Sign Out
          </Button>
        </div>
      )
    } else {
      // Wallet connected, but not signed in via SIWE
      return (
         <Button size="sm" onClick={handleSignIn} disabled={isSigningIn}>
            {isSigningIn ? 'Signing In...' : 'Sign In With Wallet'}
          </Button>
      )
    }
  } else {
    // Wallet not connected
    return (
      <Button
        size="sm"
        onClick={() => {
            // Prefer MetaMask if available
            const metaMaskConnector = connectors.find((c: Connector) => c.id === 'metaMask')
            connect({ connector: metaMaskConnector || connectors[0] })
        }}
      >
        Connect Wallet
      </Button>
    )
  }
}

// Helper function to get stored token (example)
export function getAuthToken(): string | null {
    if (sessionCache) {
        return sessionCache.token
    }
    // In real app, read from localStorage:
    // return localStorage.getItem('authToken');
    return null;
} 