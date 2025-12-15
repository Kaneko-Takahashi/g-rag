"""
RAGシステム（DEMO/REALモード対応）
"""
import os
import hashlib
import json
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from cachetools import LRUCache

EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "demo")
DATA_DIR = Path(__file__).parent.parent.parent / "data"

class RAGSystem:
    def __init__(self):
        self.mode = EMBEDDING_MODE
        self.documents: List[Dict] = []
        self.embeddings: Optional[np.ndarray] = None
        self.cache = LRUCache(maxsize=int(os.getenv("CACHE_SIZE", 1000)))
        self.chunk_size = int(os.getenv("DEFAULT_CHUNK_SIZE", 500))
        self.chunk_overlap = int(os.getenv("DEFAULT_CHUNK_OVERLAP", 50))
    
    async def initialize(self):
        """初期化: 文書読み込みとベクトル化"""
        # data/*.md を読み込み
        md_files = list(DATA_DIR.glob("*.md"))
        if not md_files:
            # サンプル文書を生成
            await self._create_sample_docs()
            md_files = list(DATA_DIR.glob("*.md"))
        
        chunks = []
        for md_file in md_files:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
                doc_chunks = self._chunk_text(content, md_file.stem)
                chunks.extend(doc_chunks)
        
        self.documents = chunks
        
        # 埋め込み生成
        texts = [chunk["text"] for chunk in chunks]
        if self.mode == "demo":
            self.embeddings = self._demo_embed(texts)
        else:
            self.embeddings = await self._real_embed(texts)
    
    def _chunk_text(self, text: str, doc_id: str) -> List[Dict]:
        """テキストをチャンクに分割"""
        chunks = []
        words = text.split()
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_text = " ".join(words[i:i + self.chunk_size])
            chunks.append({
                "id": f"{doc_id}_chunk_{i}",
                "doc_id": doc_id,
                "text": chunk_text,
                "title": doc_id.replace("_", " ").title()
            })
        return chunks
    
    def _demo_embed(self, texts: List[str]) -> np.ndarray:
        """DEMO: 簡易ベクトル化（hashベース）"""
        # 各テキストを固定次元ベクトルに変換（簡易版）
        dim = 128
        embeddings = []
        for text in texts:
            vec = np.zeros(dim)
            # 単語のhashを利用
            words = text.lower().split()
            for word in words[:50]:  # 最初の50単語
                h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                idx = h % dim
                vec[idx] += 1.0
            # 正規化
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            embeddings.append(vec)
        return np.array(embeddings)
    
    async def _real_embed(self, texts: List[str]) -> np.ndarray:
        """REAL: OpenAI/Azure OpenAI埋め込み"""
        try:
            from langchain_openai import OpenAIEmbeddings
            embeddings_model = OpenAIEmbeddings()
            vectors = await embeddings_model.aembed_documents(texts)
            return np.array(vectors)
        except Exception as e:
            print(f"Real embedding failed: {e}, falling back to demo")
            return self._demo_embed(texts)
    
    async def _create_sample_docs(self):
        """サンプル文書作成"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        samples = [
            ("ai_overview.md", """
# AI Overview

Artificial Intelligence (AI) is a branch of computer science that aims to create systems capable of performing tasks that typically require human intelligence. These tasks include learning, reasoning, problem-solving, perception, and language understanding.

## Key Concepts

Machine Learning is a subset of AI that enables systems to learn from data without being explicitly programmed. Deep Learning, in turn, is a subset of machine learning that uses neural networks with multiple layers.

## Applications

AI is used in various fields including healthcare, finance, transportation, and entertainment. Recent advances in large language models have enabled new applications in natural language processing and generation.
"""),
            ("rag_explained.md", """
# Retrieval-Augmented Generation (RAG)

RAG is a technique that combines information retrieval with language generation. It allows AI systems to access external knowledge bases to provide more accurate and up-to-date answers.

## How RAG Works

1. Query Processing: The user's question is converted into a search query.
2. Retrieval: Relevant documents are retrieved from a knowledge base using vector similarity.
3. Augmentation: Retrieved context is combined with the original query.
4. Generation: A language model generates an answer based on the augmented context.

## Benefits

RAG improves answer accuracy, reduces hallucinations, and enables access to domain-specific knowledge without retraining the model.
"""),
            ("langgraph_intro.md", """
# LangGraph Introduction

LangGraph is a framework for building stateful, multi-actor applications with LLMs. It provides a way to define complex workflows as graphs of nodes and edges.

## Core Concepts

- State: Shared data structure that flows through the graph
- Nodes: Functions that process the state
- Edges: Connections that determine the flow between nodes
- Tools: External functions that nodes can call

## Use Cases

LangGraph is ideal for building agents, chatbots, and complex reasoning systems that require multiple steps and decision points.
""")
        ]
        
        for filename, content in samples:
            (DATA_DIR / filename).write_text(content.strip(), encoding="utf-8")
    
    async def retrieve(
        self,
        query: str,
        top_k: int = 4,
        use_rerank: bool = False
    ) -> List[Dict]:
        """検索実行"""
        cache_key = f"retrieve:{hashlib.md5(query.encode()).hexdigest()}:{top_k}:{use_rerank}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # クエリ埋め込み
        if self.mode == "demo":
            query_vec = self._demo_embed([query])[0]
        else:
            query_vec = (await self._real_embed([query]))[0]
        
        # 類似度計算
        similarities = cosine_similarity([query_vec], self.embeddings)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k * 2]  # リランク用に多めに取得
        
        results = []
        for idx in top_indices:
            doc = self.documents[idx].copy()
            doc["score"] = float(similarities[idx])
            results.append(doc)
        
        # リランク（簡易版: スコア再計算）
        if use_rerank and len(results) > top_k:
            # 簡易リランク: クエリとの単語マッチ数を追加スコアに
            query_words = set(query.lower().split())
            for doc in results:
                doc_words = set(doc["text"].lower().split())
                match_ratio = len(query_words & doc_words) / max(len(query_words), 1)
                doc["score"] = doc["score"] * 0.7 + match_ratio * 0.3
            
            results.sort(key=lambda x: x["score"], reverse=True)
        
        final_results = results[:top_k]
        self.cache[cache_key] = final_results
        return final_results

