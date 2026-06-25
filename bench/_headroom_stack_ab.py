"""Deterministic Headroom stack-marginal benchmark.

Run inside an environment that has headroom-ai installed:

    python bench/_headroom_stack_ab.py

The benchmark uses saved raw/RTK command outputs plus controlled synthetic
fixtures. It measures into-context tokens, compressor latency, and exact
sentinel retention. It does not call an LLM or any paid API.
"""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

import tiktoken
from headroom.compression import compress
from headroom.transforms.smart_crusher import SmartCrusher, SmartCrusherConfig


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bench" / "out" / "compress"
ENC = tiktoken.get_encoding("cl100k_base")
SMART_CRUSHER = SmartCrusher(SmartCrusherConfig(min_tokens_to_crush=200))


@dataclass(frozen=True)
class Fixture:
    name: str
    content: str
    needles: tuple[str, ...] = ()
    source: str = "synthetic"


def tokens(text: str) -> int:
    return len(ENC.encode(text, disallowed_special=()))


def compressed_text(result: object) -> str:
    for attr in ("compressed", "text", "content"):
        value = getattr(result, attr, None)
        if isinstance(value, str):
            return value
    if isinstance(result, str):
        return result
    raise TypeError(f"Unsupported Headroom result: {type(result)!r}")


def run_compressor(compressor: object, content: str, repeats: int = 3) -> tuple[str, float]:
    # Warm the tokenizer/model and exclude one-time initialization from latency.
    compressor(content)
    outputs: list[str] = []
    timings: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        outputs.append(compressed_text(compressor(content)))
        timings.append((time.perf_counter() - start) * 1000)
    if len(set(outputs)) != 1:
        raise RuntimeError("Headroom output was not deterministic across repeats")
    return outputs[0], statistics.median(timings)


def run_headroom(content: str, repeats: int = 3) -> tuple[str, float]:
    return run_compressor(compress, content, repeats)


def run_smart_crusher(content: str, repeats: int = 3) -> tuple[str, float]:
    return run_compressor(SMART_CRUSHER.crush, content, repeats)


def synthetic_fixtures() -> list[Fixture]:
    rows = [
        {
            "id": i,
            "status": "ok",
            "region": f"r{i % 5}",
            "latency_ms": 20 + (i % 17),
            "message": "periodic health check completed normally",
        }
        for i in range(500)
    ]
    rows[367] = {
        "id": 367,
        "status": "critical",
        "incident_id": "INC-367-X",
        "region": "r2",
        "latency_ms": 9917,
        "error_code": "PAW-E917",
        "host": "db-17",
        "resolution": "rotate-cert-chain",
        "message": "FATAL certificate validation failure",
    }
    json_fixture = Fixture(
        "json_500",
        json.dumps(rows, ensure_ascii=False),
        ("PAW-E917", "db-17", "rotate-cert-chain", "INC-367-X"),
    )

    log_lines = [
        f"2026-06-24T12:{i % 60:02d}:00Z INFO worker={i % 8} build step completed"
        for i in range(600)
    ]
    log_lines[421] = (
        "2026-06-24T12:41:00Z FATAL error=PAW-E421 host=builder-09 "
        "resolution=clear-stale-lock"
    )
    log_fixture = Fixture(
        "build_log_600",
        "\n".join(log_lines),
        ("PAW-E421", "builder-09", "clear-stale-lock"),
    )

    search_lines = [
        f"src/module_{i % 20}.py:{i + 1}: normal_search_result_{i}"
        for i in range(300)
    ]
    search_lines[233] = (
        "src/router.py:918: TARGET_PAW_ROUTE preserve_this_exact_search_hit"
    )
    search_fixture = Fixture(
        "search_300",
        "\n".join(search_lines),
        ("TARGET_PAW_ROUTE", "src/router.py:918"),
    )

    functions = [
        f"def generated_{i}(value: int) -> int:\n    return value + {i}\n"
        for i in range(250)
    ]
    functions[177] = (
        "def critical_handler(value: int) -> int:\n"
        '    """PAW-CODE-177 must remain visible."""\n'
        "    return value // 0  # TARGET_DIV_ZERO\n"
    )
    code_fixture = Fixture(
        "python_code_250",
        "\n".join(functions),
        ("PAW-CODE-177", "TARGET_DIV_ZERO", "critical_handler"),
    )
    return [json_fixture, log_fixture, search_fixture, code_fixture]


def saved_stack_fixtures() -> list[tuple[str, str, str]]:
    pairs: list[tuple[str, str, str]] = []
    for raw_path in sorted(OUT.glob("*.raw.txt")):
        name = raw_path.name.removesuffix(".raw.txt")
        rtk_path = OUT / f"{name}.rtk.txt"
        if rtk_path.exists():
            pairs.append(
                (
                    name,
                    raw_path.read_text(encoding="utf-8"),
                    rtk_path.read_text(encoding="utf-8"),
                )
            )
    return pairs


def main() -> None:
    results: dict[str, object] = {"schema": "paw.headroom-stack-ab.v1"}

    stack_rows = []
    for name, raw, rtk in saved_stack_fixtures():
        hr_raw, raw_ms = run_headroom(raw)
        hr_rtk, rtk_ms = run_headroom(rtk)
        raw_t, rtk_t = tokens(raw), tokens(rtk)
        hr_raw_t, hr_rtk_t = tokens(hr_raw), tokens(hr_rtk)
        stack_rows.append(
            {
                "fixture": name,
                "raw_tokens": raw_t,
                "rtk_tokens": rtk_t,
                "headroom_raw_tokens": hr_raw_t,
                "rtk_headroom_tokens": hr_rtk_t,
                "rtk_saved_pct": round(100 * (1 - rtk_t / raw_t), 1)
                if raw_t
                else 0,
                "headroom_saved_pct": round(100 * (1 - hr_raw_t / raw_t), 1)
                if raw_t
                else 0,
                "headroom_after_rtk_marginal_pct": round(
                    100 * (1 - hr_rtk_t / rtk_t), 1
                )
                if rtk_t
                else 0,
                "headroom_raw_latency_ms": round(raw_ms, 2),
                "headroom_after_rtk_latency_ms": round(rtk_ms, 2),
            }
        )
    results["stack_marginal"] = stack_rows

    home_rows = []
    for fixture in synthetic_fixtures():
        output, latency_ms = run_headroom(fixture.content)
        before, after = tokens(fixture.content), tokens(output)
        missing = [needle for needle in fixture.needles if needle not in output]
        row = {
            "fixture": fixture.name,
            "before_tokens": before,
            "after_tokens": after,
            "saved_pct": round(100 * (1 - after / before), 1),
            "latency_ms": round(latency_ms, 2),
            "correct": not missing,
            "missing_needles": missing,
        }
        if fixture.name == "json_500":
            smart_output, smart_latency_ms = run_smart_crusher(fixture.content)
            smart_after = tokens(smart_output)
            smart_missing = [
                needle for needle in fixture.needles if needle not in smart_output
            ]
            row.update(
                {
                    "smart_crusher_tokens": smart_after,
                    "smart_crusher_saved_pct": round(
                        100 * (1 - smart_after / before), 1
                    ),
                    "smart_crusher_latency_ms": round(smart_latency_ms, 2),
                    "smart_crusher_correct": not smart_missing,
                    "smart_crusher_missing_needles": smart_missing,
                }
            )
        home_rows.append(row)
    results["home_turf"] = home_rows

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
