'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { logout } from '@/lib/auth'
import { MessageSquare, BarChart3, FileText, Shield, Settings, LogOut } from 'lucide-react'

export default function Sidebar() {
  const pathname = usePathname()

  const navItems = [
    { href: '/', label: 'Chat', icon: MessageSquare },
    { href: '/bench', label: 'Bench', icon: BarChart3 },
    { href: '/eval', label: 'Eval', icon: FileText },
    { href: '/audit', label: 'Audit', icon: Shield },
    { href: '/settings', label: 'Settings', icon: Settings },
  ]

  return (
    <div className="w-64 h-screen bg-card border-r flex flex-col">
      <div className="p-4 border-b">
        <h1 className="text-xl font-bold">G-RAG</h1>
      </div>
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-md ${
                isActive ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span>{item.label}</span>
            </Link>
          )
        })}
      </nav>
      <div className="p-4 border-t">
        <button
          onClick={logout}
          className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-muted w-full"
        >
          <LogOut className="w-5 h-5" />
          <span>Logout</span>
        </button>
      </div>
    </div>
  )
}

