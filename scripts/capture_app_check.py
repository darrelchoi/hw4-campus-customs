"""Problem 11: drive the live site with Playwright and save screenshots for output/app_check.html.

Needs both servers running (backend :8000, frontend :5173). Run from the hw4 folder:
    .venv/bin/pip install playwright        # dev-only tool, not needed to run the site
    .venv/bin/python scripts/capture_app_check.py

Writes output/app_check_images/*.png and output/app_check_images/results.json
(chat replies + the matching database rows, read-only).
"""

import json
import os
import sqlite3
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "app_check_images"
DB = ROOT / "data" / "campus_customs.db"
SITE = "http://localhost:5173"
# Account for the logged-in (bonus) check. Defaults to the seed test user that ships with the course DB.
LOGIN = {
    "email": os.getenv("APP_CHECK_EMAIL", "test@campuscustoms.yale.edu"),
    "password": os.getenv("APP_CHECK_PASSWORD", "password"),
}

OUT.mkdir(parents=True, exist_ok=True)
results: dict = {"captured_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def db_rows(sql: str, params=()) -> list[dict]:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def open_chat(page: Page) -> None:
    if not page.locator(".chat-panel").is_visible():
        page.click(".chat-launcher")
    page.wait_for_selector(".chat-form input")


def ask(page: Page, question: str, step_shot: str | None = None, min_steps: int = 3) -> str:
    """Type a question, optionally screenshot the live progress steps, and return the final reply text."""
    open_chat(page)
    before = page.locator(".bubble-group").count()
    page.fill(".chat-form input", question)
    page.click(".chat-form button[type=submit]")
    if step_shot:
        page.wait_for_function(
            f"document.querySelectorAll('.chat-steps .step').length >= {min_steps}", timeout=90_000
        )
        page.screenshot(path=OUT / step_shot)
        results[step_shot] = page.locator(".chat-steps").inner_text()
    page.wait_for_function(
        f"!document.querySelector('.chat-steps') && document.querySelectorAll('.bubble-group').length > {before}",
        timeout=120_000,
    )
    page.wait_for_timeout(900)  # let cards/grid animations settle
    return page.locator(".bubble-group").last.locator(".bubble").inner_text()


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
        page = ctx.new_page()

        # ---------- 1. Honest stock + price from the database ----------
        pid = "crew-left-chest-hoodie"
        page.goto(f"{SITE}/products/{pid}")
        page.wait_for_selector(".size-grid")
        q1 = "How many Crew Left Chest Hoodies do you have in each size, and what's the price?"
        results["check1_question"] = q1
        results["check1_reply"] = ask(page, q1)
        page.screenshot(path=OUT / "inventory_chat.png")
        page.click(".chat-close")
        page.wait_for_timeout(300)
        page.locator(".detail").scroll_into_view_if_needed()
        page.screenshot(path=OUT / "inventory_product_page.png")
        results["check1_db"] = db_rows(
            """SELECT c.name, c.price, i.size, i.quantity FROM catalogue c JOIN inventory i USING (product_id)
               WHERE c.product_id = ? ORDER BY CASE i.size WHEN 'XS' THEN 0 WHEN 'S' THEN 1 WHEN 'M' THEN 2
               WHEN 'L' THEN 3 WHEN 'XL' THEN 4 ELSE 5 END""",
            (pid,),
        )

        # ---------- 2. Category question -> dynamic cards on the page ----------
        page.goto(f"{SITE}/")
        page.wait_for_selector(".hero")
        q2 = "What hoodies do you have?"
        results["check2_question"] = q2
        results["check2_reply"] = ask(page, q2)
        page.wait_for_selector(".chat-results .card")
        page.screenshot(path=OUT / "hoodies_chat_and_cards.png")
        page.click(".chat-close")
        page.locator(".chat-results").scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / "hoodies_cards_grid.png")
        results["check2_grid_title"] = page.locator(".chat-results-title").inner_text()
        results["check2_grid_meta"] = page.locator(".chat-results-meta").inner_text()
        results["check2_card_count"] = page.locator(".chat-results .card").count()
        results["check2_first_cards"] = page.locator(".chat-results .card-title").all_inner_texts()[:4]
        second = page.locator(".chat-results .card").nth(1)
        results["check2_clicked"] = second.locator(".card-title").inner_text()
        second.click()
        page.wait_for_selector(".detail-info h1")
        page.wait_for_timeout(600)
        page.screenshot(path=OUT / "hoodies_card_detail.png")
        results["check2_detail_url"] = page.url
        results["check2_db"] = db_rows(
            """SELECT COUNT(*) AS matches, MIN(price) AS min_price, MAX(price) AS max_price FROM catalogue
               WHERE lower(name||garment_type||description||colors||search_tags) LIKE '%hoodie%'"""
        )

        # ---------- 3. Usability feature (Problem 9): live progress steps while the agent works ----------
        pid3 = "ice-hockey-left-chest-hoodie"
        page.goto(f"{SITE}/products/{pid3}")
        page.wait_for_selector(".size-grid")
        q3 = "Is this in stock in XXL, and how much is it?"
        results["check3_question"] = q3
        results["check3_reply"] = ask(page, q3, step_shot="streaming_steps.png", min_steps=3)
        page.screenshot(path=OUT / "streaming_final.png")
        results["check3_db"] = db_rows(
            "SELECT c.name, c.price, i.size, i.quantity FROM catalogue c JOIN inventory i USING (product_id) "
            "WHERE c.product_id = ? AND i.size = 'XXL'",
            (pid3,),
        )

        # ---------- Bonus (Problem 9): restock alert for a sold-out size, logged in ----------
        page.request.post(f"{SITE}/api/auth/login", data=LOGIN)
        page.goto(f"{SITE}/products/{pid3}")
        page.wait_for_selector(".size-grid")
        page.wait_for_timeout(800)  # let saved history + alerts load
        xl = page.locator(".size", has=page.locator(".size-name", has_text="XL")).filter(has_not_text="XXL").first
        xl.locator("button.size-alert").click()  # "Notify me" pre-fills the chat
        page.wait_for_timeout(300)
        results["bonus_question"] = page.input_value(".chat-form input")
        before = page.locator(".bubble-group").count()
        page.click(".chat-form button[type=submit]")
        page.wait_for_function(
            f"!document.querySelector('.chat-steps') && document.querySelectorAll('.bubble-group').length > {before}",
            timeout=120_000,
        )
        page.wait_for_timeout(1200)
        results["bonus_reply"] = page.locator(".bubble-group").last.locator(".bubble").inner_text()
        results["bonus_chip"] = page.locator(".bubble-group").last.locator(".alert-chip").all_inner_texts()
        page.screenshot(path=OUT / "restock_alert.png")
        results["bonus_tile"] = xl.inner_text()
        results["bonus_db"] = db_rows(
            """SELECT a.product_id, a.size, a.created_at, i.quantity AS current_stock FROM restock_alerts a
               JOIN users u ON u.id = a.user_id JOIN inventory i ON i.product_id = a.product_id AND i.size = a.size
               WHERE u.email = ? AND a.product_id = ? AND a.size = 'XL'""",
            (LOGIN["email"], pid3),
        )

        browser.close()

    (OUT / "results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
