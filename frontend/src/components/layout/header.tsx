'use client'

import { ConnectWalletButton } from '@/components/auth/connect-wallet-button'
import Link from 'next/link'

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 max-w-screen-2xl items-center">
        <div className="mr-4 hidden md:flex">
          <Link href="/" className="mr-6 flex items-center space-x-2">
            {/* <Icons.logo className="h-6 w-6" /> */}
            <span className="hidden font-bold sm:inline-block">
              VeriFAI
            </span>
          </Link>
          {/* <nav className="flex items-center gap-6 text-sm">
            <Link
              href="/docs"
              className={cn(
                "transition-colors hover:text-foreground/80",
                pathname === "/docs" ? "text-foreground" : "text-foreground/60"
              )}
            >
              Docs
            </Link>
            </nav> */}
        </div>
        <div className="flex flex-1 items-center justify-end space-x-2">
          <ConnectWalletButton />
        </div>
      </div>
    </header>
  )
} 