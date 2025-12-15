'use client'

interface Citation {
  id: string
  title: string
  snippet: string
  score?: number
}

interface EvidencePanelProps {
  citations: Citation[]
}

export default function EvidencePanel({ citations }: EvidencePanelProps) {
  return (
    <div className="flex-1 p-4 overflow-y-auto">
      <h2 className="font-semibold mb-4">Evidence</h2>
      {citations.length === 0 ? (
        <div className="text-sm text-muted-foreground">引用はここに表示されます</div>
      ) : (
        <div className="space-y-3">
          {citations.map((cite) => (
            <div key={cite.id} className="p-3 border rounded-md bg-card">
              <div className="font-medium text-sm mb-1">{cite.title}</div>
              <div className="text-xs text-muted-foreground line-clamp-3">
                {cite.snippet}
              </div>
              {cite.score !== undefined && (
                <div className="text-xs text-muted-foreground mt-1">
                  Score: {cite.score.toFixed(3)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

