"""Optional local multilingual semantic scorer for skill discovery."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Sequence

from paw.skill_router import SkillRecord

_MODEL = "model_quantized.onnx"
_TOKENIZER = "tokenizer.json"


class OnnxSemanticScorer:
    """Embed raw tasks and full routing text in one multilingual space."""

    def __init__(
        self,
        model_dir: Path,
        *,
        max_tokens: int = 192,
        batch_size: int = 24,
    ) -> None:
        self.model_dir = model_dir
        self.max_tokens = max_tokens
        self.batch_size = batch_size
        self._session = None
        self._tokenizer = None
        self._input_names: set[str] = set()

    def __call__(
        self,
        task: str,
        skills: Sequence[SkillRecord],
    ) -> dict[str, float]:
        if not skills:
            return {}
        import numpy as np

        query = self._encode((task,))[0]
        documents = tuple(
            skill.routing_text or f"{skill.name}. {skill.description}"
            for skill in skills
        )
        matrix = self._encode(documents)
        similarities = matrix @ query
        return {
            skill.name: float(similarities[index])
            for index, skill in enumerate(skills)
        }

    def _load(self) -> None:
        if self._session is not None:
            return
        import onnxruntime as ort
        from tokenizers import Tokenizer

        options = ort.SessionOptions()
        options.log_severity_level = 3
        options.intra_op_num_threads = max(1, (os.cpu_count() or 2) // 2)
        self._session = ort.InferenceSession(
            str(self.model_dir / _MODEL),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {
            item.name for item in self._session.get_inputs()
        }
        tokenizer = Tokenizer.from_file(str(self.model_dir / _TOKENIZER))
        pad_id = tokenizer.token_to_id("<pad>")
        tokenizer.enable_truncation(max_length=self.max_tokens)
        tokenizer.enable_padding(
            pad_id=1 if pad_id is None else pad_id,
            pad_token="<pad>",
        )
        self._tokenizer = tokenizer

    def _encode(self, texts: Sequence[str]):
        import numpy as np

        self._load()
        matrices = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            encoded = self._tokenizer.encode_batch(list(batch))
            ids = np.array([item.ids for item in encoded], dtype=np.int64)
            mask = np.array(
                [item.attention_mask for item in encoded],
                dtype=np.int64,
            )
            feed = {}
            if "input_ids" in self._input_names:
                feed["input_ids"] = ids
            if "attention_mask" in self._input_names:
                feed["attention_mask"] = mask
            if "token_type_ids" in self._input_names:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = self._session.run(None, feed)[0]
            weights = mask.astype(np.float32)[..., None]
            pooled = (hidden * weights).sum(axis=1) / np.clip(
                weights.sum(axis=1),
                1e-9,
                None,
            )
            pooled /= np.clip(
                np.linalg.norm(pooled, axis=1, keepdims=True),
                1e-12,
                None,
            )
            matrices.append(pooled.astype(np.float32))
        return np.concatenate(matrices, axis=0)


def default_semantic_scorer() -> OnnxSemanticScorer | None:
    """Return a local scorer when model files and dependencies are present."""
    if not all(
        importlib.util.find_spec(module)
        for module in ("numpy", "onnxruntime", "tokenizers")
    ):
        return None
    for directory in _model_candidates():
        if (directory / _MODEL).is_file() and (
            directory / _TOKENIZER
        ).is_file():
            return OnnxSemanticScorer(directory)
    return None


def _model_candidates() -> tuple[Path, ...]:
    configured = os.environ.get("PAW_EMBED_MODEL_DIR")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend(
        (
            Path(__file__).resolve().parent / "models",
            Path.home() / ".claude" / "hooks" / "models",
        )
    )
    return tuple(candidates)
