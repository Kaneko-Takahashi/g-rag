'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { login, setAuthToken } from '@/lib/auth'

export default function LoginForm() {
  const [passcode, setPasscode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const { token } = await login(passcode)
      setAuthToken(token)
      router.push('/')
    } catch (err) {
      setError('ログインに失敗しました')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-md space-y-8 p-8 bg-card rounded-lg border">
      <div className="text-center">
        <h1 className="text-3xl font-bold">G-RAG</h1>
        <p className="mt-2 text-muted-foreground">ログインしてください</p>
        <p className="mt-1 text-xs text-muted-foreground">DEMO MODE</p>
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="passcode" className="block text-sm font-medium mb-2">
            パスコード
          </label>
          <input
            id="passcode"
            type="password"
            value={passcode}
            onChange={(e) => setPasscode(e.target.value)}
            className="w-full px-3 py-2 border rounded-md bg-background"
            placeholder="任意のパスコード"
            required
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-2 px-4 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? 'ログイン中...' : 'ログイン'}
        </button>
      </form>
    </div>
  )
}

