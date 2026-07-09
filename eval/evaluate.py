"""Protocolo de avaliação do Themis.IA: RAG vs. baseline (LLM puro).

Para cada pergunta canônica:
1. recupera o contexto na base vetorial;
2. gera a resposta (com contexto, no modo `rag`; sem contexto, no modo `baseline`);
3. um juiz LLM (LLM-as-a-judge) mede a fidelidade ao contexto (groundedness):
   fração das afirmações da resposta que são sustentadas pelos trechos recuperados.

Requer GOOGLE_API_KEY no .env e a base populada (python scripts/setup_db.py).

Uso:
    python eval/evaluate.py --mode rag --runs 3
    python eval/evaluate.py --mode baseline --runs 3
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402

from src.rag import engine  # noqa: E402
from src.rag.retriever import retrieve, trim_to_budget  # noqa: E402
from src.rag.vector_store import get_vector_store  # noqa: E402

JUDGE_SYSTEM = (
    "Você é um avaliador rigoroso de sistemas RAG jurídicos. Receberá trechos-fonte, "
    "uma resposta gerada e uma resposta de referência. Avalie a resposta gerada e "
    "retorne APENAS um JSON válido, sem markdown, no formato: "
    '{"total_claims": <int>, "supported_claims": <int>, "groundedness": <float 0-1>, '
    '"matches_reference": <true|false>, "comment": "<curto>"} — onde groundedness é a '
    "fração de afirmações factuais da resposta sustentadas pelos trechos-fonte, e "
    "matches_reference indica se a resposta contém a informação essencial da referência."
)


def judge(llm, context: str, answer: str, reference: str) -> dict:
    prompt = (
        f"## Trechos-fonte\n{context}\n\n"
        f"## Resposta gerada\n{answer}\n\n"
        f"## Resposta de referência\n{reference}\n\n"
        "Avalie conforme as instruções e retorne apenas o JSON."
    )
    raw = llm.invoke([SystemMessage(content=JUDGE_SYSTEM), HumanMessage(content=prompt)]).content
    match = re.search(r"\{.*\}", raw if isinstance(raw, str) else str(raw), re.DOTALL)
    if not match:
        return {"groundedness": None, "matches_reference": None, "comment": "juiz não retornou JSON"}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"groundedness": None, "matches_reference": None, "comment": "JSON do juiz malformado"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="eval/questions.json")
    parser.add_argument("--mode", choices=["rag", "baseline"], default="rag")
    parser.add_argument("--runs", type=int, default=1, help="repetições para média ± desvio")
    parser.add_argument("--output", default=None, help="arquivo JSON de saída")
    args = parser.parse_args()

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    vs = get_vector_store()
    judge_llm = engine.get_llm(temperature=0.0)

    all_results: list[dict] = []
    for run in range(1, args.runs + 1):
        for item in questions:
            question, reference = item["question"], item.get("reference", "")

            # O contexto recuperado é a régua do juiz nos dois modos: no baseline
            # ele existe mas NÃO é entregue ao gerador (protocolo da metodologia).
            chunks = trim_to_budget(retrieve(vs, question))
            context = engine.format_context(chunks)

            start = time.perf_counter()
            if args.mode == "rag":
                response = engine.answer_question(
                    vs, question, persona_key="analista", lexml_mode="nunca", log=False
                )
                answer, latency = response.answer, response.latency_total_s
            else:
                answer, latency = engine.answer_baseline(question)
            elapsed = round(time.perf_counter() - start, 3)

            verdict = judge(judge_llm, context, answer, reference)
            result = {
                "run": run,
                "id": item.get("id"),
                "mode": args.mode,
                "question": question,
                "answer": answer,
                "latency_s": latency or elapsed,
                "groundedness": verdict.get("groundedness"),
                "matches_reference": verdict.get("matches_reference"),
                "judge_comment": verdict.get("comment", ""),
            }
            all_results.append(result)
            grounded = result["groundedness"]
            grounded_str = f"{grounded:.2f}" if isinstance(grounded, (int, float)) else "n/a"
            print(
                f"[run {run}] Q{item.get('id')}: groundedness={grounded_str} "
                f"ok_ref={result['matches_reference']} latency={result['latency_s']}s"
            )

    grounded_values = [r["groundedness"] for r in all_results if isinstance(r["groundedness"], (int, float))]
    latencies = [r["latency_s"] for r in all_results if isinstance(r["latency_s"], (int, float))]
    match_values = [r["matches_reference"] for r in all_results if r["matches_reference"] is not None]

    summary = {
        "mode": args.mode,
        "runs": args.runs,
        "n_questions": len(questions),
        "groundedness_mean": round(statistics.mean(grounded_values), 3) if grounded_values else None,
        "groundedness_std": (
            round(statistics.stdev(grounded_values), 3) if len(grounded_values) > 1 else 0.0
        ),
        "reference_match_rate": (
            round(sum(bool(v) for v in match_values) / len(match_values), 3) if match_values else None
        ),
        "latency_mean_s": round(statistics.mean(latencies), 2) if latencies else None,
        "latency_p95_s": (
            round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2) if latencies else None
        ),
    }

    print("\n===== RESUMO =====")
    for key, value in summary.items():
        print(f"{key}: {value}")

    output = Path(args.output or f"eval/results_{args.mode}.json")
    output.write_text(
        json.dumps({"summary": summary, "results": all_results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nResultados salvos em {output}")


if __name__ == "__main__":
    main()
