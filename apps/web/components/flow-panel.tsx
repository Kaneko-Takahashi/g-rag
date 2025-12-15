'use client'

interface FlowPanelProps {
  metrics: any
}

export default function FlowPanel({ metrics }: FlowPanelProps) {
  if (!metrics) {
    return (
      <div className="p-4 border-t">
        <h2 className="font-semibold mb-4">Execution Flow</h2>
        <div className="text-sm text-muted-foreground">実行フローはここに表示されます</div>
      </div>
    )
  }

  const nodes = metrics.node_history || []

  return (
    <div className="p-4 border-t">
      <h2 className="font-semibold mb-4">Execution Flow</h2>
      <div className="space-y-2">
        {nodes.map((node: any, idx: number) => (
          <div key={idx} className="text-sm">
            <div className="flex justify-between">
              <span className="font-medium">{node.node}</span>
              <span className="text-muted-foreground">
                {node.elapsed_ms?.toFixed(0)}ms
              </span>
            </div>
            <div className="text-xs text-muted-foreground">
              {node.status === 'success' ? '✓' : '✗'} {node.status}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 pt-4 border-t text-sm">
        <div className="flex justify-between">
          <span>Total:</span>
          <span className="font-medium">{metrics.total_elapsed_ms?.toFixed(0)}ms</span>
        </div>
      </div>
    </div>
  )
}

