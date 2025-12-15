# 設計判断メモ

## アーキテクチャ

### モノレポ構成
- `apps/web`: Next.js (TypeScript)
- `apps/api`: FastAPI (Python)
- `eval/`: 評価スクリプト
- `data/`: サンプル文書

### 認証
- DEMOモード: パスコードのみ（外部依存なし）
- 将来拡張: Supabase/GitHub OAuth対応可能な構造

### データベース
- デモ: SQLite（`data/grag.db`）
- 本番: Postgres等へ差し替え可能

## RAG実装

### 埋め込みモード
- **DEMO**: hashベースの簡易ベクトル化（外部API不要）
- **REAL**: OpenAI/Azure OpenAI embeddings

### ベクトルDB
- 初期: メモリ内（numpy + sklearn）
- 将来: FAISS/Chroma等へ移行可能

### キャッシュ
- LRUキャッシュ（埋め込み・検索結果）
- ベンチマークでヒット率計測

## LangGraph

### ノード構成
1. `classify_intent`: 意図分類（キーワードベース）
2. `retrieve`: 文書検索
3. `generate`: 回答生成（LLM or テンプレート）
4. `finalize`: メトリクス集計

### リトライ
- 失敗時は最大1回リトライ
- ノード履歴に記録

## 速度改善ポイント

1. **キャッシュ**: 埋め込み・検索結果をキャッシュ
2. **top_k調整**: 必要最小限の文書数に調整
3. **チャンクサイズ**: 500文字（調整可能）
4. **並列化**: 将来的に複数質問の並列処理
5. **リランク**: 必要時のみ有効化

## UI/UX

### デザイン方針
- Tailwind CSS + shadcn/ui
- ダークモード対応
- レスポンシブ（モバイル対応）

### 可視化
- LangGraph実行フロー（タイムライン）
- 引用カード（Evidence）
- メトリクス表示（p50/p95等）

