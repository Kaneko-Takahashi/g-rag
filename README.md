# G-RAG

RAG（Retrieval-Augmented Generation）システムのデモツール。LangGraph + FastAPI + Next.js で構築。

## 概要

G-RAGは、LangGraphを使ったRAGシステムの実装例です。以下の機能を提供します：

- **Web UI**: チャット形式で**質問と回答を別々の吹き出し**で表示→ストリーミング回答→引用表示
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
- **テンプレート回答は日本語のみ**（英語は含みません）

### REALモード
- OpenAI/Azure OpenAI embeddings使用
- 実際のLLM回答（プロンプトで日本語出力を指定）

## 起動方法

### 1. 依存関係インストール

**ルートで yarn（全ワークスペース）:**

```bash
yarn install
```

**API の Python 依存:**

```bash
cd apps/api
pip install -r requirements.txt
```

> **Windows (PowerShell) の場合**: `&&` は使えません。上のようにコマンドを分けて実行するか、`;` でつなげてください。  
> 例: `cd apps/api; pip install -r requirements.txt`

**API で langchain 系の競合エラーが出る場合:**

`langchain` / `langchain-community` / `langgraph` が別途入っているとバージョン競合することがあります。以下で競合パッケージを外してから入れ直してください。

```bash
cd apps/api
pip uninstall langchain langchain-community langgraph -y
pip install -r requirements.txt
```

（このプロジェクトでは `langchain-core` と `langchain-openai` のみ使用しています。）

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
2. **Chat**: 質問を入力→**質問・回答が別々の吹き出しで表示**→ストリーミング回答を確認→引用カードを確認（DEMO時は回答は日本語のみ）
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
    icon.png      # アプリアイコン（PNG）
    web/          # Next.js (TypeScript)
      app/        # App Router（icon.png = ファビコン）
      public/     # 静的ファイル（icon.png）
      components/ # UIコンポーネント
      lib/        # ユーティリティ
      .dockerignore  # Dockerビルド時に node_modules を除外
    api/          # FastAPI (Python)
      main.py     # APIエントリーポイント
      rag.py      # RAGシステム
      langgraph_agent.py  # エージェントフロー（自前実装）
      auth.py     # 認証
      database.py # DB初期化
      tests/      # pytest
  eval/           # 評価スクリプト
    questions.jsonl
    run_eval.py
  data/           # サンプル文書
    *.md
  docs/           # 設計メモ
    design.md
```

## アイコン

- **`apps/icon.png`**: アプリアイコン（角丸四角・青→ティールのグラデーション・白いチャット吹き出しとループパス）のマスターファイル
- **`apps/web/public/icon.png`**: 公開用（サイドバーなどで `/icon.png` として参照）
- **`apps/web/app/icon.png`**: Next.js App Router がファビコンとして自動認識
- サイドバーのロゴは `components/sidebar.tsx` で `/icon.png` を参照

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

## 本番デプロイ

### 環境変数（本番）

- `JWT_SECRET`: **必須**。32文字以上のランダム文字列（`openssl rand -hex 32` 推奨）
- `DATABASE_URL`: Postgres 推奨（`postgresql://user:pass@host:5432/dbname`）
- `AUTH_MODE`: `demo` | `supabase` | `github`
- `VECTOR_DB`: `memory` | `chroma`（Chroma で永続化）
- `RATE_LIMIT_PER_MINUTE`: レート制限（0=無制限）
- `LOG_LEVEL`: `DEBUG` | `INFO` | `WARNING` | `ERROR`

詳細は `env.example` を参照。

### Docker Compose 本番

```bash
# .env に POSTGRES_PASSWORD, JWT_SECRET を設定
cp env.example .env
# 編集: POSTGRES_PASSWORD=..., JWT_SECRET=...（いずれも必須）

docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

- Web: http://localhost:3000
- API: http://localhost:8000

**初回やイメージの作り直し時は `--build` を付ける。**

### 本番Dockerの注意（トラブルシューティング）

- **WSL 2 で Docker を使っている場合**: メモリ不足で Web ビルドが落ちることがあります。`C:\Users\<あなたのユーザー名>\.wslconfig` に `[wsl2]` セクションで `memory=8GB` などを設定し、`wsl --shutdown` のあと Docker Desktop を再起動してください。
- **API の Python 依存**: `langchain-core` と `langchain-openai` を使用（競合回避のためトップレベルの `langchain` パッケージは未使用）。エージェントフローは `langgraph_agent.py` 内の自前実装です。
- **Web の Docker ビルド**: `apps/web/.dockerignore` で `node_modules` を除外し、コンテナ内でクリーンに `yarn install` しています。

**本番コンテナの停止**

```bash
docker compose -f docker-compose.prod.yml down
```

データを消す場合: `down -v`

### CI/CD

- GitHub Actions: `.github/workflows/ci.yml`（push/PR で API テスト・Web ビルド）

### 完了したデプロイ対応

- [x] 本番環境用の環境変数設定（JWT_SECRET等）
- [x] データベースをPostgres等に移行（DATABASE_URL + docker-compose.prod）
- [x] ベクトルDBをChromaに移行可能（VECTOR_DB=chroma）
- [x] 認証をSupabase/GitHub OAuthに移行可能（AUTH_MODE + access_token）
- [x] Docker Composeでの本番デプロイ設定（docker-compose.prod.yml）
- [x] CI/CDパイプライン構築（GitHub Actions）
- [x] ログ・モニタリング設定（構造化ログ、LOG_LEVEL）
- [x] レート制限実装（SlowAPI、RATE_LIMIT_PER_MINUTE）
- [x] エラーハンドリング強化（グローバル例外ハンドラ、429）
- [x] テスト追加（apps/api/tests、pytest）

## ライセンス

MIT

