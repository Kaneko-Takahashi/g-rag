'use client'

import { useState } from 'react'
import Sidebar from './sidebar'
import { apiRequest } from '@/lib/auth'

export default function BenchPage() {
  const [questions, setQuestions] = useState<string[]>([''])
  const [runs, setRuns] = useState(3)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const validQuestions = questions.filter(q => q.trim())
  const canRun = validQuestions.length > 0 && !loading

  const handleRun = async () => {
    if (!canRun) return
    setLoading(true)
    setError(null)
    setResults(null)
    try {
      const res = await apiRequest('/bench', {
        method: 'POST',
        body: JSON.stringify({
          questions: validQuestions,
          runs,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'ベンチマークに失敗しました')
        return
      }
      setResults(data)
    } catch (err: unknown) {
      console.error(err)
      const msg = err instanceof Error ? err.message : '接続エラー'
      setError(`API に接続できません。API が起動しているか確認してください。（${msg}）`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 p-8 overflow-y-auto">
        <h1 className="text-2xl font-bold mb-6">Benchmark</h1>
        <div className="space-y-4 max-w-2xl">
          <div>
            <label htmlFor="bench-questions" className="block text-sm font-medium mb-2">
              質問（1行1問）
            </label>
            <textarea
              id="bench-questions"
              value={questions.join('\n')}
              onChange={(e) => setQuestions(e.target.value.split('\n'))}
              className="w-full h-32 px-3 py-2 border rounded-md bg-background"
              placeholder={'RAGとは？\nLangGraphとは？'}
              aria-describedby="bench-questions-help"
            />
            <p id="bench-questions-help" className="mt-1 text-xs text-muted-foreground">
              1行に1つずつ質問を入力してください。空行は無視されます。
            </p>
          </div>
          <div>
            <label htmlFor="bench-runs" className="block text-sm font-medium mb-2">
              実行回数（回）
            </label>
            <input
              id="bench-runs"
              type="number"
              value={runs}
              onChange={(e) => setRuns(Number(e.target.value))}
              className="w-32 px-3 py-2 border rounded-md bg-background"
              min={1}
              max={10}
            />
          </div>
          <button
            onClick={handleRun}
            disabled={!canRun}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? '実行中...' : '実行'}
          </button>
          {error && (
            <div className="p-3 text-sm text-destructive bg-destructive/10 border border-destructive/20 rounded-md">
              {error}
            </div>
          )}
          {results && (
            <div className="mt-6 p-4 border rounded-md bg-card space-y-2">
              <h2 className="font-semibold">結果</h2>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">P50:</span>{' '}
                  <span className="font-medium">{results.p50_ms?.toFixed(0)}ms</span>
                </div>
                <div>
                  <span className="text-muted-foreground">P95:</span>{' '}
                  <span className="font-medium">{results.p95_ms?.toFixed(0)}ms</span>
                </div>
                <div>
                  <span className="text-muted-foreground">平均:</span>{' '}
                  <span className="font-medium">{results.avg_ms?.toFixed(0)}ms</span>
                </div>
                <div>
                  <span className="text-muted-foreground">キャッシュヒット率:</span>{' '}
                  <span className="font-medium">{(results.cache_hit_rate * 100).toFixed(1)}%</span>
                </div>
                <div>
                  <span className="text-muted-foreground">推定トークン数:</span>{' '}
                  <span className="font-medium">{results.est_tokens}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">推定コスト (USD):</span>{' '}
                  <span className="font-medium">${results.est_cost_usd?.toFixed(4)}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

