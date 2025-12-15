'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import ChatPage from '@/components/chat-page'

export default function Home() {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    // 認証チェック
    const token = document.cookie.split('; ').find(row => row.startsWith('grag_session='))
    if (!token) {
      router.push('/login')
    } else {
      setIsAuthenticated(true)
    }
  }, [router])

  // 認証チェック中は何も表示しない
  if (isAuthenticated === null) {
    return null
  }

  // 認証済みの場合のみChatPageを表示
  if (!isAuthenticated) {
    return null
  }

  return <ChatPage />
}

