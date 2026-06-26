"""Optional local multilingual semantic scorer for skill discovery."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
from typing import Sequence

from paw.skill_router import SkillRecord

_MODEL = "model_quantized.onnx"
_TOKENIZER = "tokenizer.json"
_CACHE_ENV = "PAW_EMBED_CACHE"
_MAX_CACHE_ENTRIES = 8192


class OnnxSemanticScorer:
    """Embed raw tasks and full routing text in one multilingual space."""

    def __init__(
        self,
        model_dir: Path,
        *,
        max_tokens: int = 192,
        batch_size: int = 24,
        cache_path: Path | None = None,
    ) -> None:
        self.model_dir = model_dir
        self.max_tokens = max_tokens
        self.batch_size = batch_size
        self.cache_path = cache_path or _default_cache_path()
        self._session = None
        self._tokenizer = None
        self._input_names: set[str] = set()
        self._doc_cache: dict[str, object] | None = None
        self._model_sig: str | None = None

    def __call__(
        self,
        task: str,
        skills: Sequence[SkillRecord],
    ) -> dict[str, float]:
        if not skills:
            return {}
        documents = tuple(
            skill.routing_text or f"{skill.name}. {skill.description}"
            for skill in skills
        )
        matrix = self._embed_documents(documents)
        query = self._encode((task,))[0]
        similarities = matrix @ query
        return {
            skill.name: float(similarities[index])
            for index, skill in enumerate(skills)
        }

    def _embed_documents(self, documents: Sequence[str]):
        """Embed docs with a persistent per-document content-hash cache.

        Only documents whose (model+text) hash is absent get embedded; a single
        added/changed skill costs one embed, not a full re-encode. The query is
        never cached (it is unique per task)."""
        import numpy as np

        cache = self._load_doc_cache()
        sig = self._model_signature()
        keys = [_doc_key(sig, text) for text in documents]
        missing = list(dict.fromkeys(
            text for text, key in zip(documents, keys) if key not in cache
        ))
        if missing:
            fresh = self._encode(tuple(missing))
            for text, vector in zip(missing, fresh):
                cache[_doc_key(sig, text)] = vector
            self._persist_doc_cache(cache, keys)
        return np.stack([cache[key] for key in keys])

    def _load_doc_cache(self) -> dict[str, object]:
        if self._doc_cache is not None:
            return self._doc_cache
        import numpy as np

        cache: dict[str, object] = {}
        try:
            data = np.load(self.cache_path, allow_pickle=False)
            for key, vector in zip(data["keys"].tolist(), data["vecs"]):
                cache[str(key)] = vector
        except (OSError, ValueError, KeyError):
            cache = {}
        self._doc_cache = cache
        return cache

    def _persist_doc_cache(
        self,
        cache: dict[str, object],
        current_keys: Sequence[str],
    ) -> None:
        import numpy as np

        if len(cache) > _MAX_CACHE_ENTRIES:
            keep = list(dict.fromkeys(current_keys))
            extra = [k for k in cache if k not in set(keep)]
            keep += extra[: max(0, _MAX_CACHE_ENTRIES - len(keep))]
            cache = {k: cache[k] for k in keep}
            self._doc_cache = cache
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
            with open(tmp, "wb") as handle:  # file handle: no .npz auto-suffix
                np.savez(
                    handle,
                    keys=np.array(list(cache.keys())),
                    vecs=np.stack(list(cache.values()))
                    if cache
                    else np.zeros((0, 1), np.float32),
                )
            os.replace(tmp, self.cache_path)
        except OSError:
            pass

    def _model_signature(self) -> str:
        if self._model_sig is not None:
            return self._model_sig
        parts = []
        for name in (_MODEL, _TOKENIZER):
            try:
                stat = (self.model_dir / name).stat()
                parts.append(f"{name}:{stat.st_size}:{int(stat.st_mtime)}")
            except OSError:
                parts.append(f"{name}:0")
        parts.append(f"tok{self.max_tokens}")
        self._model_sig = "|".join(parts)
        return self._model_sig

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


def _doc_key(model_sig: str, text: str) -> str:
    digest = hashlib.sha1(f"{model_sig}\x00{text}".encode("utf-8"))
    return digest.hexdigest()


def _default_cache_path() -> Path:
    configured = os.environ.get(_CACHE_ENV)
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".cache" / "paw" / "skill-embeddings.npz"


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
