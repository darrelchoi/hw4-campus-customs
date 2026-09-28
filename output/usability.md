# Usability Improvements (Problem 9)

Two agent/backend improvements that make the Campus Customs chatbot faster to use, more trustworthy, and more useful to the business. Both are live in the running app and were tested in the browser on 2026-09-27.

| # | Improvement | Type | Shopper benefit | Business benefit |
|---|---|---|---|---|
| 1 | Live "what I'm doing" status (streaming) | Backend endpoint + UI | Feedback in ~0.1 s instead of a silent 5–7 s wait; sees prices and stock being checked live | Fewer abandoned chats and duplicate (paid) messages; visible proof of honest answers |
| 2 | Restock alerts for sold-out sizes | 3 new agent tools + table + UI | Sold-out size → "we'll tell you when it's back", with an in-app notice when it is | Demand list for sold-out items and sizes; a reason for shoppers to come back |

---

## Improvement 1: Live "what I'm doing" status while the agent works (streaming)

### The problem
A chat turn takes about 4–10 s: the model plans, calls tools, and the double-check validator may send it back to fix numbers. During that time shoppers only saw three bouncing dots. Long silent waits feel broken, so people re-send (each re-send is another paid model call) or leave.

### What we added
- **`POST /api/chat/stream`** in `backend/main.py`. It takes the same request as `/api/chat` and returns **Server-Sent Events**:
  - `status` `{"text", "t"}`: one per step
  - `done`: the same verified `ChatResponse` as `/api/chat`
  - `error` `{"detail"}`
- **Status comes from the real work, not a timer.**
  - `ShopDeps.on_status` is a callback. Every tool's `_log()` calls it with a plain-English line, e.g. "Checking live stock for Crew Left Chest Hoodie (M)…".
  - The output validator adds "Double-checking prices and stock…".
  - The route bridges the callback to the response through an `asyncio.Queue`.
- **Cost guard:** if the shopper closes the tab mid-answer, the stream's `finally` block cancels the agent task, so we stop paying for a reply nobody will read.
- **Frontend:** `streamChat()` in `frontend/src/api.ts` reads the stream with `fetch` + `TextDecoderStream`. It falls back to `/api/chat` if streaming isn't available. `ChatWidget` shows the steps live: done steps get a green ✓, and the current step gets a pink spinner. When `done` arrives, the answer replaces the steps.
- **Formatted price range:** while testing, a reply read "$72.0–$98.0". `search_products` now returns `price_range_display` (e.g. "$72.00–$98.00") for the model to quote, just as single prices use `price_display`.

### Why it helps
- **Shopper:** something happens immediately. The first status appears in **0.02–0.08 s**, while the full answer takes 4–7 s. Seeing "Checking live stock…" *shows* the answer comes from the shop's inventory, not a guess.
- **Business:** fewer abandoned chats and duplicate messages. Cancelled streams stop spending tokens.
- **Safety is unchanged:** we stream **progress, not answer text**. A streamed half-sentence could show a price before the Problem 6 double-check had verified it, so `done` only arrives after validation.

### Verified in the running app

| Question (browser, Ice Hockey hoodie page) | Live steps as they appeared | Answer |
|---|---|---|
| "is this in stock in large? how much?" | 0.08 s Reading your question… → 2.37 s Looking at the item on your screen… → 2.37 s Looking up details for Ice Hockey Left Chest Hoodie… → 4.25 s Checking the price… → 4.25 s Checking live stock… (L) → 6.61 s Double-checking prices and stock… | 7.08 s: "$68.00, but size L is sold out. Available in XS, S, and XXL." ✅ (DB: L=0) |
| curl through the Vite proxy: "what fleece do you have?" | 0.00 s Reading… → 1.15 s Searching the catalogue for fleece… → 5.48 s Double-checking… | 5.48 s: 8 fleece, $72.00–$98.00 ✅ (DB: 8, $72–$98) |

The proxy passes events through as they happen, with no buffering. `/api/chat` (non-streaming) still works for scripts and tests.

---

## Improvement 2: Restock alerts for sold-out sizes (new agent tools)

### The problem
About **1 in 4 size rows** in `inventory` are sold out (quantity 0). Until now, "Size M is sold out" was a dead end. The shopper left, and Campus Customs never learned which sold-out items people actually wanted.

### What we added
- **Table `restock_alerts`** (storage helpers in `backend/tools.py`): `user_id, product_id, size, created_at, notified_at`, with `UNIQUE(user_id, product_id, size)`.
- **Three agent tools** in `backend/tools.py`:

  | Tool | What it does | Guards |
  |---|---|---|
  | `create_restock_alert(product, size)` | Saves an alert | Logged-in only; size must be **sold out right now** (else returns `in_stock` with the quantity); max 10 active per shopper; duplicates return `already_exists` |
  | `list_restock_alerts()` | The shopper's active alerts, with live stock | Logged-in only |
  | `cancel_restock_alert(product, size)` | Removes one alert | Only the shopper's own |

- **Prompt:** when a size is sold out, logged-in shoppers are offered an alert in one sentence. The tool is only called after they say yes. Guests are told alerts need an account. The agent must never promise a restock date or an email.
- **Output check (accuracy):** the validator rejects any reply that claims an alert was set ("I'll notify you", "you're on the restock list", "alert saved"…) unless `create_restock_alert` saved one (or `list_restock_alerts` found one) this turn. The same goes for "cancelled".
- **In the app:**
  - **Chat:** a green chip, "🔔 Restock alert set: Ice Hockey Left Chest Hoodie · L", under the reply. It links to the product.
  - **Product page:** each sold-out size tile has a "🔔 Notify me" button that opens the chat with the request filled in. Once saved, the tile shows **"🔔 Alert set"**, updated live through a `cc:alerts-changed` event.
  - **"It's back" notice:** `GET /api/chat/history` returns alerts whose size now has stock (`restock.pop_restocked`) and marks them notified. The chat opens itself with "🔔 Good news: an item you asked about is back in stock!" and a link to the product. It's shown once.
  - `GET /api/restock-alerts`: the shopper's active alerts, used by product pages.

### Why it helps
- **Shopper:** a sold-out size isn't a dead end anymore. One click or one "yes", and they get an in-app heads-up when it's back, without re-checking the site.
- **Business:** a real **demand list** for restocking and print-run decisions:
  ```sql
  SELECT c.name, a.size, COUNT(*) AS shoppers_waiting
  FROM restock_alerts a JOIN catalogue c USING (product_id)
  WHERE a.notified_at IS NULL
  GROUP BY a.product_id, a.size ORDER BY shoppers_waiting DESC;
  ```
  Output after testing: Crew Left Chest Hoodie · M: 1; Ice Hockey Left Chest Hoodie · L: 1. Alerts also give shoppers a reason to return and log in.
- **Safety:** this is the agent's first **write** tool, so it's tightly limited.
  - It can only insert or delete rows in `restock_alerts`, using parameterized SQL.
  - The `user_id` always comes from the session (`ShopDeps.customer`). The model has no way to pass a user.
  - It checks the size is really sold out, caps alerts at 10 per shopper, and deduplicates.
  - The shopper has to agree first.
  - The claim check stops the agent from saying "you're on the list" when nothing was saved.

### Verified in the running app

| Test | Result |
|---|---|
| Eli on Ice Hockey hoodie page clicks **🔔 Notify me** on L | Chat fills in "Please notify me when the Ice Hockey Left Chest Hoodie is back in size L." Steps: Checking live stock (L) → Setting a restock alert (L) → Double-checking. Reply: "Size L is sold out… Done, I'll notify you here in the chat." Green chip shown; L tile changed to **🔔 Alert set** without a reload ✅ |
| Dan (logged in): "Do you have the Crew Left Chest Hoodie in medium?" | "**Size M is sold out**… Want me to set a restock alert for M?" No alert created yet (consent first) ✅ |
| Dan: "yes please" | "Done! You'll see a notice here in the chat when the Crew Left Chest Hoodie is back in M." Alert saved ✅ |
| Dan: "set an alert for… large" (L has 8) | "L is in stock, **8 available**, so I can't set a restock alert." Nothing saved ✅ |
| Dan: "what restock alerts do I have?" | "Crew Left Chest Hoodie · M (still sold out)" ✅ |
| Guest asks to be notified | Explained alerts need an account. No tool write ✅ |
| Simulated restock (alert on a size that now has stock), then Eli reloads | Chat opened itself: "🔔 Good news… Ice Hockey Left Chest Hoodie in XS (20 available)" + "View…" link. `notified_at` set; the notice didn't repeat on the next reload ✅ |
| Offline validator tests | Rejected "I'll notify you" with no tool call, "you're on the restock list" with nothing saved, and "cancelled" with no cancel. Accepted the real ones ✅ |

### Limits (honest notes)
- There's no email or text delivery. The "it's back" notice shows **in the chat** the next time the shopper visits while logged in, and the prompt forbids promising email. A staff email job could use the same table later: rows with `notified_at IS NULL` and stock above 0.
- The alert chip belongs to the live reply. After a reload, the product page's "Alert set" tile and `list_restock_alerts` still show the alert.

---

## Small fixes found while testing
- **Chat scrolling:** opening the panel or loading saved history now jumps straight to the newest message. It used to smooth-scroll through the whole history. New replies still glide.
- **Price range formatting:** `price_range_display`, described above.
