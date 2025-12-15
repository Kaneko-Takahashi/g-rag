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
      
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      
      // SSEフレームをパースする関数
      function parseSSEFrame(frame: string): { event?: string; data: string } | null {
        const normalized = frame.replace(/\r\n/g, '\n')
        const lines = normalized.split('\n')
        
        let event: string | undefined
        const dataLines: string[] = []
        
        for (const line of lines) {
          const trimmedLine = line.trim()
          if (!trimmedLine) continue
          
          // event: の処理
          if (trimmedLine.startsWith('event:')) {
            event = trimmedLine.slice('event:'.length).trim()
          } 
          // data: の処理（スペースがあってもなくてもOK）
          else if (trimmedLine.startsWith('data:')) {
            // data: の後の部分を取得
            let dataContent = trimmedLine.slice('data:'.length)
            // 先頭のスペースを除去
            dataContent = dataContent.trimStart()
            // もしdataContentの中にまだ"data:"が含まれていたら除去（念のため）
            dataContent = dataContent.replace(/^data:\s*/g, '')
            if (dataContent) {
              dataLines.push(dataContent)
            }
          }
        }
        
        if (!event && dataLines.length === 0) return null
        const joinedData = dataLines.join('\n')
        return { event, data: joinedData }
      }
      
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
      
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        
        let idx: number
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          
          // デバッグ: フレームの内容を確認
          if (frame.includes('data:')) {
            console.log('Raw frame:', JSON.stringify(frame))
          }
          
          const parsed = parseSSEFrame(frame)
          if (!parsed) continue
          
          // デバッグ: パース結果を確認
          if (parsed.data && parsed.data.includes('data:')) {
            console.log('Parsed data contains "data:":', JSON.stringify(parsed.data))
          }
          
          const kind = parsed.event ?? 'token'
          
          if (kind === 'citations') {
            try {
              setCitations(JSON.parse(parsed.data))
            } catch (e) {
              console.error('Failed to parse citations:', e)
            }
            continue
          }
          if (kind === 'metrics') {
            try {
              setMetrics(JSON.parse(parsed.data))
            } catch (e) {
              console.error('Failed to parse metrics:', e)
            }
            continue
          }
          if (kind === 'done') {
            break
          }
          
          // token/message/未指定 → 本文に「dataだけ」追記
          // parsed.dataには既にdata:プレフィックスは含まれていないはず
          if (parsed.data && parsed.data !== '[DONE]') {
            // 念のため、もしdata:が含まれていたら除去（複数行対応）
            let cleanData = parsed.data
            // 行単位でdata:プレフィックスを除去
            cleanData = cleanData.split('\n').map(line => {
              const trimmed = line.trim()
              if (trimmed.startsWith('data:')) {
                return trimmed.slice('data:'.length).trimStart()
              }
              return line
            }).join('\n')
            
            if (cleanData && cleanData !== '[DONE]') {
              appendAssistantText(cleanData)
            }
          }
        }
      }
      
      // 残りのバッファを処理（最後の不完全なフレーム）
      if (buffer.trim()) {
        const parsed = parseSSEFrame(buffer)
        if (parsed) {
          const kind = parsed.event ?? 'token'
          
          if (kind === 'citations') {
            try {
              setCitations(JSON.parse(parsed.data))
            } catch (e) {
              console.error('Failed to parse citations:', e)
            }
          } else if (kind === 'metrics') {
            try {
              setMetrics(JSON.parse(parsed.data))
            } catch (e) {
              console.error('Failed to parse metrics:', e)
            }
          } else if (kind !== 'done' && parsed.data && parsed.data !== '[DONE]') {
            // 念のため、もしdata:が含まれていたら除去
            const cleanData = parsed.data.replace(/^data:\s*/g, '')
            if (cleanData) {
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

