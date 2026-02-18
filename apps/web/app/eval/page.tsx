'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/sidebar'
import { apiRequest } from '@/lib/auth'

export default function EvalPage() {
  const router = useRouter()
  useEffect(() => {
    const token = document.cookie.split('; ').find(row => row.startsWith('grag_session='))
    if (!token) router.push('/login')
  }, [router])
  const [markdown, setMarkdown] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadResults = async () => {
    setLoading(true)
    setError(null)
    setMarkdown(null)
    try {
      const res = await apiRequest('/eval/results')
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        setError((data && data.detail) || '結果の取得に失敗しました')
        return
      }
      setMarkdown(data.markdown ?? '')
    } catch (err) {
      console.error(err)
      setError('API に接続できません。API が起動しているか確認してください。')
    } finally {
      setLoading(false)
    }
  }

  const downloadResults = () => {
    if (!markdown) return
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `eval_results_${new Date().toISOString().slice(0, 10)}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 p-8 overflow-y-auto">
        <h1 className="text-2xl font-bold mb-2">評価（Eval）</h1>
        <p className="text-muted-foreground mb-6">
          RAG の設定（top_k・rerank など）ごとの応答時間・引用数を比較する評価結果を表示します。
          結果を取得する前に、API を起動した状態でターミナルから <code className="px-1 py-0.5 bg-muted rounded text-sm">eval/run_eval.py</code> を実行してください。
        </p>

        <div className="flex gap-2 mb-4">
          <button
            onClick={loadResults}
            disabled={loading}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? '読み込み中...' : '結果を読み込む'}
          </button>
          {markdown && (
            <button
              onClick={downloadResults}
              type="button"
              className="px-4 py-2 border border-input rounded-md bg-background hover:bg-muted"
            >
              結果をダウンロード（.md）
            </button>
          )}
        </div>

        {error && (
          <div className="mb-4 p-3 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md">
            {error}
          </div>
        )}

        {markdown !== null && (
          <div className="mt-4 p-4 border rounded-md bg-card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-semibold">評価結果</h2>
              <button
                onClick={downloadResults}
                type="button"
                className="text-sm px-3 py-1.5 border border-input rounded-md bg-background hover:bg-muted"
              >
                ダウンロード
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-sm overflow-x-auto max-h-[60vh] overflow-y-auto font-sans">
              {markdown}
            </pre>
          </div>
        )}

        {!markdown && !loading && !error && (
          <p className="text-sm text-muted-foreground">
            「結果を読み込む」をクリックすると、直前に実行した評価結果（eval/results.md）を表示します。
          </p>
        )}
      </div>
    </div>
  )
}
