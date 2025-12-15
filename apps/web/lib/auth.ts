/**
 * 認証ユーティリティ
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function login(passcode: string): Promise<{ token: string; user_id: string }> {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ passcode }),
  })
  if (!res.ok) throw new Error('Login failed')
  const data = await res.json()
  return data
}

export function setAuthToken(token: string) {
  document.cookie = `grag_session=${token}; path=/; max-age=86400; SameSite=Lax`
}

export function getAuthToken(): string | null {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(/grag_session=([^;]+)/)
  return match ? match[1] : null
}

export function logout() {
  document.cookie = 'grag_session=; path=/; max-age=0'
  window.location.href = '/login'
}

export async function apiRequest(url: string, options: RequestInit = {}) {
  const token = getAuthToken()
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  }
  return fetch(`${API_URL}${url}`, { ...options, headers })
}

