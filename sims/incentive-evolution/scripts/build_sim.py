"""Inline the browser engine into the live simulator page.

    python scripts/build_sim.py

The result is a single self-contained file: no network requests, so it works
opened from disk and under a strict content-security policy.
"""

from __future__ import annotations

import sys
from pathlib import Path

TEMPLATE = Path("web/sim_template.html")
ENGINE = Path("web/engine.js")
PLACEHOLDER = "/*__ENGINE__*/"


def main() -> int:
    out_path = Path(sys.argv[1] if len(sys.argv) > 1 else "web/sim.html")

    html = TEMPLATE.read_text()
    if PLACEHOLDER not in html:
        raise ValueError(f"placeholder missing from {TEMPLATE}: {PLACEHOLDER}")

    engine = ENGINE.read_text()
    # The engine is written to work under both node (module.exports) and the
    # browser; that trailing line is meaningless inline and would throw.
    engine = engine.replace(
        'if (typeof module !== "undefined" && module.exports) module.exports = Engine;', ""
    )

    html = html.replace(PLACEHOLDER, engine, 1)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)

    print(f"wrote {out_path} ({len(html) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
