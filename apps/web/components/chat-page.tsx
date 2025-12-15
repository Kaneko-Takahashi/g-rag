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

      // SSEパーサー（行ベース、空行でイベント確定）
      type SSEOut = { event: string; data: string }

      const sseParseLines = (state: { buf: string; ev: string; data: string[] }, chunk: string): SSEOut[] => {
        state.buf += chunk.replace(/\r\n/g, '\n') // 改行正規化
        const out: SSEOut[] = []

        while (true) {
          const nl = state.buf.indexOf('\n')
          if (nl === -1) break

          const line = state.buf.slice(0, nl)
          state.buf = state.buf.slice(nl + 1)

          // 空行＝イベント確定
          if (line === '') {
            if (state.data.length > 0) {
              out.push({ event: state.ev || 'message', data: state.data.join('\n') })
            }
            state.ev = ''
            state.data = []
            continue
          }

          if (line.startsWith('event:')) {
            state.ev = line.slice(6).trim()
            continue
          }

          if (line.startsWith('data:')) {
            // data: の後の部分を取得（スペースがあってもなくてもOK）
            const dataContent = line.slice(5).trimStart() // ★ data: を剥がす
            if (dataContent) {
              state.data.push(dataContent)
            }
            continue
          }

          // その他は無視
        }

        return out
      }

      // ストリーム読み取りループ
      const decoder = new TextDecoder('utf-8')
      const state = { buf: '', ev: '', data: [] as string[] }

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        const chunkText = decoder.decode(value, { stream: true })
        
        // デバッグ: 生のチャンクを確認
        if (chunkText.includes('data:') || chunkText.includes('event:')) {
          console.log('Raw chunk:', JSON.stringify(chunkText.substring(0, 200)))
        }
        
        const events = sseParseLines(state, chunkText)

        for (const e of events) {
          const ev = e.event
          const data = e.data

          // デバッグ: パース結果を確認
          console.log('Parsed event:', ev, 'data:', JSON.stringify(data.substring(0, 50)))

          if (data === '[DONE]' || ev === 'done') {
            // 終了処理
            break
          }

          if (ev === 'citations') {
            try {
              setCitations(JSON.parse(data))
            } catch (e) {
              console.error('Failed to parse citations:', e)
            }
            continue
          }

          if (ev === 'metrics') {
            try {
              setMetrics(JSON.parse(data))
            } catch (e) {
              console.error('Failed to parse metrics:', e)
            }
            continue
          }

          // ★本文には data だけを追記（event/data: は一切入れない）
          if (data) {
            // 念のため、dataの中に"data:"や"event:"が含まれていたら除去
            let cleanData = data
            // data: や event: を除去（複数回出現する可能性がある）
            cleanData = cleanData.replace(/data:\s*/g, '')
            cleanData = cleanData.replace(/event:\s*/g, '')
            
            if (cleanData && cleanData !== '[DONE]') {
              appendAssistantText(cleanData)
            }
          }
        }
      }

      // 残りのバッファを処理（最後の不完全なイベント）
      if (state.data.length > 0) {
        const ev = state.ev || 'message'
        const data = state.data.join('\n')

        if (data && data !== '[DONE]' && ev !== 'done') {
          if (ev === 'citations') {
            try {
              setCitations(JSON.parse(data))
            } catch (e) {
              console.error('Failed to parse citations:', e)
            }
          } else if (ev === 'metrics') {
            try {
              setMetrics(JSON.parse(data))
            } catch (e) {
              console.error('Failed to parse metrics:', e)
            }
          } else {
            // ★本文には data だけを追記
            // 念のため、dataの中に"data:"や"event:"が含まれていたら除去
            let cleanData = data
            cleanData = cleanData.replace(/data:\s*/g, '')
            cleanData = cleanData.replace(/event:\s*/g, '')
            
            if (cleanData && cleanData !== '[DONE]') {
              appendAssistantText(cleanData)
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

