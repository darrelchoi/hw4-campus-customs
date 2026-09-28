# Design Refresh (Problem 10)

**Goal:** make the site feel like the real Campus Customs storefront and make buying feel rewarding.

**Research (read-only):** homepage and theme stylesheet of https://www.campuscustoms.com. No forms, carts, or contact.

| Their design | What we found |
|---|---|
| Colors | Navy `#0c233f`, light blue `#7ba0c5`, white background, grays `#d3d3d3` and `#606975` |
| Type | **Archivo Narrow**: condensed, often uppercase, used for headings, menus, and buttons. Raleway for body text. |
| Layout | Navy top bar → rotating hero slider → centered light-blue section titles → simple product grid → light-blue footer with navy headings |
| Chat | A navy tab docked at the bottom right |

Darrel chose to **match their palette**, so this app no longer uses black and pink.

## What we changed and why

| Change | Why it helps shoppers stay and buy |
|---|---|
| **Campus Customs palette + Archivo Narrow caps** everywhere (buttons, prices, nav, headings) | It looks like the store people already know and trust. Consistent navy calls to action are easy to spot. |
| **Three-layer header:** navy utility bar (licensed, since 1975, open 7 days), white brand bar with **search + Bag**, navy **category menu** (Hoodies, Crewnecks, T-Shirts…) | Shoppers are one click from any category, search is always visible, and trust facts are on every page |
| **Rotating hero slider** (hoodies / game day / fleece) with staggered text and a product medallion; pauses on hover and stops for reduced-motion users | Motion draws the eye to three buying paths instead of one static banner |
| **Trust strip** under the hero: Made on Broadway · Officially licensed · Real-time stock | Answers "is this legit / in stock?" before the shopper has to ask |
| **Edge-to-edge product photos.** 73 of 102 photos have black backgrounds, so every image now fills its tile instead of sitting on white. | Product photos look professional and consistent, not like pasted squares |
| **Cards:** hover lift + zoom, a navy "View Details" bar slides up, uppercase names, big prices | Clear hierarchy (image → name → price) and an obvious next step |
| **A real buy flow:** pick a size (in-stock sizes only), quantity capped at live stock, **Add to Bag** with a total like "Add to Bag · $136.00" | Removes friction, and the shopper can't add more than exists |
| **Slide-in bag** with an item count badge on the header Bag button, a subtotal, and a gold "Checkout (demo)" button | The bag is always one tap away, and a visible subtotal commits the shopper |
| **Chat restyled** as a navy docked tab with a green "online" dot, white/navy bubbles, and "Minimize chat" | Matches their live chat and reads as a real person-style helper |
| Light-blue **footer** with navy headings, a navy fine-print bar, and 30-day returns noted | Mirrors their footer, and seeing the returns policy lowers purchase anxiety |

## Purchase-moment "casino" feedback (`src/celebrate.ts`)
- **Add to Bag:**
  - A burst of 60 navy/blue/gold confetti pieces from the button.
  - A **"cha-ching"** made with the Web Audio API: a click plus two bell tones, with no audio files.
  - The button flashes green: "✓ Added to Bag!"
  - The Bag badge **pops and wiggles**, and the bag slides open.
- **Checkout:** a full-screen shower of 140 confetti pieces, the cha-ching, and a "Boola Boola, you're all set!" screen.
- **Subtle pull:** a slow shine sweeps across the Add to Bag button. The live-chat dot pulses.

**Why it works:** instant, variable sensory rewards, in the style of slot-machine wins, make buying feel good and train people to repeat it. The bouncing badge keeps the bag top of mind. People value things more once they're "theirs" in a bag (the endowment effect).

## Honest urgency only
- "🔥 **Only 5 left in M.** Real-time stock." appears on a size with 5 or fewer units.
- The **"Only 9 left"** badge appears on cards with 15 or fewer units in total.
- Both come straight from the `inventory` table.

**What we deliberately did *not* add:** fake countdown timers, fake "12 people are viewing this" messages, or pre-checked add-ons. Those are deceptive, they'd contradict the chatbot's "never invent stock" rule, and shoppers who catch them stop trusting the store.

## Guardrails
- A 🔊/🔇 **sound toggle** in the header, saved in `localStorage`.
- `prefers-reduced-motion` turns off confetti, the slider, and animations.
- Checkout says **"demo, no payment taken"** in the bag and on the confirmation, so nothing is ever charged or ordered.

## Checked in the running app (2026-09-27)
- **Add to Bag without a size:** shows "Pick a size first."
- **Basic Hoodie in M (5 in stock):**
  - The urgency line appears.
  - Quantity stops at 5, and the button reads "Add to Bag · $340.00".
  - Clicking it fired 60 confetti pieces. The button switched to "✓ Added to Bag!", the badge popped to 5, and the bag opened: "That's all we have in M", subtotal $340.00.
- **Checkout:** 140 confetti pieces and the demo confirmation. The bag emptied. No console errors.
- **Sound toggle:** switches between on and off, and the setting persists.
- **Low-stock badges:** show only on the three real low-stock tees (9, 13, and 14 units).
- **Mobile (375px):** no sideways overflow, a hamburger menu, the Bag button fits, and cards show two per row.
