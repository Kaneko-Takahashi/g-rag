'use client'

import { useState, useRef } from 'react'
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
      if (!reader) throw new Error('Failed to get reader')
      
      // アシスタントメッセージにテキストを追記する関数
      const appendAssistantText = (text: string) => {
        setMessages(prev => {
          const newMessages = [...prev]
          if (newMessages[assistantMessageId]) {
            newMessages[assistantMessageId].content += text
          }
          return newMessages
        })
      }

      // SSEのdataが引用JSONっぽいか判定（保険）
      const looksLikeCitationsJson = (s: string): boolean => {
        try {
          const v = JSON.parse(s)
          return Array.isArray(v) && v.length > 0 && typeof v[0]?.snippet === 'string'
        } catch {
          return false
        }
      }

      const looksLikeMetricsJson = (s: string): boolean => {
        try {
          const v = JSON.parse(s)
          return v && typeof v === 'object' && ('latency_ms' in v || 'p95_ms' in v || 'tokens' in v)
        } catch {
          return false
        }
      }

      // ストリーム読み取りループ
      let buffer = ''
      const decoder = new TextDecoder('utf-8')

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        buffer = buffer.replace(/\r\n/g, '\n') // Windows改行を正規化

        // フレーム（空行区切り）で処理
        while (true) {
          const idx = buffer.indexOf('\n\n')
          if (idx === -1) break

          const frame = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)

          let eventName = ''
          const dataLines: string[] = []

          for (const rawLine of frame.split('\n')) {
            const line = rawLine.trim() // 念のためtrim
            if (!line) continue

            if (line.startsWith('event:')) {
              eventName = line.slice('event:'.length).trim()
              continue // 本文に入れない
            }

            if (line.startsWith('data:')) {
              dataLines.push(line.slice('data:'.length).trimStart())
              continue
            }

            // その他の行は無視（本文に入れない）
          }

          const data = dataLines.join('\n')

          // 終了
          if (eventName === 'done' || data === '[DONE]') {
            break
          }

          // citations / metrics（eventが付いてるケース）
          if (eventName === 'citations') {
            try {
              setCitations(JSON.parse(data))
            } catch (e) {
              console.error('Failed to parse citations:', e)
            }
            continue
          }
          if (eventName === 'metrics') {
            try {
              setMetrics(JSON.parse(data))
            } catch (e) {
              console.error('Failed to parse metrics:', e)
            }
            continue
          }

          // 保険：event無しでJSONが飛んできたケース
          if (looksLikeCitationsJson(data)) {
            try {
              setCitations(JSON.parse(data))
            } catch (e) {
              console.error('Failed to parse citations (fallback):', e)
            }
            continue
          }
          if (looksLikeMetricsJson(data)) {
            try {
              setMetrics(JSON.parse(data))
            } catch (e) {
              console.error('Failed to parse metrics (fallback):', e)
            }
            continue
          }

          // ここだけ本文に追記
          if (data) {
            appendAssistantText(data)
          }
        }
      }

      // 残りのバッファを処理（最後の不完全なフレーム）
      if (buffer.trim()) {
        let eventName = ''
        const dataLines: string[] = []

        for (const rawLine of buffer.split('\n')) {
          const line = rawLine.trim()
          if (!line) continue

          if (line.startsWith('event:')) {
            eventName = line.slice('event:'.length).trim()
            continue
          }

          if (line.startsWith('data:')) {
            dataLines.push(line.slice('data:'.length).trimStart())
            continue
          }
        }

        const data = dataLines.join('\n')

        if (data && data !== '[DONE]') {
          if (eventName === 'citations') {
            try {
              setCitations(JSON.parse(data))
            } catch (e) {
              console.error('Failed to parse citations:', e)
            }
          } else if (eventName === 'metrics') {
            try {
              setMetrics(JSON.parse(data))
            } catch (e) {
              console.error('Failed to parse metrics:', e)
            }
          } else if (eventName !== 'done') {
            // 保険：event無しでJSONが飛んできたケース
            if (looksLikeCitationsJson(data)) {
              try {
                setCitations(JSON.parse(data))
              } catch (e) {
                console.error('Failed to parse citations (fallback):', e)
              }
            } else if (looksLikeMetricsJson(data)) {
              try {
                setMetrics(JSON.parse(data))
              } catch (e) {
                console.error('Failed to parse metrics (fallback):', e)
              }
            } else {
              appendAssistantText(data)
            }
          }
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

