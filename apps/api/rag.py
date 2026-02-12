"""
RAGシステム（DEMO/REALモード対応、メモリ/Chroma ベクトルDB対応）
"""
import os
import hashlib
from typing import List, Dict, Optional
from pathlib import Path
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from cachetools import LRUCache

EMBEDDING_MODE = os.getenv("EMBEDDING_MODE", "demo")
VECTOR_DB = os.getenv("VECTOR_DB", "memory")
DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent.parent / "data")))


class RAGSystem:
    def __init__(self):
        self.mode = EMBEDDING_MODE
        self.vector_db = VECTOR_DB
        self.documents: List[Dict] = []
        self.embeddings: Optional[np.ndarray] = None
        self._chroma_client = None
        self._chroma_collection = None
        self.cache = LRUCache(maxsize=int(os.getenv("CACHE_SIZE", 1000)))
        self.chunk_size = int(os.getenv("DEFAULT_CHUNK_SIZE", 500))
        self.chunk_overlap = int(os.getenv("DEFAULT_CHUNK_OVERLAP", 50))

    async def initialize(self):
        """初期化: 文書読み込みとベクトル化"""
        md_files = list(DATA_DIR.glob("*.md"))
        if not md_files:
            await self._create_sample_docs()
            md_files = list(DATA_DIR.glob("*.md"))

        chunks = []
        for md_file in md_files:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()
                doc_chunks = self._chunk_text(content, md_file.stem)
                chunks.extend(doc_chunks)

        self.documents = chunks

        texts = [chunk["text"] for chunk in chunks]
        if self.mode == "demo":
            emb = self._demo_embed(texts)
        else:
            emb = await self._real_embed(texts)

        if self.vector_db == "chroma":
            await self._init_chroma(chunks, emb)
        else:
            self.embeddings = emb

    async def _init_chroma(self, chunks: List[Dict], embeddings: np.ndarray):
        """ChromaDB にコレクション作成・投入"""
        try:
            import chromadb
            from chromadb.config import Settings

            persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
            os.makedirs(persist_dir, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=persist_dir, settings=Settings(anonymized_telemetry=False))
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name="grag_docs",
                metadata={"description": "G-RAG document chunks"},
            )
            if self._chroma_collection.count() == 0:
                ids = [c["id"] for c in chunks]
                metadatas = [{"doc_id": c["doc_id"], "title": c["title"]} for c in chunks]
                docs = [c["text"] for c in chunks]
                self._chroma_collection.add(
                    ids=ids,
                    embeddings=embeddings.tolist(),
                    documents=docs,
                    metadatas=metadatas,
                )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Chroma init failed, falling back to memory: %s", e)
            self.vector_db = "memory"
            self.embeddings = embeddings

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
        dim = 128
        embeddings = []
        for text in texts:
            vec = np.zeros(dim)
            words = text.lower().split()
            for word in words[:50]:
                h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                idx = h % dim
                vec[idx] += 1.0
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
            import logging
            logging.getLogger(__name__).warning("Real embedding failed, falling back to demo: %s", e)
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

        if self.mode == "demo":
            query_vec = self._demo_embed([query])[0]
        else:
            query_vec = (await self._real_embed([query]))[0]

        if self.vector_db == "chroma" and self._chroma_collection is not None:
            results = await self._retrieve_chroma(query_vec, top_k, use_rerank, query)
        else:
            results = await self._retrieve_memory(query_vec, top_k, use_rerank, query)

        self.cache[cache_key] = results
        return results

    async def _retrieve_memory(
        self, query_vec: np.ndarray, top_k: int, use_rerank: bool, query: str
    ) -> List[Dict]:
        """メモリ内ベクトルで検索"""
        similarities = cosine_similarity([query_vec], self.embeddings)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k * 2]
        results = []
        for idx in top_indices:
            doc = self.documents[idx].copy()
            doc["score"] = float(similarities[idx])
            results.append(doc)
        if use_rerank and len(results) > top_k:
            query_words = set(query.lower().split())
            for doc in results:
                doc_words = set(doc["text"].lower().split())
                match_ratio = len(query_words & doc_words) / max(len(query_words), 1)
                doc["score"] = doc["score"] * 0.7 + match_ratio * 0.3
            results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def _retrieve_chroma(
        self, query_vec: np.ndarray, top_k: int, use_rerank: bool, query: str
    ) -> List[Dict]:
        """ChromaDB で検索"""
        n_results = top_k * 2 if use_rerank else top_k
        res = self._chroma_collection.query(
            query_embeddings=[query_vec.tolist()],
            n_results=min(n_results, self._chroma_collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        results = []
        if res["ids"] and res["ids"][0]:
            for i, id_ in enumerate(res["ids"][0]):
                dist = res["distances"][0][i] if res["distances"] else 0
                score = 1.0 / (1.0 + dist) if dist is not None else 0.0
                meta = res["metadatas"][0][i] if res["metadatas"] else {}
                results.append({
                    "id": id_,
                    "doc_id": meta.get("doc_id", ""),
                    "text": res["documents"][0][i],
                    "title": meta.get("title", ""),
                    "score": score,
                })
        if use_rerank and len(results) > top_k:
            query_words = set(query.lower().split())
            for doc in results:
                doc_words = set(doc["text"].lower().split())
                match_ratio = len(query_words & doc_words) / max(len(query_words), 1)
                doc["score"] = doc["score"] * 0.7 + match_ratio * 0.3
            results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
