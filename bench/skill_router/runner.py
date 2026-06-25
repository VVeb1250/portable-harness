"""Frozen multilingual benchmark for skill discovery and context cost."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from paw.semantic_router import OnnxSemanticScorer, default_semantic_scorer
from paw.skill_graph import (
    SkillGraph,
    default_skill_graph_path,
    load_skill_graph,
)
from paw.skill_router import (
    SkillRecord,
    default_skill_roots,
    discover_skills,
    suggest_skill,
)

ARMS = (
    "load_all",
    "metadata_lexical",
    "semantic_top3",
    "graph_top3",
    "oracle",
)
DEFAULT_COHORT = Path(__file__).with_name("cohort_2026-06-26.json")
DEFAULT_OUTPUT = Path(__file__).with_name("results_2026-06-26")


@dataclass(frozen=True)
class BenchCase:
    id: str
    intent: str
    language: str
    query: str
    required_skills: tuple[str, ...]
    kind: str


def load_cohort(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("cohort root must be an object")
    return data


def expand_cohort(source: dict[str, object]) -> tuple[BenchCase, ...]:
    languages = source.get("languages")
    intents = source.get("intents")
    if not isinstance(languages, list) or not isinstance(intents, list):
        raise ValueError("cohort requires languages and intents lists")
    cases: list[BenchCase] = []
    for raw in intents:
        if not isinstance(raw, dict):
            raise ValueError("intent must be an object")
        intent_id = str(raw.get("id", "")).strip()
        kind = str(raw.get("kind", "")).strip()
        queries = raw.get("queries")
        required = raw.get("required_skills", [])
        if (
            not intent_id
            or kind not in {"positive", "silence"}
            or not isinstance(queries, dict)
            or not isinstance(required, list)
        ):
            raise ValueError(f"invalid intent: {intent_id or '<missing>'}")
        required_skills = tuple(str(item) for item in required)
        if kind == "silence" and required_skills:
            raise ValueError(f"silence intent {intent_id} cannot require skills")
        for language in languages:
            language = str(language)
            query = queries.get(language)
            if not isinstance(query, str) or not query.strip():
                raise ValueError(f"{intent_id} missing query for {language}")
            cases.append(
                BenchCase(
                    id=f"{intent_id}:{language}",
                    intent=intent_id,
                    language=language,
                    query=query.strip(),
                    required_skills=required_skills,
                    kind=kind,
                )
            )
    return tuple(cases)


def token_count(text: str) -> int:
    try:
        import tiktoken

        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except Exception:
        return max(1, (len(text.encode("utf-8")) + 3) // 4)


def evaluate_predictions(
    predictions: Sequence[dict[str, object]],
) -> dict[str, object]:
    positive = [row for row in predictions if row["required"]]
    silence = [row for row in predictions if not row["required"]]
    required_total = sum(len(row["required"]) for row in positive)
    hits = 0
    predicted_positive = 0
    full = 0
    reciprocal: list[float] = []
    for row in positive:
        required = set(row["required"])
        predicted = list(row["predicted"])
        overlap = required & set(predicted)
        hits += len(overlap)
        predicted_positive += len(predicted)
        full += int(required.issubset(predicted))
        ranks = [
            predicted.index(skill) + 1
            for skill in required
            if skill in predicted
        ]
        reciprocal.append(1.0 / min(ranks) if ranks else 0.0)
    silence_hits = sum(not row["predicted"] for row in silence)
    tokens = [int(row["context_tokens"]) for row in predictions]
    latencies = [float(row["latency_ms"]) for row in predictions]
    by_language: dict[str, dict[str, object]] = {}
    for language in sorted({str(row["language"]) for row in predictions}):
        rows = [row for row in predictions if row["language"] == language]
        lang_positive = [row for row in rows if row["required"]]
        lang_required = sum(len(row["required"]) for row in lang_positive)
        lang_hits = sum(
            len(set(row["required"]) & set(row["predicted"]))
            for row in lang_positive
        )
        lang_silence = [row for row in rows if not row["required"]]
        by_language[language] = {
            "cases": len(rows),
            "recall_at_k": _ratio(lang_hits, lang_required),
            "full_coverage": _ratio(
                sum(
                    set(row["required"]).issubset(row["predicted"])
                    for row in lang_positive
                ),
                len(lang_positive),
            ),
            "silence_accuracy": _ratio(
                sum(not row["predicted"] for row in lang_silence),
                len(lang_silence),
            ),
            "mean_context_tokens": _mean(
                [int(row["context_tokens"]) for row in rows]
            ),
        }
    return {
        "cases": len(predictions),
        "positive_cases": len(positive),
        "silence_cases": len(silence),
        "recall_at_k": _ratio(hits, required_total),
        "precision_at_k": _ratio(hits, predicted_positive),
        "full_coverage": _ratio(full, len(positive)),
        "mrr": _mean(reciprocal),
        "silence_accuracy": _ratio(silence_hits, len(silence)),
        "false_positive_rate": 1.0 - _ratio(silence_hits, len(silence)),
        "mean_context_tokens": _mean(tokens),
        "median_context_tokens": statistics.median(tokens) if tokens else 0.0,
        "mean_latency_ms": _mean(latencies),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "by_language": by_language,
    }


def build_manifest(
    *,
    cohort_path: Path,
    graph_path: Path,
    catalog_hash: str,
    case_count: int,
) -> dict[str, object]:
    return {
        "schema": "paw-skill-router-bench/v1",
        "created": str(date.today()),
        "arms": list(ARMS),
        "case_count": case_count,
        "cohort": str(cohort_path),
        "cohort_sha256": _file_hash(cohort_path),
        "graph": str(graph_path),
        "graph_sha256": _file_hash(graph_path),
        "catalog_sha256": catalog_hash,
        "tokenizer": "o200k_base if available; utf8-bytes/4 fallback",
        "notes": (
            "Retrieval/context benchmark only. load_all measures availability "
            "and context tax, not model selection or end-to-end task success."
        ),
    }


def run_benchmark(
    *,
    cohort_path: Path = DEFAULT_COHORT,
    output_dir: Path = DEFAULT_OUTPUT,
    graph_path: Path | None = None,
    skills_roots: Sequence[Path] | None = None,
) -> dict[str, object]:
    source = load_cohort(cohort_path)
    cases = expand_cohort(source)
    roots = tuple(skills_roots or default_skill_roots(Path.cwd()))
    skills = discover_skills(roots)
    if not skills:
        raise RuntimeError("no skills discovered")
    missing = sorted(
        {
            skill
            for case in cases
            for skill in case.required_skills
            if skill not in {record.name for record in skills}
        }
    )
    if missing:
        raise RuntimeError("required skills missing from catalog: " + ", ".join(missing))

    resolved_graph = graph_path or default_skill_graph_path()
    graph = load_skill_graph(resolved_graph, skills)
    semantic = default_semantic_scorer()
    if semantic is None:
        raise RuntimeError("multilingual ONNX scorer is unavailable")

    semantic_scores, graph_scores, index_stats = _precompute_scores(
        semantic,
        cases,
        skills,
        graph,
    )
    metadata_payload = _metadata_payload(skills)
    skill_by_name = {skill.name: skill for skill in skills}
    predictions: dict[str, list[dict[str, object]]] = {
        arm: [] for arm in ARMS
    }

    for index, case in enumerate(cases):
        required = list(case.required_skills)
        common = {
            "case_id": case.id,
            "intent": case.intent,
            "language": case.language,
            "required": required,
        }

        predictions["load_all"].append(
            {
                **common,
                "predicted": [skill.name for skill in skills],
                "context_tokens": token_count(metadata_payload),
                "latency_ms": 0.0,
            }
        )

        start = time.perf_counter()
        lexical = suggest_skill(
            case.query,
            skills,
            max_candidates=3,
        )
        predictions["metadata_lexical"].append(
            _prediction(
                common,
                lexical,
                (time.perf_counter() - start) * 1000.0,
            )
        )

        start = time.perf_counter()
        semantic_result = suggest_skill(
            case.query,
            skills,
            max_candidates=3,
            semantic_scorer=_fixed_scorer(semantic_scores[index]),
        )
        predictions["semantic_top3"].append(
            _prediction(
                common,
                semantic_result,
                index_stats["mean_query_encode_ms"]
                + (time.perf_counter() - start) * 1000.0,
            )
        )

        start = time.perf_counter()
        graph_result = suggest_skill(
            case.query,
            skills,
            max_candidates=3,
            semantic_scorer=_fixed_scorer(graph_scores[index]),
            graph=graph,
        )
        predictions["graph_top3"].append(
            _prediction(
                common,
                graph_result,
                index_stats["mean_query_encode_ms"]
                + (time.perf_counter() - start) * 1000.0,
            )
        )

        oracle_records = [
            skill_by_name[name] for name in case.required_skills
        ]
        oracle_payload = _cards_payload(oracle_records)
        predictions["oracle"].append(
            {
                **common,
                "predicted": required,
                "context_tokens": token_count(oracle_payload),
                "latency_ms": 0.0,
            }
        )

    metrics = {
        arm: evaluate_predictions(rows)
        for arm, rows in predictions.items()
    }
    catalog_hash = _catalog_hash(skills)
    manifest = build_manifest(
        cohort_path=cohort_path,
        graph_path=resolved_graph,
        catalog_hash=catalog_hash,
        case_count=len(cases),
    )
    result = {
        "manifest": manifest,
        "catalog": {
            "skill_count": len(skills),
            "metadata_context_tokens": token_count(metadata_payload),
        },
        "index": index_stats,
        "metrics": metrics,
    }
    _write_outputs(output_dir, result, predictions)
    return result


def _precompute_scores(
    scorer: OnnxSemanticScorer,
    cases: Sequence[BenchCase],
    skills: Sequence[SkillRecord],
    graph: SkillGraph,
) -> tuple[list[dict[str, float]], list[dict[str, float]], dict[str, float]]:
    skill_records = tuple(skills)
    graph_records = graph.search_records()
    queries = tuple(case.query for case in cases)

    started = time.perf_counter()
    skill_matrix = scorer._encode(  # benchmark intentionally reuses local backend
        tuple(
            skill.routing_text or f"{skill.name}. {skill.description}"
            for skill in skill_records
        )
    )
    graph_matrix = scorer._encode(
        tuple(
            record.routing_text or f"{record.name}. {record.description}"
            for record in graph_records
        )
    )
    index_ms = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    query_matrix = scorer._encode(queries)
    query_ms = (time.perf_counter() - started) * 1000.0
    skill_similarities = query_matrix @ skill_matrix.T
    graph_similarities = query_matrix @ graph_matrix.T
    skill_scores = [
        {
            record.name: float(skill_similarities[row, column])
            for column, record in enumerate(skill_records)
        }
        for row in range(len(cases))
    ]
    graph_scores = [
        {
            record.name: float(graph_similarities[row, column])
            for column, record in enumerate(graph_records)
        }
        for row in range(len(cases))
    ]
    return (
        skill_scores,
        graph_scores,
        {
            "corpus_encode_ms": round(index_ms, 3),
            "query_encode_ms": round(query_ms, 3),
            "mean_query_encode_ms": round(query_ms / len(cases), 3),
        },
    )


def _prediction(
    common: dict[str, object],
    result,
    latency_ms: float,
) -> dict[str, object]:
    names = [item.skill for item in result.suggestions]
    if not names:
        names = [item.skill for item in result.candidates]
    return {
        **common,
        "predicted": names,
        "context_tokens": token_count(
            json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":"))
        ),
        "latency_ms": round(latency_ms, 3),
    }


def _fixed_scorer(scores: dict[str, float]):
    def score(
        task: str,
        records: Sequence[SkillRecord],
    ) -> dict[str, float]:
        del task
        return {record.name: scores.get(record.name, 0.0) for record in records}

    return score


def _metadata_payload(skills: Sequence[SkillRecord]) -> str:
    return json.dumps(
        [
            {"name": skill.name, "description": skill.description}
            for skill in skills
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _cards_payload(skills: Sequence[SkillRecord]) -> str:
    return json.dumps(
        [
            {"skill": skill.name, "description": skill.description[:160]}
            for skill in skills
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _catalog_hash(skills: Sequence[SkillRecord]) -> str:
    payload = "\n".join(
        f"{skill.name}\0{skill.description}\0{skill.path}"
        for skill in sorted(skills, key=lambda record: record.name)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_outputs(
    output_dir: Path,
    result: dict[str, object],
    predictions: dict[str, list[dict[str, object]]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(result["manifest"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for arm in ARMS:
            for row in predictions[arm]:
                handle.write(
                    json.dumps({"arm": arm, **row}, ensure_ascii=False) + "\n"
                )
    (output_dir / "REPORT.md").write_text(
        _markdown_report(result),
        encoding="utf-8",
    )


def _markdown_report(result: dict[str, object]) -> str:
    metrics = result["metrics"]
    lines = [
        "# Multilingual Skill Router Benchmark",
        "",
        f"- Cases: {result['manifest']['case_count']}",
        f"- Skills: {result['catalog']['skill_count']}",
        f"- Load-all metadata tokens: {result['catalog']['metadata_context_tokens']}",
        "",
        "| Arm | Recall@K | Full coverage | Precision@K | Silence | Mean ctx tok | Mean ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ARMS:
        item = metrics[arm]
        lines.append(
            "| "
            + " | ".join(
                (
                    arm,
                    _pct(item["recall_at_k"]),
                    _pct(item["full_coverage"]),
                    _pct(item["precision_at_k"]),
                    _pct(item["silence_accuracy"]),
                    f"{item['mean_context_tokens']:.1f}",
                    f"{item['mean_latency_ms']:.2f}",
                )
            )
            + " |"
        )
    lines.extend(
        (
            "",
            "## Notes",
            "",
            "- `load_all` exposes every skill metadata record, so recall is an availability ceiling, not autonomous selection accuracy.",
            "- `oracle` exposes only labeled required skills and is the context-efficiency ceiling.",
            "- This run measures retrieval, silence, compatibility coverage, context tokens, and local latency—not end-to-end task completion.",
            "",
        )
    )
    return "\n".join(lines)


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 6) if denominator else 0.0


def _mean(values: Iterable[int | float]) -> float:
    materialized = [float(value) for value in values]
    return round(statistics.mean(materialized), 6) if materialized else 0.0


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return round(float(ordered[index]), 6)


def _pct(value: float) -> str:
    return f"{float(value) * 100:.1f}%"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--graph", type=Path, default=default_skill_graph_path())
    args = parser.parse_args(argv)
    result = run_benchmark(
        cohort_path=args.cohort,
        output_dir=args.output,
        graph_path=args.graph,
    )
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
