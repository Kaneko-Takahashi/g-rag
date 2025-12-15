'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import BenchPage from '@/components/bench-page'

export default function Bench() {
  const router = useRouter()

  useEffect(() => {
    const token = document.cookie.split('; ').find(row => row.startsWith('grag_session='))
    if (!token) {
      router.push('/login')
    }
  }, [router])

  return <BenchPage />
}

