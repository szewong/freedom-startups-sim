"""Inline the live simulator into one self-contained page.

web/sim.html loads worlds.js and engine.js as separate files, which is the right
shape on disk — the engine is shared with the validator and the config is
generated. A hosted artifact has to be a single file with no external requests,
so this inlines them and strips the document shell the host supplies itself.

Generated, never edited: rerun after any change to the page, the engine, or a
recalibration.

    .venv/bin/python scripts/bundle_sim.py
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path("web/sim.html")
OUT = Path("web/sim.bundle.html")


def main() -> None:
    html = SRC.read_text()

    # Replace each external script with its contents.
    def inline(match: re.Match[str]) -> str:
        name = match.group(1)
        code = Path("web") / name
        return f"<script>\n/* inlined from web/{name} */\n{code.read_text()}</script>"

    html, n = re.subn(r'<script src="([^"]+)"></script>', inline, html)
    if n != 2:
        raise SystemExit(f"expected 2 external scripts to inline, found {n}")

    # The host supplies the document shell, so hand it body content only.
    html = re.sub(r"^<!doctype html>\s*<html[^>]*>\s*<head>\s*", "", html, flags=re.I)
    html = html.replace('<meta charset="utf-8">\n', "")
    html = re.sub(r'<meta name="viewport"[^>]*>\s*', "", html)
    html = re.sub(r"</head>\s*<body>\s*", "", html, flags=re.I)
    html = re.sub(r"\s*</body>\s*</html>\s*$", "\n", html, flags=re.I)

    if "<!doctype" in html.lower() or "<body" in html.lower():
        raise SystemExit("document shell survived the strip")

    OUT.write_text(html)
    print(f"wrote {OUT} ({len(html):,} bytes, {n} scripts inlined)")


if __name__ == "__main__":
    main()
