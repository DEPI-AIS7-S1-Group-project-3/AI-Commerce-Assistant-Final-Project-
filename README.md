# Dalil (دليل) - Frontend

Frontend for the Egyptian AI Commerce Marketplace (DEPI graduation project).
Arabic/English, RTL/LTR, electronics marketplace with an AI shopping assistant UI.

> Work in progress. Not final. Read `HANDOFF.md` first for the full state, decisions and next steps.

## Stack

- Vite, React 18, TypeScript (strict)
- Tailwind CSS v3
- React Router v6, TanStack Query v5
- lucide-react icons
- Fonts via `@fontsource` (Lalezar, Readex Pro, IBM Plex Mono), self-hosted

## Run locally

```bash
npm install
cp .env.example .env     # optional, defaults work
npm run dev              # http://localhost:5173
npm run build            # type-check + production build
```

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `VITE_USE_MOCK` | `true` | Use mock data (products, auth) instead of the backend |
| `VITE_API_URL` | `http://localhost:8000` | FastAPI backend base URL |

## What works now

- Home, product listing (search, filters, sort), AR/EN switch with RTL/LTR
- AI assistant (`/assistant`): scripted replies over the mock catalog, real product recommendations, saved chat history (localStorage), suggested prompts
- Login and register (mock mode, or real `/auth/*` when `VITE_USE_MOCK=false`)
- Local cart (context + localStorage)

## Not built yet

Cart page, product detail, checkout, orders, policy pages, seller dashboard, Support/Seller/Order Actions chats. See the roadmap in `HANDOFF.md`.

## Backend

FastAPI + PostgreSQL (separate repo/branch). Implemented endpoints: auth, addresses, cart, orders. Products, reviews, policies and seller endpoints do not exist yet, so the frontend mocks them behind `src/api/*`. Mock response shapes are proposals and must be agreed with the backend owner.

## Conventions

- All visible text goes through `t()` from `src/lib/i18n.tsx` (never hardcode Arabic or English in components)
- Server access only via `src/api/*` and hooks in `src/hooks/`
- Logical Tailwind classes only (`ms-`, `ps-`, `start-`), never `ml-`/`mr-`/`left-`/`right-`
- Files with JSX must be `.tsx`
- No emojis in the UI
