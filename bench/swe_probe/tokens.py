"""tiktoken token accounting for the cost axis — no paid API.

The existential question is whether the team strategy (Claude plans once,
DeepSeek loops) burns far less scarce *Claude* quota than claude-solo looping
on the seat. Claude here = this subscription seat ($0 marginal), so we never
call a paid Anthropic API. We still need an honest, symmetric token count to
compare the two arms.

tiktoken is that proxy: it is NOT Anthropic's tokenizer, so absolute counts
are approximate, but it is applied identically to both arms, so the DELTA
between claude-solo and team is valid (STATUS §D: delta readable, absolute
optimistic). We count the actual content that crosses the seat — the problem
+ oracle files read in, and the plan / patches written out.
"""
from __future__ import annotations

import tiktoken

# o200k_base: encoding family of the current frontier models; a stable,
# reproducible proxy. Any fixed encoding works since only the delta matters.
_ENC = tiktoken.get_encoding("o200k_base")


def count(text: str) -> int:
    return len(_ENC.encode(text or ""))


def count_many(texts) -> int:
    return sum(count(t) for t in texts)
