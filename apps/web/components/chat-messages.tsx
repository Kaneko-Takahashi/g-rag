'use client'

interface ChatMessagesProps {
  messages: Array<{ role: 'user' | 'assistant'; content: string }>
}

/** 回答本文から「質問「〇〇」について、」などの繰り返しを除去 */
function answerOnly(content: string, previousUserContent: string | null): string {
  if (!content.trim()) return content
  if (!previousUserContent?.trim()) return content
  const q = previousUserContent.trim()
  // 「質問「〇〇」について、」で始まる
  const prefix1 = `質問「${q}」について、`
  if (content.startsWith(prefix1)) return content.slice(prefix1.length).trimStart()
  // 「〇〇 質問 「〇〇」について、」
  const prefix2 = `${q} 質問 「${q}」について、`
  if (content.startsWith(prefix2)) return content.slice(prefix2.length).trimStart()
  // 質問文そのもので始まっている
  if (content.startsWith(q)) return content.slice(q.length).trimStart()
  return content
}

export default function ChatMessages({ messages }: ChatMessagesProps) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.length === 0 ? (
        <div className="text-center text-muted-foreground mt-8">
          質問を入力して開始してください
        </div>
      ) : (
        messages.map((msg, idx) => {
          const prevUser = msg.role === 'assistant'
            ? messages.slice(0, idx).reverse().find(m => m.role === 'user')?.content ?? null
            : null
          const displayContent = msg.role === 'assistant' && prevUser
            ? answerOnly(msg.content, prevUser)
            : msg.content
          return (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg p-3 ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted'
                }`}
              >
                {displayContent}
              </div>
            </div>
          )
        })
      )}
    </div>
  )
}

