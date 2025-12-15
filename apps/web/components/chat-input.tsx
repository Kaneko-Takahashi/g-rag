'use client'

import { useState } from 'react'
import { Send } from 'lucide-react'

interface ChatInputProps {
  onSend: (question: string, useRerank: boolean, topK: number) => Promise<void>
  loading: boolean
}

export default function ChatInput({ onSend, loading }: ChatInputProps) {
  const [question, setQuestion] = useState('')
  const [useRerank, setUseRerank] = useState(true)
  const [topK, setTopK] = useState(4)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || loading) return
    await onSend(question, useRerank, topK)
    setQuestion('')
  }

  return (
    <div className="border-t p-4 bg-background">
      <div className="flex gap-2 mb-2">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={useRerank}
            onChange={(e) => setUseRerank(e.target.checked)}
          />
          Rerank
        </label>
        <label className="flex items-center gap-2 text-sm">
          Top-K:
          <input
            type="number"
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            className="w-16 px-2 py-1 border rounded"
            min="1"
            max="10"
          />
        </label>
      </div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="質問を入力..."
          className="flex-1 px-4 py-2 border rounded-md bg-background"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
        >
          <Send className="w-5 h-5" />
        </button>
      </form>
    </div>
  )
}

