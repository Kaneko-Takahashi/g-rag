"""
LangGraph Agent実装
"""
import time
import json
import asyncio
import re
from typing import Dict, Any, List, Optional, AsyncIterator
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from rag import RAGSystem


def _answer_only(answer: str, question: str) -> str:
    """回答から質問の繰り返し（質問「...」について、 等）を除去し、回答本文のみ返す"""
    if not question or not answer:
        return answer
    q = question.strip()
    # パターン1: 「質問「〇〇」について、」で始まる
    pattern1 = re.escape(f"質問「{q}」について、")
    if re.match(pattern1, answer):
        return re.sub(r"^" + pattern1 + r"\s*", "", answer, count=1)
    # パターン2: 「〇〇 質問 「〇〇」について、」
    pattern2 = re.escape(f"{q} 質問 「{q}」について、")
    if answer.strip().startswith(q + " 質問 "):
        try:
            prefix = re.match(re.escape(q) + r"\s+質問\s+「" + re.escape(q) + r"」について、\s*", answer)
            if prefix:
                return answer[prefix.end():]
        except Exception:
            pass
    # パターン3: 回答が質問文そのもので始まっている（先頭一致）
    if answer.startswith(q):
        rest = answer[len(q):].lstrip()
        if rest.startswith("質問") or rest.startswith("「") or len(rest) > 0:
            return rest
    return answer


class LangGraphState:
    """LangGraphの状態定義"""
    def __init__(self):
        self.question: str = ""
        self.intent: Optional[str] = None
        self.retrieved_docs: List[Dict] = []
        self.answer: str = ""
        self.citations: List[Dict] = []
        self.metrics: Dict[str, Any] = {}
        self.node_history: List[Dict] = []
        self.retry_count: int = 0

class LangGraphAgent:
    def __init__(self, rag_system: RAGSystem):
        self.rag = rag_system
        self.llm = None
        self._init_llm()
    
    def _init_llm(self):
        """LLM初期化（DEMO/REAL）"""
        import os
        mode = os.getenv("EMBEDDING_MODE", "demo")
        if mode == "real":
            try:
                self.llm = ChatOpenAI(temperature=0.7, model="gpt-3.5-turbo", streaming=True)
            except:
                self.llm = None
        # DEMOモードではLLMなし（テンプレート回答）
    
    async def classify_intent(self, state: LangGraphState) -> LangGraphState:
        """意図分類"""
        start = time.time()
        try:
            # 簡易分類: キーワードベース
            q_lower = state.question.lower()
            if any(w in q_lower for w in ["what", "what is", "explain"]):
                state.intent = "definition"
            elif any(w in q_lower for w in ["how", "how to", "how does"]):
                state.intent = "howto"
            elif any(w in q_lower for w in ["why", "why is", "reason"]):
                state.intent = "reasoning"
            else:
                state.intent = "general"
            
            elapsed = (time.time() - start) * 1000
            state.node_history.append({
                "node": "classify_intent",
                "status": "success",
                "elapsed_ms": elapsed,
                "intent": state.intent
            })
        except Exception as e:
            state.node_history.append({
                "node": "classify_intent",
                "status": "error",
                "error": str(e)
            })
        return state
    
    async def retrieve(self, state: LangGraphState, top_k: int = 4, use_rerank: bool = False) -> LangGraphState:
        """検索実行"""
        start = time.time()
        try:
            docs = await self.rag.retrieve(state.question, top_k=top_k, use_rerank=use_rerank)
            state.retrieved_docs = docs
            elapsed = (time.time() - start) * 1000
            state.node_history.append({
                "node": "retrieve",
                "status": "success",
                "elapsed_ms": elapsed,
                "doc_count": len(docs)
            })
        except Exception as e:
            state.node_history.append({
                "node": "retrieve",
                "status": "error",
                "error": str(e)
            })
        return state
    
    async def generate(self, state: LangGraphState) -> LangGraphState:
        """回答生成"""
        start = time.time()
        try:
            context = "\n\n".join([f"[{i+1}] {doc['text']}" for i, doc in enumerate(state.retrieved_docs)])
            
            if self.llm:
                # REAL: LLM使用
                messages = [
                    HumanMessage(content=f"""質問: {state.question}

参考文書:
{context}

上記の参考文書に基づいて回答してください。引用は[1][2]の形式で示してください。質問文の繰り返しは不要です。回答は必ず日本語で出力し、英語は使わないでください。回答のみを出力してください。""")
                ]
                answer = ""
                async for chunk in self.llm.astream(messages):
                    if chunk.content:
                        answer += chunk.content
                state.answer = _answer_only(answer, state.question)
            else:
                # DEMO: テンプレート回答（日本語のみ。質問はフロントで表示するため含めない）
                n = len(state.retrieved_docs)
                state.answer = f"""{n}件の関連文書を参照しました。

主なトピック: 検索結果に含まれる文書の概要を参照しています。
引用番号 [1]～[3] は右側の引用カードで確認できます。

（DEMOモード: 実際のLLM回答ではありません。REALモードでは日本語で回答します。）"""
            
            # Citations作成
            state.citations = [
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "snippet": doc["text"][:150] + "...",
                    "score": doc.get("score", 0.0)
                }
                for doc in state.retrieved_docs
            ]
            
            elapsed = (time.time() - start) * 1000
            state.node_history.append({
                "node": "generate",
                "status": "success",
                "elapsed_ms": elapsed
            })
        except Exception as e:
            state.node_history.append({
                "node": "generate",
                "status": "error",
                "error": str(e)
            })
            if state.retry_count < 1:
                state.retry_count += 1
                # リトライ
                return await self.generate(state)
        return state
    
    async def finalize(self, state: LangGraphState) -> LangGraphState:
        """最終化"""
        total_time = sum(n.get("elapsed_ms", 0) for n in state.node_history)
        state.metrics = {
            "total_elapsed_ms": total_time,
            "node_count": len(state.node_history),
            "retrieved_docs": len(state.retrieved_docs),
            "cache_hit": False,  # TODO: 実装
            "est_tokens": len(state.answer.split()) * 1.3,  # 簡易見積
            "node_history": state.node_history
        }
        return state
    
    async def run(
        self,
        question: str,
        use_rerank: bool = True,
        top_k: int = 4
    ) -> Dict[str, Any]:
        """実行（非ストリーミング）"""
        state = LangGraphState()
        state.question = question
        
        state = await self.classify_intent(state)
        state = await self.retrieve(state, top_k=top_k, use_rerank=use_rerank)
        state = await self.generate(state)
        state = await self.finalize(state)
        
        return {
            "answer": state.answer,
            "citations": state.citations,
            "metrics": state.metrics
        }
    
    async def run_stream(
        self,
        question: str,
        use_rerank: bool = True,
        top_k: int = 4
    ) -> AsyncIterator[Dict[str, Any]]:
        """実行（ストリーミング）"""
        state = LangGraphState()
        state.question = question
        
        # classify
        state = await self.classify_intent(state)
        yield {"type": "node", "data": {"node": "classify_intent", "status": "done"}}
        
        # retrieve
        state = await self.retrieve(state, top_k=top_k, use_rerank=use_rerank)
        yield {"type": "node", "data": {"node": "retrieve", "status": "done"}}
        
        # generate (streaming)
        if self.llm:
            context = "\n\n".join([f"[{i+1}] {doc['text']}" for i, doc in enumerate(state.retrieved_docs)])
            messages = [
                HumanMessage(content=f"""質問: {state.question}

参考文書:
{context}

上記の参考文書に基づいて回答してください。引用は[1][2]の形式で示してください。質問文の繰り返しは不要です。回答は必ず日本語で出力し、英語は使わないでください。回答のみを出力してください。""")
            ]
            answer = ""
            async for chunk in self.llm.astream(messages):
                if chunk.content:
                    answer += chunk.content
                    yield {"type": "text", "data": chunk.content}
            state.answer = _answer_only(answer, state.question)
        else:
            # DEMO: 模擬ストリーミング（日本語のみ。1チャンクで送り二重表示を防ぐ）
            n = len(state.retrieved_docs)
            demo_answer = f"""{n}件の関連文書を参照しました。

主なトピック: 検索結果に含まれる文書の概要を参照しています。
引用番号 [1]～[3] は右側の引用カードで確認できます。

（DEMOモード: 実際のLLM回答ではありません。REALモードでは日本語で回答します。）"""
            yield {"type": "text", "data": demo_answer}
            state.answer = demo_answer
        
        # citations
        state.citations = [
            {
                "id": doc["id"],
                "title": doc["title"],
                "snippet": doc["text"][:150] + "...",
                "score": doc.get("score", 0.0)
            }
            for doc in state.retrieved_docs
        ]
        
        # finalize
        state = await self.finalize(state)
        
        yield {
            "type": "done",
            "data": {
                "answer": state.answer,
                "citations": state.citations,
                "metrics": state.metrics
            }
        }

