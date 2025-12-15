'use client'

import { useState, useRef, useEffect } from 'react'
import Sidebar from './sidebar'
import ChatInput from './chat-input'
import ChatMessages from './chat-messages'
import EvidencePanel from './evidence-panel'
import FlowPanel from './flow-panel'
import { apiRequest, getAuthToken } from '@/lib/auth'

export default function ChatPage() {
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([])
  const [citations, setCitations] = useState<any[]>([])
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const handleSend = async (question: string, useRerank: boolean, topK: number) => {
    setLoading(true)
    setMessages([...messages, { role: 'user', content: question }])
    setCitations([])
    setMetrics(null)
    
    // ストリーミング回答用のメッセージを追加
    const assistantMessageId = messages.length
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])
    
    abortControllerRef.current = new AbortController()
    
    try {
      const token = getAuthToken()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          question,
          use_rerank: useRerank,
          top_k: topK,
        }),
        signal: abortControllerRef.current.signal,
      })
      
      if (!res.ok) throw new Error('Request failed')
      
      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data && data !== '[DONE]') {
              setMessages(prev => {
                const newMessages = [...prev]
                if (newMessages[assistantMessageId]) {
                  newMessages[assistantMessageId].content += data
                }
                return newMessages
              })
            }
          } else if (line.startsWith('event: citations')) {
            // 次の行を待つ
            continue
          } else if (line.startsWith('event: metrics')) {
            // 次の行を待つ
            continue
          }
        }
      }
      
      // 最終データ取得
      const finalLines = buffer.split('\n')
      for (let i = 0; i < finalLines.length; i++) {
        const line = finalLines[i]
        if (line.startsWith('data: ') && finalLines[i - 1]?.startsWith('event: citations')) {
          try {
            const data = JSON.parse(line.slice(6))
            setCitations(data)
          } catch {}
        } else if (line.startsWith('data: ') && finalLines[i - 1]?.startsWith('event: metrics')) {
          try {
            const data = JSON.parse(line.slice(6))
            setMetrics(data)
          } catch {}
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        console.error(err)
        setMessages(prev => {
          const newMessages = [...prev]
          if (newMessages[assistantMessageId]) {
            newMessages[assistantMessageId].content = 'エラーが発生しました: ' + err.message
          }
          return newMessages
        })
      }
    } finally {
      setLoading(false)
      abortControllerRef.current = null
    }
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <div className="flex-1 flex overflow-hidden">
          {/* 左: 履歴（簡易版） */}
          <div className="w-64 border-r bg-muted/50 p-4">
            <h2 className="font-semibold mb-4">履歴</h2>
            <div className="text-sm text-muted-foreground">会話履歴はここに表示されます</div>
          </div>
          
          {/* 中央: チャット */}
          <div className="flex-1 flex flex-col">
            <ChatMessages messages={messages} />
            <ChatInput
              onSend={handleSend}
              loading={loading}
            />
          </div>
          
          {/* 右: Evidence/Flow */}
          <div className="w-80 border-l bg-muted/50 flex flex-col">
            <EvidencePanel citations={citations} />
            <FlowPanel metrics={metrics} />
          </div>
        </div>
      </div>
    </div>
  )
}

