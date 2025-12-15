'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import ChatPage from '@/components/chat-page'

export default function Home() {
  const router = useRouter()

  useEffect(() => {
    // 認証チェック
    const token = document.cookie.split('; ').find(row => row.startsWith('grag_session='))
    if (!token) {
      router.push('/login')
    }
  }, [router])

  return <ChatPage />
}

