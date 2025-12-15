"""
評価スクリプト: chunk/top-k/rerank比較
"""
import json
import asyncio
import time
from pathlib import Path
from typing import List, Dict, Any
import csv

try:
    import aiohttp
except ImportError:
    print("aiohttpが必要です: pip install aiohttp")
    exit(1)

# API URL
API_URL = "http://localhost:8000"

async def run_question(question: str, config: Dict[str, Any], token: str) -> Dict[str, Any]:
    """1問を実行"""
    
    async with aiohttp.ClientSession() as session:
        start = time.time()
        async with session.post(
            f"{API_URL}/ask",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "question": question,
                "use_rerank": config.get("use_rerank", True),
                "top_k": config.get("top_k", 4)
            }
        ) as resp:
            if resp.status != 200:
                return {"error": f"HTTP {resp.status}"}
            
            answer = ""
            citations = []
            metrics = {}
            
            async for line_bytes in resp.content:
                line = line_bytes.decode('utf-8', errors='ignore')
                if line.startswith("data: "):
                    data = line[6:].strip()
                    if data and data != "[DONE]":
                        answer += data
                elif line.startswith("event: citations"):
                    # 次の行を読み取る
                    try:
                        next_line_bytes = await resp.content.__anext__()
                        next_line = next_line_bytes.decode('utf-8', errors='ignore')
                        if next_line.startswith("data: "):
                            citations = json.loads(next_line[6:].strip())
                    except:
                        pass
                elif line.startswith("event: metrics"):
                    # 次の行を読み取る
                    try:
                        next_line_bytes = await resp.content.__anext__()
                        next_line = next_line_bytes.decode('utf-8', errors='ignore')
                        if next_line.startswith("data: "):
                            metrics = json.loads(next_line[6:].strip())
                    except:
                        pass
            
            elapsed = (time.time() - start) * 1000
            
            return {
                "question": question,
                "answer": answer,
                "citations": citations,
                "metrics": metrics,
                "elapsed_ms": elapsed,
                "config": config
            }

async def run_eval():
    """評価実行"""
    # ログイン（DEMO）
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/auth/login",
            json={"passcode": "demo"}
        ) as resp:
            data = await resp.json()
            token = data["token"]
    
    # 質問読み込み
    questions_file = Path(__file__).parent / "questions.jsonl"
    questions = []
    with open(questions_file, "r", encoding="utf-8") as f:
        for line in f:
            questions.append(json.loads(line)["question"])
    
    # 設定パターン
    configs = [
        {"name": "A: top_k=2, rerank=off", "top_k": 2, "use_rerank": False},
        {"name": "B: top_k=4, rerank=off", "top_k": 4, "use_rerank": False},
        {"name": "C: top_k=4, rerank=on", "top_k": 4, "use_rerank": True},
        {"name": "D: top_k=8, rerank=on", "top_k": 8, "use_rerank": True},
    ]
    
    results = []
    
    for config in configs:
        print(f"\n実行中: {config['name']}")
        for q in questions:
            result = await run_question(q, config, token)
            result["config_name"] = config["name"]
            results.append(result)
            print(f"  {q[:30]}... {result.get('elapsed_ms', 0):.0f}ms")
    
    # CSV出力
    csv_file = Path(__file__).parent / "results.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "config_name", "question", "elapsed_ms", "citation_count", "total_elapsed_ms"
        ])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "config_name": r.get("config_name", ""),
                "question": r.get("question", ""),
                "elapsed_ms": r.get("elapsed_ms", 0),
                "citation_count": len(r.get("citations", [])),
                "total_elapsed_ms": r.get("metrics", {}).get("total_elapsed_ms", 0)
            })
    
    # Markdown出力
    md_file = Path(__file__).parent / "results.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("# 評価結果\n\n")
        
        # 集計
        by_config = {}
        for r in results:
            name = r.get("config_name", "unknown")
            if name not in by_config:
                by_config[name] = {"times": [], "citations": []}
            by_config[name]["times"].append(r.get("elapsed_ms", 0))
            by_config[name]["citations"].append(len(r.get("citations", [])))
        
        f.write("## 集計結果\n\n")
        f.write("| 設定 | 平均時間(ms) | P50(ms) | P95(ms) | 平均引用数 |\n")
        f.write("|------|-------------|---------|---------|----------|\n")
        
        for name, data in by_config.items():
            times = sorted(data["times"])
            n = len(times)
            avg = sum(times) / n if n > 0 else 0
            p50 = times[n // 2] if n > 0 else 0
            p95 = times[int(n * 0.95)] if n > 0 else 0
            avg_cites = sum(data["citations"]) / n if n > 0 else 0
            
            f.write(f"| {name} | {avg:.0f} | {p50:.0f} | {p95:.0f} | {avg_cites:.1f} |\n")
        
        f.write("\n## 詳細結果\n\n")
        for r in results:
            f.write(f"### {r.get('config_name')}: {r.get('question')}\n\n")
            f.write(f"- 時間: {r.get('elapsed_ms', 0):.0f}ms\n")
            f.write(f"- 引用数: {len(r.get('citations', []))}\n")
            f.write(f"- 回答: {r.get('answer', '')[:100]}...\n\n")
    
    print(f"\n完了: {csv_file}, {md_file}")

if __name__ == "__main__":
    asyncio.run(run_eval())

