# HANDOFF - Dokkan Tech (دكان تك) Frontend

> Read this file FIRST, then AGENTS.md. For any AI agent or human continuing this work.
> Last updated: 2026-11-04 (evening). The "Progress log" at the bottom is the source of truth.
> This file SUPERSEDES the old section 3 (design) of the previous HANDOFF. Where they conflict, this file wins.

---

## 1. Who you are working with

- **Esraa**, AI Engineering student, Tanta University, DEPI graduation project, team of 5.
- Sprint 1 task (with one teammate): the **frontend**. She builds v1 and deploys; the teammate (stronger in frontend) fixes and finishes. Code must be clean, conventional, easy to take over.
- Working style she asked for: mentor + hands-on partner. Direct, honest, challenge bad ideas. Short answers. **One step at a time.** Minimal token usage. Tell her what you will run/change BEFORE doing it.
- She works by pasting files into chat. Agents that cannot see the repo must ask for the exact files, never guess or rewrite blind.
- She wants **only the files that change**, not the whole project again.
- Do not invent paths/APIs/backend details. Say "unverified" when unsure. Do not claim done without evidence.

## 2. Product

**Dokkan Tech (دكان تك)**. Tagline AR: "تكنولوجيا أقرب ليك." / EN: "Your neighborhood tech shop, only smarter." Egyptian electronics marketplace (mobiles, laptops, audio) with an AI shopping assistant.
- Phase 1: marketplace without AI (auth, addresses, browse/search/filter, product detail, cart, checkout COD + simulated wallet/card, orders + timeline, cancel/return, reviews, policy pages, seller dashboard).
- **The AI assistant is a MAIN feature in the UI (Esraa's decision)**, shown first in the navbar. Backend has NO agents, so chat runs on scripted logic over the mock catalog.
- Out of scope Phase 1: real payments, shipping integrations, admin dashboard, coupons, notifications.
- Brand history: PDF mockup "سوقنا" -> "Dalil" (Esraa) -> **Dokkan Tech / دكان تك** (Noura, approved by the team 2026-11-04). Do not rename again without team agreement.
- Frontend ownership: **Noura** took over the frontend from Esraa on 2026-11-04.

## 3. DESIGN (current, decided with Esraa; the first "Ink and sand" direction was rejected)

Dark, high-energy: near-black background, blue and lime accents. Tokens in `tailwind.config.js` (legacy token names kept so components did not need edits):

| Token | Value | Use |
|---|---|---|
| paper | `#030407` | page background |
| surface | `#0D1424` | cards |
| sand | `#070B15` | recessed areas, inputs, footer |
| ink | `#F4F6EE` | main text (cream) |
| ink-soft | `#A9B4CC` | secondary text |
| line | `#1E3A78` | borders |
| neon | `#D4FF24` (deep `#B8E000`) | PRIMARY accent: primary buttons (black text), links, active states, focus ring |
| green (LEGACY NAME) | `#1558C9` (deep `#0F449C`) | **actually BLUE**, secondary accent (user message bubble, dark buttons). Rename to `blue` when the teammate takes over |
| power | `#1558C9` | alias of blue |
| danger / warn | `#FF6B7F` / `#FFB84D` | errors / low stock |

- Buttons: 2px border, `shadow-pop` offset shadow (blue), lime primary with dark text. No emojis anywhere. Lucide icons sparingly.
- **Fonts (npm `@fontsource`, self-hosted):** Lalezar (headings, single weight 400: never use `font-bold` on headings or it fakes bold), Readex Pro (body/UI), IBM Plex Mono (trace panel). Root font-size is **18px** (Esraa wanted bigger text).
- Mango (rtltype.com) was requested but is commercial; Lalezar is the free stand-in. If Esraa has a license, load it as a local font in `index.css`.
- Arabic rules: letter-spacing 0 always, logical Tailwind utilities only (`ms- me- ps- pe- start- end- text-start`), never `ml/mr/left/right` for layout.
- Copy tone Arabic: clear, calm, not slang, no "باشا", Western digits. Prices `23,499 ج.م` (AR) / `EGP 23,499` (EN).
- Rejected earlier (do not revisit): yellow `#e6e51e`, Cairo font, emojis, slang, beige/lime/orange/navy-background experiments.
- Known contrast watch: blue `#1558C9` text on near-black is weak. Use `text-neon` for text/links (already done in Home, Footer, Navbar, cards). Avoid `text-green` for text.

## 4. Backend contract (VERIFIED from repo audit 2026-11-04, branch `main`)

FastAPI + PostgreSQL 16 + SQLAlchemy 2 (sync) + Alembic. Default `http://localhost:8000`. CORS allows `http://localhost:5173`. JWT bearer. Errors: `{ "code", "message", "details" }`. Every response has `X-Request-ID`.

Implemented: `GET /health`; `POST /auth/register` (`{full_name,email,phone,password,role:"customer"}`, phone `^01[0125][0-9]{8}$`, password 8-128 with letters AND digits, 409 `email_taken`, 400 `role_not_allowed`); `POST /auth/login` -> `{access_token, token_type}` (401 `invalid_credentials`); `GET /auth/me`; `/addresses` (GET list default first, POST, PUT `/{id}`, POST `/{id}/default`, DELETE 204); `/cart` (GET `{items, subtotal_egp}` with `available` flag per item, POST `/cart/items` `{product_id, qty 1..100}`, PUT/DELETE `/cart/items/{product_id}`, DELETE `/cart`); `POST /orders` (`{address_id, payment_method}` -> 201 `{checkout_group_id, orders[]}` split per seller; 409 `checkout_unavailable`, 400 `cart_empty`); `GET /orders`, `GET /orders/{id}` (+timeline); `POST /orders/{id}/cancel` (409: already_shipped/delivered/cancelled/returned); `POST /orders/{id}/items/{item_id}/return` (`{reason_code, reason_text?}`; 409: not_delivered, not_returnable, return_exists, window_expired; 14-day window).

Enums: order status `pending, confirmed, shipped, out_for_delivery, delivered, cancelled, return_requested, returned`; payment `cod|wallet|card`; payment status `pending, paid, failed, refunded`; return reasons `defective, not_as_described, changed_mind, wrong_item, damaged_in_shipping, other`; return status `requested, approved, rejected, received, refunded`; spec_kind `mobile, laptop, audio`.
Rules: shipping 60 EGP flat, **free when seller subtotal >= 5000**; delivery in 3 days; stock deducted at checkout, restored on cancel.

**NOT implemented in backend (mocked in frontend):** products list/detail, search/filters, categories, reviews, policies, ALL seller endpoints, pagination, images, chat/agents. No products seeded.
**UNVERIFIED:** exact `CartItemOut/OrderOut/OrderDetailOut/TimelineEntry` fields (marked `// UNVERIFIED`); Decimal fields may serialize as strings (parse with `Number()` in API layer); all mock endpoint shapes (`GET /products?q=&category=&brand=&min_price=&max_price=&in_stock=&sort=`) are PROPOSALS not agreed with the backend owner.

## 5. Stack and conventions

Vite + React 18 + TypeScript strict + Tailwind v3 + React Router v6 + TanStack Query v5 + lucide-react. Alias `@/` = `src/`.
- Server access only through `src/api/*.ts` + hooks in `src/hooks/`. Components never import mock data directly.
- `VITE_USE_MOCK` (default true) and `VITE_API_URL` in `.env.example`.
- Folders: `src/{api,components,hooks,lib,pages,types}`, shared UI in `components/ui`.
- Files with JSX MUST be `.tsx` (a `.ts` rename mistake already broke the dev server once).
- No BaaS, no extra state library. Keep files small.

## 6. i18n (Arabic / English) - how it works

- `src/lib/i18n.tsx`: `I18nProvider`, `useI18n()` -> `{lang, t, toggle}`. Dictionary `dict` keyed by string, each `{ar, en}`. `t("key")` returns the current language; `TKey` type for typed keys. Sets `<html lang dir>` and persists to `localStorage` key `dalil.lang`. Default `ar`.
- `src/components/LanguageSwitch.tsx` is in the navbar.
- **Rule: any visible text must go through `t()`.** Hardcoded Arabic in a component will NOT switch (this was the recurring bug).
- Product/seller/brand/category names: `src/lib/productText.ts` (`productTitle`, `sellerName`, `brandName`, `categoryName`) holds English product titles and seller names keyed by id for the mock; falls back to Arabic. The mock `Product` type still only has `title_ar` and `description_ar`. A real bilingual field needs agreement with the backend owner.
- **Missing dict key to add:** `"stock.out": { ar: "غير متوفر", en: "Out of stock" }` (ProductCard references it via `t("stock.out" as never)`; remove the cast once the key exists).
- Product descriptions (`description_ar`) and spec labels are still Arabic only.

## 7. Auth (mock + real)

- `src/api/auth.ts`: `login`, `register`, `me`, validators `phoneOk/passwordOk/emailOk` (same rules as backend), `ApiError(code)`. With `VITE_USE_MOCK=true`, login accepts any valid email + any password and stores `dalil.token` + `dalil.user`; register skips the server. With mock off it calls `/auth/login`, `/auth/me`, `/auth/register`. **Real path is untested** (needs backend running).
- `src/hooks/useAuth.tsx`: `AuthProvider`, `useAuth()` -> `{user, loading, login, register, logout}`. Wrapped in `main.tsx` (order: I18n > Query > Auth > Cart > Router).
- Pages `LoginPage`, `RegisterPage`; Navbar shows logout with first name when logged in.
- No protected routes yet (add with checkout/orders). Cart is still local (context + localStorage), not yet synced to `/cart` after login.

## 8. AI assistant (route `/assistant`) - no API, local only

- `src/lib/assistantScript.ts`: `scriptedReply(input, products)` keyword/regex logic over the REAL mock catalog: detects category (laptops/mobiles/audio, AR+EN keywords), brand, budget ("under 25000", "25k", Arabic digits), "cheapest". Returns `Reply {text{ar,en}, productIds, reasons, followups, confident}`. Only in-stock products, max 3, ranked by rating or price. `suggestions` = starter prompts. `traceFor` = FAKE step timings (UI says "Simulated").
- `src/lib/chatStore.ts` + `src/hooks/useChats.ts`: chat history in `localStorage` key `dalil.chats.v1` (stores message text and product IDs only; price/stock always read live, replies are bilingual so old chats switch language). Swap for backend chat endpoints later.
- `AssistantPage.tsx`: history sidebar (new/select/delete), messages (assistant = plain text with lime start-border, user = compact blue block), `RecommendationTable.tsx` (ranked rows: reason line, stock, price, add to cart), confidence indicator, suggested follow-up chips, suggested starter prompts, collapsible dark `TracePanel.tsx` (monospace, off by default).
- Not built: Support Agent, Seller Agent, Order Actions Agent (needs explicit confirm-card with a real button, never "type yes"), Observability dashboard. Reuse this chat shell.
- Assistant button is lime (`btn-primary`) and FIRST in the navbar (after the logo).

## 9. Run

```bash
npm install
cp .env.example .env     # optional
npm run dev              # http://localhost:5173
npm run build            # type-check + production build (run before claiming done)
```

## 10. Git

- Repo: https://github.com/DEPI-AIS7-S1-Group-project-3/AI-Commerce-Assistant-Final-Project- ; **never push to `main`**.
- Plan given to Esraa: clone, `git switch -c frontend`, copy project into a `frontend/` folder (excluding `node_modules`, `dist`, `.git`, `.env`), check `git status`, then `git add frontend`, commit, `git push -u origin frontend`. **Status: UNKNOWN, confirm with Esraa whether the push succeeded.** Possible blockers: not a collaborator (permission denied), existing `frontend/` folder.

## 11. Rules for the next agent

- Read this file and AGENTS.md first. Continue from "Next steps". Do not redo finished work or rewrite working components.
- If you cannot see the repo, ask Esraa to paste the specific files; never write blind against files you have not seen.
- Update the Progress log at the END of every batch and BEFORE you run low on budget. If near the limit: finish the file you are in so it compiles, update the log with exact state and next step, tell Esraa.
- Verify with `npm run build`. No emojis, no slang copy, no negative letter-spacing on Arabic, no `font-bold` on Lalezar headings, no new fonts or colors without asking.
- Flag backend assumptions instead of silently choosing.

---

## Progress log (source of truth)

- [x] Batch 1 (previous agent): scaffold, types, 12 mock products, `api/products.ts`, cart context, Navbar/Footer/Home/Products listing/ProductCard, build passing.
- [x] FIX blank page: `Layout.tsx` `ScrollToTop` effect returned a value (`useEffect(() => window.scrollTo(0,0), ...)`); now uses a block body.
- [x] Redesign: dark palette (section 3), Lalezar + Readex Pro, 18px root. `tailwind.config.js` + `src/index.css` replaced.
- [x] AR/EN switch: `i18n.tsx`, `LanguageSwitch.tsx`, provider in `main.tsx`. Translated: Navbar, Home, Footer, ProductsPage, ProductCard, AssistantPage, Login, Register.
- [x] `productText.ts` English names for mock products.
- [x] AI assistant (section 8) working locally, history persisted, real products shown.
- [x] Login + Register pages, `useAuth`, mock-mode auth (section 7).
- [ ] Git push to `frontend` branch (see section 10, unconfirmed).

**Current state:** App runs (`npm run dev`). Routes: `/`, `/products`, `/assistant`, `/login`, `/register`, `*`. Cart is local only.

**Next steps (start at the top, one step at a time with Esraa):**
1. **Cart page `/cart`.** NEEDS `src/hooks/useCart.tsx` and `src/api/products.ts` pasted first (not seen by this agent). Qty +/- and remove, unavailable lines excluded from subtotal, shipping rule (60 EGP, free at seller subtotal >= 5000, per seller), subtotal/total, empty state, checkout button (to login if logged out). All text via `t()`.
2. Translate `FilterPanel.tsx` and `src/lib/format.ts` (`stockState` labels, `formatPrice`): needs those files pasted. Add `stock.out` dict key (section 6).
3. Product detail `/products/:id` (gallery placeholder, specs from `specs` by `spec_kind`, warranty, stock, returnable flag, qty + add to cart, mock reviews). Product card links already point here.
4. Mobile navbar: search is hidden below `lg`; add a compact search row or menu. Login button hidden on phones (below `sm`): add to a menu.
5. Switch cart to real `/cart` when logged in; protected routes; addresses + checkout (real `/addresses`, `/orders`, show `checkout_unavailable` details).
6. Orders list + detail + timeline + cancel + return (map 409 codes to AR/EN messages).
7. Policy pages (`/policies/shipping|returns|warranty|cancellation`), footer links currently 404.
8. Seller dashboard (mock): KPIs, sales chart, product/inventory table, orders table with status update.
9. Chat variants: Support (sources list, "transferring to a human" state), Seller, Order Actions (confirm card), Observability.
10. Deploy (Vercel/Netlify static) with `VITE_USE_MOCK=true` so the teammate can review without backend.
11. Swap mock to real endpoints per module as backend ships; rename `green` token to `blue`; confirm mock shapes and bilingual product fields with the backend owner.

**Known issues (do not assume these work):**
1. Hardcoded Arabic still in: FilterPanel, `format.ts`, ProductImage/skeleton aria labels, NotFoundPage, Logo (check), spec labels, product descriptions.
2. `/cart`, `/products/:id`, `/policies/*` are dead links (show NotFound).
3. Mock products have no images (category icon placeholder).
4. Mock API shapes are proposals, not agreed with backend. Filtering/sorting is client-side in the mock.
5. Real-mode auth untested. Token stored in localStorage (fine for a student project; mention to teammate).
6. No automated tests. Verification so far = manual checks + `npm run build` from batch 1; the later batches were checked by Esraa in the browser only, `npm run build` NOT re-run since batch 1. Run it first.
7. Colour contrast of blue text on dark not audited; some components may still use `text-green` (blue) for text.
8. Assistant intent logic is keyword-based and limited (3 categories, brands in catalog, one budget number).
