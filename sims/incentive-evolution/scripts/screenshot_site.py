"""Screenshot the built site in both themes, and surface any console errors.

    python scripts/screenshot_site.py

The validator in the dataviz workflow checks colour, not layout — this is the
"render it and look at it" step.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("figures")
PAGE = Path("web/index.html").resolve()


def main() -> int:
    OUT.mkdir(exist_ok=True)
    problems: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in ("light", "dark"):
            page = browser.new_page(
                viewport={"width": 1280, "height": 1000},
                device_scale_factor=2,
                color_scheme=theme,
            )
            page.on("console", lambda msg: (
                problems.append(f"console.{msg.type}: {msg.text}")
                if msg.type in ("error", "warning") else None
            ))
            page.on("pageerror", lambda err: problems.append(f"pageerror: {err}"))

            page.goto(PAGE.as_uri())
            page.wait_for_timeout(700)

            page.screenshot(path=OUT / f"site-{theme}.png", full_page=True)

            # Horizontal overflow is the classic responsive failure.
            overflow = page.evaluate(
                "document.documentElement.scrollWidth - document.documentElement.clientWidth"
            )
            if overflow > 1:
                problems.append(f"{theme}: page scrolls horizontally by {overflow}px")

            page.close()

        # Narrow viewport check.
        page = browser.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2)
        page.goto(PAGE.as_uri())
        page.wait_for_timeout(500)
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        if overflow > 1:
            problems.append(f"mobile: page scrolls horizontally by {overflow}px")
        page.screenshot(path=OUT / "site-mobile.png", full_page=True)
        page.close()

        browser.close()

    for problem in problems:
        print(f"  ! {problem}")
    print(f"{len(problems)} problem(s); screenshots in {OUT}/")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
