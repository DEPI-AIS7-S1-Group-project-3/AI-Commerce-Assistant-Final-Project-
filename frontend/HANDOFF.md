# HANDOFF — Dalil (دليل) Frontend

> Read this file FIRST, then AGENTS.md. Written for any AI agent (Claude, Codex, other) or human continuing this work.
> Last updated: 2026-11-04. Status: IN PROGRESS (see "Progress log" at the bottom, it is the source of truth for what is done).

---

## 1. Who you are working with

- **User: Esraa**, AI Engineering student at Tanta University, DEPI graduation project, team of 5.
- **Her sprint 1 task (with one teammate): the frontend.** The teammate knows more frontend; the plan is that Esraa builds the first version, deploys it, then the teammate fixes and finishes it. So code must be **clean, conventional and easy for someone else to take over**.
- Esraa wants a **mentor + hands-on partner**. Working style she asked for in the project instructions:
  - Be direct, practical, honest. Challenge bad ideas. Do not just agree.
  - Short, organized explanations. One clear next action at a time.
  - **Tell her what you will run/modify and why BEFORE running commands, installing packages or changing files, then wait for approval.** (She gave a blanket "go" for the initial scaffold described in this file. Anything beyond the scope in section 6 needs a new OK.)
  - Do not invent file paths, APIs or backend details. Say "unverified" when unsure.
  - Do not mark things done without evidence (build passes, screenshot checked).
- She prefers plain, human-sounding explanations, not textbook prose.

## 2. The product

**Dalil (دليل)** = "guide". Tagline: **دليلك لأحسن موبايل ولابتوب**.
An Egyptian electronics marketplace (mobiles, laptops, audio) with an AI shopping assistant planned for Phase 2.

- **Phase 1 (this frontend's real target):** marketplace without AI. Register/login, addresses, browse/search/filter/sort Arabic products, product detail (images, specs, warranty, reviews), cart, checkout (COD + simulated wallet/card), order tracking with timeline, cancel + return requests, verified reviews, policy pages, seller dashboard (products, inventory, orders, sales stats).
- **Phase 2 (UI is needed in sprint 1 per Esraa):** AI chat screens. Mockups are in her PDF (transcribed in `attachment.txt`, not in this repo): Shopping Agent chat (message bubbles, product cards inside replies, quick-suggestion chips, a collapsible developer "trace" panel), Support Agent, Seller Agent, Order Actions Agent (explicit confirm button), Observability dashboard. The backend has NO agents yet, so chat runs on fake scripted responses.
- Out of scope in Phase 1: real payments, shipping integrations, admin dashboard, coupons, notifications.

## 3. Design direction (decided with Esraa, do not drift)

Esraa **rejected** the first direction (yellow `#e6e51e`, Cairo font, emojis, Egyptian slang copy). Reasons, in her words: she dislikes the colors and the font, hates "AI-looking" emojis everywhere, and does not want slang like "باشا". She wants it **sophisticated: not too formal, but not slang**. She also wants **bold, non-basic, nice Arabic fonts** and an **AI chat that is not "the basic thing"**.

**Chosen: Direction A "Ink and sand".**

| Token | Value | Use |
|---|---|---|
| paper | `#FAF8F4` | page background |
| surface | `#FFFFFF` | cards |
| sand | `#F1EDE4` | recessed areas, chips |
| ink | `#14161A` | text, primary dark buttons |
| ink-soft | `#4B4F57` | secondary text |
| line | `#E2DDD1` | borders (thin, 1px) |
| green | `#1F6F5B` | the ONE accent: links, primary action, active states |
| green-deep | `#164F41` | hover |
| green-tint | `#E3EFEA` | selected/soft badge background |
| danger | `#B3261E` | errors, out-of-stock |
| warn | `#A15C00` | low stock |

Rules:
- Restrained: lots of whitespace, thin borders, **small radii (6–10px for controls, 14px max for cards)**, **no drop shadows** except a very light one on popovers. No gradients on UI. No pill-everything.
- One accent color only (green). Do not add a second brand color.
- **NO EMOJIS anywhere in the UI or the mock copy.** Not in headlines, buttons, chips or chat. Use simple line icons (lucide-react) sparingly.
- Dark surfaces are allowed ONLY for the developer trace panel inside the AI chat (see section 7).

**Fonts (all via npm `@fontsource/*`, self-hosted, no CDN):**
- Display / headings: **Reem Kufi** (700). Geometric Kufi, architectural, bold, distinctive.
- Body / UI: **Readex Pro** (400/500/600). Modern, readable, not the usual Cairo/Tajawal/Plex look.
- Mono (developer panel only): **IBM Plex Mono**.
- If a font file fails to render a glyph, check the `@fontsource` subset import includes `arabic`. Swapping fonts is a one-line change in `src/index.css` (`--font-display`, `--font-body`).
- **Letter-spacing must be 0 for Arabic.** Negative tracking breaks Arabic letter joining. Never add `tracking-tight` etc. to Arabic text.
- Headlines use weight 700. Avoid light weights for Arabic.

**Tone of copy (Arabic):** clear modern standard-leaning Arabic, calm and confident, a little warm. Short sentences. No slang, no "باشا", no exclamation marks overload, no marketing hype.
- Good: `ابحث، قارن، واشترِ بثقة` / `أضف إلى السلة` / `متاح في المخزون` / `يتبقى 3 قطع`
- Bad: `عندنا لقطة ليك يا باشا!` / `يلا بينا نشتري` / anything with emoji.
- Prices: `23,499 ج.م` with Western digits.
- Dates and numbers: Western digits everywhere.

**The AI chat should feel considered, not like a default chatbot:**
- Not a bubble-gradient "chat app". Think editorial: assistant replies are plain text blocks on paper with a thin rule, user messages are compact ink-colored blocks.
- Product recommendations render as **a comparison table / ranked rows with a reason line** (as in the PDF: badge, specs, price, stock, seller, add to cart), not as a carousel of generic cards.
- Visible, honest states: "checking stock", confidence indicator, "I am not sure, transferring to a human" state, sources list with section names (from the Support Agent mockup).
- Quick-suggestion chips are text buttons with a thin border, not colorful pills.
- Developer trace panel: dark, monospace, step list with latency per step (Input Guardrail, Supervisor, tools, Output Guardrail). Collapsible, off by default.
- Order Actions: explicit **confirmation card with a real button** (identity, eligibility, action, refund summary, "this cannot be undone"). Execution is never triggered by typing "yes".

## 4. Backend contract (VERIFIED from the repo audit dated 2026-11-04, branch `main`)

Backend: FastAPI + PostgreSQL 16 + SQLAlchemy 2 (sync) + Alembic. Base URL default `http://localhost:8000`. CORS allows `http://localhost:5173` (Vite default) via `.env`. JWT bearer auth. Errors use a unified body: **`{ "code": string, "message": string, "details": ... }`**. Every response carries `X-Request-ID`.

**Implemented endpoints (frontend can call these for real):**

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | `{status, version}` |
| POST | `/auth/register` | body `{full_name, email, phone, password, role:"customer"}`; phone must match `^01[0125][0-9]{8}$`; password 8–128 chars with letters AND digits; 409 `email_taken`; sellers cannot self-register (400 `role_not_allowed`) |
| POST | `/auth/login` | `{email, password}` -> `{access_token, token_type:"bearer"}`; 401 `invalid_credentials` |
| GET | `/auth/me` | `{id, role, full_name, email, phone}` |
| GET | `/addresses` | list, default first |
| POST | `/addresses` | `{label?, recipient_name, phone, governorate, city, street_address, is_default?}`; first address becomes default automatically |
| PUT | `/addresses/{id}` | same body |
| POST | `/addresses/{id}/default` | |
| DELETE | `/addresses/{id}` | 204; deleting the default promotes the newest remaining |
| GET | `/cart` | `{items: [...], subtotal_egp}`; each item has `available` flag; unavailable lines are excluded from subtotal |
| POST | `/cart/items` | `{product_id, qty 1..100}`; 400 `insufficient_stock`; 404 `product_not_found` |
| PUT | `/cart/items/{product_id}` | `{qty}` |
| DELETE | `/cart/items/{product_id}` | |
| DELETE | `/cart` | clears |
| POST | `/orders` | checkout: `{address_id, payment_method: "cod"|"wallet"|"card"}` -> 201 `{checkout_group_id, orders: [...]}`; orders are split per seller; 409 `checkout_unavailable` with details of bad items; 400 `cart_empty` |
| GET | `/orders` | list (no pagination) |
| GET | `/orders/{id}` | detail + `timeline` |
| POST | `/orders/{id}/cancel` | only `pending`/`confirmed`; 409 codes `already_shipped`, `already_delivered`, `already_cancelled`, `already_returned` |
| POST | `/orders/{id}/items/{item_id}/return` | `{reason_code, reason_text?}`; 409 codes `not_delivered`, `not_returnable`, `return_exists`, `window_expired`; window is 14 days from delivery |

Enums (from backend `core/enums.py`):
- Order status: `pending, confirmed, shipped, out_for_delivery, delivered, cancelled, return_requested, returned`
- Payment method: `cod, wallet, card`; payment status: `pending, paid, failed, refunded`
- Return reasons: `defective, not_as_described, changed_mind, wrong_item, damaged_in_shipping, other`
- Return status: `requested, approved, rejected, received, refunded`
- Category `spec_kind`: `mobile, laptop, audio`

Business rules the UI must reflect: shipping fee is flat 60 EGP, free when seller subtotal >= 5000 EGP; delivery expected in 3 days; product `is_returnable` flag; stock is deducted at checkout and restored on cancel.

**NOT implemented in the backend yet (no endpoints exist):** products list/detail, search/filters, categories, reviews, policies, ALL seller endpoints (orders, status updates, product/inventory CRUD, stats), pagination, product images upload. No products are seeded either.
=> The frontend uses **mock data for these** behind `src/api/*`. The shapes of the mocked endpoints (e.g. `GET /products?q=&category=&brand=&min_price=&max_price=&in_stock=&sort=`) are **PROPOSALS, not agreed with the backend teammate**. Esraa must confirm them with whoever owns the backend before swapping `USE_MOCK` off.

**UNVERIFIED details (check backend `schemas/*.py` or `/docs` OpenAPI before relying on them):**
- Exact fields of `CartItemOut`, `OrderOut`, `OrderDetailOut`, `TimelineEntry`. Current TS types for these are best guesses; marked with `// UNVERIFIED` comments.
- Numeric fields (`price_egp`, `subtotal_egp`, ...) are Pydantic `Decimal`; FastAPI usually serializes Decimal as a **string** in JSON. Confirm and parse with `Number()` in the API layer if so.
- Conflict to raise: the PDF mockup brand name is "سوقنا"; we renamed to **Dalil** (Esraa's choice). Confirm the team agrees.
- The mockup nav (shopping / support / order actions / seller dashboard / observability) is a Phase 2 demo layout, not the Phase 1 page list.

## 5. Tech stack and conventions

- Vite + React 18 + TypeScript (strict) + Tailwind CSS v3 + React Router v6 + TanStack Query v5 + lucide-react.
- RTL: `<html lang="ar" dir="rtl">`. Use Tailwind **logical** utilities (`ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`, `text-start`). Never `ml-/mr-/left-/right-` for layout.
- All server access goes through `src/api/*.ts` functions wrapped by TanStack Query hooks in `src/hooks/`. **Components never import mock data directly.**
- `VITE_USE_MOCK` (default `true`) and `VITE_API_URL` (default `http://localhost:8000`) in `.env.example`.
- Folder layout: `src/{api,components,hooks,lib,pages,types}`; shared UI in `src/components/ui`.
- No Supabase, no BaaS, no extra state library. Cart is React context + localStorage while logged out/mock, to be replaced by `/cart` endpoints after auth is built.
- Keep files small. No giant components.

## 6. Scope of the first batch (what was approved)

1. Scaffold project + tokens + fonts + RTL.
2. Types + 12 mock products (4 mobiles, 4 laptops, 4 audio) + `api/products.ts` + cart context.
3. Navbar, footer (policy links), Home, Products listing (filters, sort, search, skeletons, empty state, mobile filter drawer), ProductCard.
Not in batch 1: product detail, cart page, checkout, auth, orders, seller dashboard, chat, policy pages.

## 7. Roadmap after batch 1 (suggested order, one step at a time with Esraa)

1. Product detail page (gallery, specs from JSONB, warranty, stock, reviews mock).
2. Cart page (qty change, unavailable lines, shipping fee rule, subtotal).
3. Auth pages (register with phone/password validation matching backend, login, token storage, protected routes). Switch cart to real `/cart` when logged in.
4. Addresses + checkout (real `/addresses`, `/orders`, show `checkout_unavailable` details).
5. Orders list + order detail with status timeline + cancel + return request (real endpoints; map 409 codes to Arabic messages).
6. Policy pages (shipping, returns, warranty, cancellation), static content for now.
7. Seller dashboard (mock): KPI cards, sales chart, product/inventory table, orders table with status update.
8. AI chat: Shopping Agent first (scripted fake responses, comparison-table recommendations, chips, collapsible dark trace panel). Support / Seller / Order Actions are variations of the same chat shell.
9. Deploy (Vercel/Netlify static) with `VITE_USE_MOCK=true` so the teammate can review without the backend.
10. Swap mock to real endpoints per module as the backend ships them; update this file.

## 8. How to run

```bash
npm install
cp .env.example .env     # optional, defaults work
npm run dev              # http://localhost:5173
npm run build            # type-check + production build
```

## 9. Rules for the next agent

- Read this file and AGENTS.md before touching anything. Then read the Progress log below.
- Continue from the first unchecked item. Do not redo finished work or rewrite working components.
- Update the Progress log at the END of every batch, and BEFORE you run low on budget. If you are close to your limit: stop building, finish the file you are in so the project still compiles, update the log with exact state and the next step, then tell Esraa.
- Verify with `npm run build` before claiming a batch is done.
- Do not add emojis, slang copy, new accent colors, or extra fonts. Do not use negative letter-spacing on Arabic.
- Flag assumptions about the backend instead of silently choosing.

---

## Progress log (source of truth)

- [x] HANDOFF.md and AGENTS.md written (2026-11-04)
- [x] Scaffold: config files, fonts, tokens, RTL index.html, npm install (all font CSS imports verified to exist)
- [x] Types, mock data (12 products), `api/products.ts`, hooks (`useProducts`, `useCart`) written (not yet compiled)
- [x] Layout (Navbar, Footer, Logo), Home, Products listing (URL-synced filters, sort, search, skeletons, empty/error states, mobile filter drawer), ProductCard, ProductImage (category-icon placeholder)
- [x] `npm run build` passes (tsc + vite, 2026-11-04)
- [x] Visually checked with headless Chrome: home (desktop 1280px) and listing (desktop + mobile 390px). RTL, fonts and layout look correct.
- [x] Zip delivered to Esraa

**Current state (end of batch 1):** Batch 1 is COMPLETE and builds. Routes that exist: `/` (home), `/products` (listing, also accepts `?q=&category=&brand=&min_price=&max_price=&in_stock=1&sort=`), `*` (not found). Cart is local (context + localStorage).

**Next step (start here): batch 2 = Product detail page `/products/:id`.** Links to it already exist in `ProductCard`. Use `useProduct(id)`, render specs from the `specs` JSON (labels in Arabic per `spec_kind`: laptop/mobile/audio), warranty months, stock state, returnable flag, add-to-cart with quantity, seller name, and a mock reviews block. Then cart page, then auth (see section 7 roadmap).

**Known issues / not done yet (be aware, do not assume these work):**
1. **Mobile navbar hides search and the login button** (`hidden sm:block` / `hidden sm:inline-flex`). On phones there is no way to search or log in. Fix in batch 2: add a compact search row under the navbar or a menu button.
2. Dead links on purpose (pages not built): `/products/:id`, `/cart`, `/login`, `/policies/*` -> show the NotFound page for now.
3. Mock products have no images (category icon placeholder). Real image URLs will come from the backend `product_images` table once product endpoints exist.
4. The mock product/category/brand API shapes are PROPOSALS, not agreed with the backend owner (section 4).
5. Filtering/sorting runs client-side in the mock only. The real backend will do it server-side (pg_trgm search exists in the DB but no endpoint).
6. No automated tests yet. Verification so far = type-check + build + manual screenshots.
7. Reem Kufi is used for headings only. Product card titles deliberately use the body font (Readex Pro) because Kufi is too decorative for long titles mixed with Latin model names. Keep it that way.
8. The AI chat UI is not started. Design notes for it are in section 3.
