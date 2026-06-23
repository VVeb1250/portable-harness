# Plan — pallets__flask-4992

**File:** `src/flask/config.py`, method `Config.from_file`.

**Goal:** let `from_file` open the target file in binary mode so loaders that
require it (e.g. `tomllib.load`, which rejects text-mode handles) can be used.

**Changes (only this method):**
1. Add a new keyword parameter `text: bool = True` to the signature, placed
   right after `silent: bool = False,`.
2. Where the file is opened, select the mode from `text`:
   replace `with open(filename) as f:` with
   `with open(filename, "r" if text else "rb") as f:`.
3. (Doc) add a `:param text:` line describing it opens the file in text or
   binary mode; keep the existing behavior the default (text=True).

Do not change any other method or file. Preserve all existing behavior when
`text` is left at its default.
