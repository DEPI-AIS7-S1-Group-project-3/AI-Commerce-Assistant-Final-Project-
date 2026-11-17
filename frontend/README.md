# Dokkan Tech (دكان تك) - Frontend

Web app for the Egyptian AI Commerce Marketplace (DEPI graduation project): an Arabic/English
electronics shop for customers and sellers, with an AI shopping assistant screen.

## Stack

- Vite, React 18, TypeScript (strict)
- Tailwind CSS v3 (design tokens in `src/index.css`, dark default + light theme)
- React Router v6, TanStack Query v5, lucide-react icons
- Self-hosted fonts via `@fontsource`: Kufam (Arabic display), Changa (Latin display),
  Readex Pro (body), IBM Plex Mono (assistant trace)

## Run locally

Start the backend first (see the root `README.md`), then:

```bash
npm install
cp .env.example .env     # then set VITE_USE_MOCK=false to use the real backend
npm run dev              # http://localhost:5173
npm run build            # type-check + production build (run before every PR)
```

| Variable | Default | Meaning |
|---|---|---|
| `VITE_USE_MOCK` | `true` | `true`: built-in mock catalog and login, no backend needed. `false`: real FastAPI backend |
| `VITE_API_URL` | `http://localhost:8000` | Backend base URL |

Cart sync, checkout, addresses, orders, policies and the seller pages need the real backend.

Demo logins (password `Demo@12345`, from the seed): customers `customer01..12@example.com`,
sellers `seller1..4@example.com`. Sellers land on `/seller` after logging in.

## Pages

| Route | What it does |
|---|---|
| `/` | Home |
| `/products` | Search, filters (category, brand, price, in stock), sort |
| `/products/:id` | Gallery, specs table, policy badges, reviews, similar products, add to cart |
| `/cart` | Server cart when logged in (guest cart is merged on login), one shipping line + free-shipping hints |
| `/checkout` | Wizard: address > payment (COD / simulated wallet or card) > review, one package per seller |
| `/orders`, `/orders/:id` | Purchases grouped by checkout, status timeline, cancel per package, return requests |
| `/addresses` | Address book (27 governorates) |
| `/policies/:slug` | Shipping, returns, warranty, cancellation (Arabic text, tabs + contents) |
| `/assistant` | Chat-app layout; scripted replies over the real catalog until an agent runtime exists |
| `/seller`, `/seller/orders`, `/seller/products` | Seller dashboard (KPIs, daily revenue chart), order status updates, inventory (regular/sale price, stock, hide/show) |

Login-only pages use `RequireAuth` (seller pages also check the role).

## Structure

```
src/
  api/          the only place that calls the backend; converts money strings to numbers
  hooks/        TanStack Query hooks + auth and cart contexts
  pages/        one file per route
  components/   shared UI (Navbar, Logo, ProductCard, AddressForm, MiniMarkdown, seller/, assistant/)
  lib/          i18n, formatting, shipping rule, specs labels, orders helpers, governorates
  types/        shared TypeScript types (match the backend schemas)
```

## Conventions

- All visible text goes through `t()` from `src/lib/i18n.tsx`; never hardcode Arabic or English.
  Numbers inside text use `fill(t("key"), { n })`.
- Arabic product titles and seller names inside English text are wrapped in `<bdi>`.
- Logical Tailwind classes only (`ms-`, `ps-`, `start-`), never `ml-`/`mr-`/`left-`/`right-`.
- Server access only via `src/api/*` and hooks in `src/hooks/`. Components never call `fetch`.
- Brand names are always shown in English; product titles use `title_en` in English mode, else Arabic.
- Files with JSX must be `.tsx`. No emojis in the UI.
- The colour token named `green` is actually blue (legacy name).
