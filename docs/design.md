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
- **memory**（デフォルト）: メモリ内（numpy + sklearn）
- **chroma**: ChromaDB で永続化（`VECTOR_DB=chroma`、`CHROMA_PERSIST_DIR` で指定）

### キャッシュ
- LRUキャッシュ（埋め込み・検索結果）
- ベンチマークでヒット率計測

## エージェントフロー（LangGraph風）

API のエージェントは `langgraph_agent.py` で自前実装。Python パッケージの `langgraph` は未使用。LLM 連携は `langchain-core` と `langchain-openai` のみ使用（依存関係競合を避けるため）。

### Python 依存の注意（API）

- `requirements.txt` には `langchain` / `langgraph` は含めず、`langchain-core` と `langchain-openai` のみ指定。
- 既存環境に `langchain` や `langgraph` が入っているとバージョン競合することがある。その場合は `pip uninstall langchain langchain-community langgraph -y` のあと `pip install -r requirements.txt` で解消する。詳細は README の「起動方法」を参照。

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

### アイコン
- アプリアイコンは PNG（`apps/icon.png`）。同一ファイルを `apps/web/public/icon.png` と `apps/web/app/icon.png` に配置し、サイドバーは `/icon.png`、ファビコンは App Router の `app/icon.png` を参照。

### 可視化
- LangGraph実行フロー（タイムライン）
- 引用カード（Evidence）
- メトリクス表示（p50/p95等）

