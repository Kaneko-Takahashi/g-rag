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
      
      const decoder = new TextDecoder()
      let buffer = ''
      let streamDone = false
      
      while (!streamDone) {
        const { done, value } = await reader.read()
        if (done) {
          streamDone = true
          break
        }
        
        buffer += decoder.decode(value, { stream: true })
        
        // SSEフレームを \n\n で分割
        const frames = buffer.split('\n\n')
        // 最後の不完全なフレームはバッファに残す
        buffer = frames.pop() || ''
        
        // 各フレームを処理
        for (const frame of frames) {
          if (!frame.trim()) continue
          
          let event: string | null = null
          const dataLines: string[] = []
          
          // フレーム内の各行を解析
          const lines = frame.split('\n')
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              event = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              // data: の後の部分を取得（複数行のdataに対応）
              dataLines.push(line.slice(6))
            }
          }
          
          // data を連結（複数行data対応）
          const data = dataLines.join('\n')
          
          if (!data || data === '[DONE]') {
            if (event === 'done') {
              streamDone = true
              break
            }
            continue
          }
          
          // event に応じて処理
          if (event === 'citations') {
            try {
              const citationsData = JSON.parse(data)
              setCitations(citationsData)
            } catch (e) {
              console.error('Failed to parse citations:', e)
            }
          } else if (event === 'metrics') {
            try {
              const metricsData = JSON.parse(data)
              setMetrics(metricsData)
            } catch (e) {
              console.error('Failed to parse metrics:', e)
            }
          } else if (event === 'done') {
            streamDone = true
            break
          } else {
            // event が "message" または "token" または event未指定の data は、チャット本文に追記
            // "data:"文字は表示しない（既にdata変数には含まれていない）
            setMessages(prev => {
              const newMessages = [...prev]
              if (newMessages[assistantMessageId]) {
                newMessages[assistantMessageId].content += data
              }
              return newMessages
            })
          }
        }
      }
      
      // 残りのバッファを処理（最後の不完全なフレーム）
      if (buffer.trim()) {
        let event: string | null = null
        const dataLines: string[] = []
        
        const lines = buffer.split('\n')
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            event = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            dataLines.push(line.slice(6))
          }
        }
        
        const data = dataLines.join('\n')
        
        if (data && data !== '[DONE]') {
          if (event === 'citations') {
            try {
              const citationsData = JSON.parse(data)
              setCitations(citationsData)
            } catch (e) {
              console.error('Failed to parse citations:', e)
            }
          } else if (event === 'metrics') {
            try {
              const metricsData = JSON.parse(data)
              setMetrics(metricsData)
            } catch (e) {
              console.error('Failed to parse metrics:', e)
            }
          } else if (!event || event === 'message' || event === 'token') {
            setMessages(prev => {
              const newMessages = [...prev]
              if (newMessages[assistantMessageId]) {
                newMessages[assistantMessageId].content += data
              }
              return newMessages
            })
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

