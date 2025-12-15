# G-RAG

RAG（Retrieval-Augmented Generation）システムのデモツール。LangGraph + FastAPI + Next.js で構築。

## 概要

G-RAGは、LangGraphを使ったRAGシステムの実装例です。以下の機能を提供します：

- **Web UI**: チャット形式で質問→ストリーミング回答→引用表示
- **API**: `/ask`（質問回答）、`/bench`（ベンチマーク）
- **LangGraph**: 意図分類→検索→生成のエージェントフロー
- **評価**: chunk/top-k/rerank比較スクリプト

## 前提条件

- Node.js 18+ (yarn)
- Python 3.10+
- （オプション）OpenAI API Key（REALモード使用時）

## モード

### DEMOモード（デフォルト）
- 外部API不要で動作
- 簡易ベクトル化（hashベース）
- テンプレート回答

### REALモード
- OpenAI/Azure OpenAI embeddings使用
- 実際のLLM回答

## 起動方法

### 1. 依存関係インストール

```bash
# ルート
yarn install

# API
cd apps/api
pip install -r requirements.txt

# Web（ルートから）
yarn install:all
```

### 2. 環境変数設定

`env.example`を`.env`にコピー（必要に応じて編集）：

```bash
# Windows (PowerShell)
Copy-Item env.example .env

# Linux/Mac
cp env.example .env
```

### 3. API起動

```bash
cd apps/api
python -m uvicorn main:app --reload --port 8000
```

または、ルートから：

```bash
yarn dev:api
```

### 4. Web起動

```bash
cd apps/web
yarn dev
```

または、ルートから：

```bash
yarn dev:web
```

### 5. アクセス

- Web UI: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 使い方

### Web UI

1. **ログイン**: `/login`で任意のパスコードを入力（DEMOモード）
2. **Chat**: 質問を入力→ストリーミング回答を確認→引用カードを確認
3. **Bench**: 複数質問でベンチマーク実行（p50/p95等を表示）
4. **Settings**: top_k、rerank、モード切替

### API

#### POST /ask

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "question": "What is RAG?",
    "use_rerank": true,
    "top_k": 4
  }'
```

#### POST /bench

```bash
curl -X POST http://localhost:8000/bench \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "questions": ["What is AI?", "How does RAG work?"],
    "runs": 3
  }'
```

## 評価の回し方

```bash
# APIが起動している状態で
cd eval
python run_eval.py
```

結果:
- `eval/results.csv`: CSV形式の詳細結果
- `eval/results.md`: Markdown形式の集計結果

評価項目:
- 設定A: top_k=2, rerank=off
- 設定B: top_k=4, rerank=off
- 設定C: top_k=4, rerank=on
- 設定D: top_k=8, rerank=on

## 速度改善ポイント

1. **キャッシュ**: 埋め込み・検索結果をLRUキャッシュ（`CACHE_SIZE`で調整）
2. **top_k調整**: 必要最小限の文書数に（デフォルト4）
3. **チャンクサイズ**: `DEFAULT_CHUNK_SIZE`（デフォルト500文字）
4. **リランク**: 精度重視時のみ有効化（`use_rerank=true`）
5. **並列化**: 将来的に複数質問の並列処理対応

詳細は `docs/design.md` を参照。

## プロジェクト構成

```
/
  apps/
    web/          # Next.js (TypeScript)
      app/        # App Router
      components/ # UIコンポーネント
      lib/        # ユーティリティ
    api/          # FastAPI (Python)
      main.py     # APIエントリーポイント
      rag.py      # RAGシステム
      langgraph_agent.py  # LangGraph実装
      auth.py     # 認証
      database.py # DB初期化
  eval/           # 評価スクリプト
    questions.jsonl
    run_eval.py
  data/           # サンプル文書
    *.md
  docs/           # 設計メモ
    design.md
```

## アイコン

- `apps/web/app/icon.svg`: SVG形式のアイコン（32px、グラフ×検索モチーフ）
  - Next.js 13+ App Routerでは、`app/icon.svg`が自動的にfaviconとして認識されます
- モチーフ: 3-5ノードのグラフ + 検索アイコン（ルーペ）

## データベース

- デモ: SQLite（`data/grag.db`）
- 本番: Postgres等へ差し替え可能（`DATABASE_URL`を変更）

## 認証

- **DEMOモード**: パスコードのみ（外部依存なし）
- 将来拡張: Supabase/GitHub OAuth対応可能な構造

## セキュリティ

- Cookie: HttpOnly / Secure（本番想定）/ SameSite=Lax
- `.env`とキー類はコミットしない（`.env.example`のみ）
- DEMO認証であることをUIに表示

## 次にやるべきTODO（デプロイ）

- [ ] 本番環境用の環境変数設定（JWT_SECRET等）
- [ ] データベースをPostgres等に移行
- [ ] ベクトルDBをFAISS/Chroma等に移行
- [ ] 認証をSupabase/GitHub OAuthに移行
- [ ] Docker Composeでの本番デプロイ設定
- [ ] CI/CDパイプライン構築
- [ ] ログ・モニタリング設定
- [ ] レート制限実装
- [ ] エラーハンドリング強化
- [ ] テスト追加（単体・統合）

## ライセンス

MIT

