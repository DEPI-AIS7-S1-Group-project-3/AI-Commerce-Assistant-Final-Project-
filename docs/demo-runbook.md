# Demo runbook

How to run the full demo on a Windows laptop (PowerShell) with the **real backend** and the real
assistant. Every step is a command you copy. Time: about 10 minutes the first time, 2 minutes after.

## 0. Once per laptop

You need: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, PostgreSQL 16 running on port 5432.

```powershell
git checkout main
git pull
uv sync
cd frontend
npm ci          # NOT "npm install": ci installs exactly the locked versions
cd ..
```

Copy `.env.example` to `.env` in the project root and fill it:

| Key | Value |
|---|---|
| `DATABASE_URL` | already right if your database is `ai_commerce` with user `app` |
| `CORS_ORIGINS` | keep both `localhost:5173` and `127.0.0.1:5173` |
| `LLM_PROVIDERS` | `gemini,groq` (first = primary, the rest = fallback when it fails or hits a limit) |
| `GEMINI_API_KEY`, `GROQ_API_KEY` | put **both**: the free Gemini tier hits 429 often, Groq then answers |
| `ASSISTANT_DEBUG_TRACE` | `false` for the demo |

Copy `frontend/.env.example` to `frontend/.env` and set:

```
VITE_USE_MOCK=false
VITE_API_URL=http://localhost:8000
```

`VITE_USE_MOCK=false` is what connects the site to the real API. With `true` you get fake data and the
assistant is not real.

## 1. Before every demo or rehearsal: reset the data

The cancel flow changes order 10002 for good, so reset first. Stop the API (Ctrl+C) before this.

```powershell
uv run python -m scripts.demo_reset
```

## 2. Check the assistant with the real models (2 minutes)

```powershell
uv run python -m scripts.demo_run --out demo-transcript.md
```

It asks the 16 demo questions below and prints every answer. Read them. This run cancels order 10002,
so **run the reset (step 1) again afterwards**. If you see 429 in the output, add `--pause 4`.

## 3. Start everything (two terminals)

```powershell
# terminal 1, project root
uv run uvicorn ai_commerce_marketplace.api.main:app --port 8000
```

```powershell
# terminal 2
cd frontend
npm run dev
```

Open **http://localhost:5173** (the exact address Vite prints). Log in with the demo accounts, password
`Demo@12345`: `customer01@example.com`, `seller1@example.com`.

## 4. The demo questions

Open the assistant page. Use a new chat for each block (the «محادثة جديدة» button).

**A. Visitor, not logged in: shopping**

1. عايز موبايل سامسونج بحدود 15 ألف → product cards with prices
2. وأيهم كاميرته أحسن؟ → follow-up that uses the conversation
3. (new chat) عايز لابتوب للشغل والمونتاج ميزانيتي 40 ألف
4. قارن لي بين أرخص اتنين فيهم

**B. Visitor: support and limits**

5. الشحن بياخد كام يوم وبكام؟ → answer from the real policy
6. لو الموبايل جه بايظ أرجّعه إزاي؟
7. ألغي طلب 10002 → refuses and asks the visitor to log in

**C. Log in as `seller1@example.com`**

8. مبيعاتي آخر 30 يوم كام؟
9. إيه أكتر 3 منتجات بتتباع عندي؟
10. في منتجات المخزون بتاعها قرب يخلص؟
11. ألغي طلب 10002 → the seller cannot cancel a customer's order

**D. Log out, log in as `customer01@example.com`**

12. طلب 10105 وصل فين؟ → status of the customer's own order
13. ألغي طلب 10006 → refused: it is already delivered
14. ألغي طلب 10002 → the assistant asks first; press **أيوه** → "تم إلغاء الطلب"
15. أيوه (typed again, right after) → "nothing is waiting for your confirmation": no second cancel
16. عايز أرجّع طلب 10030 → checked against the return window

What to point out while presenting: four agents behind one chat box; the router picks the agent by the
role in the login token; nothing that changes data runs before the user presses yes; a seller only
ever sees their own data.

## 5. If something goes wrong

| What you see | Cause and fix |
|---|---|
| The site looks plain, no colors or layout | `npm ci` was not run, or you opened the wrong port. Run `npm ci` in `frontend`, restart `npm run dev`, and open the address Vite prints |
| The site shows data but the assistant says it is offline | The API is not running, or `VITE_API_URL` is wrong, or the origin is missing from `CORS_ORIGINS`. Restart both after changing a `.env` |
| The data looks fake | `VITE_USE_MOCK` is still `true`. Change it and restart `npm run dev` |
| The assistant answers "assistant unavailable" (503) | Every model failed: no keys, or all hit their limit. Check the keys and wait a minute |
| Answers are slow or "too many messages" (429) | Free-tier limits, or more than 20 messages in a minute from one user. Wait a minute. Raise `ASSISTANT_RATE_LIMIT_PER_MINUTE` if needed |
| The cancel question says order 10002 cannot be cancelled | It was cancelled in an earlier run. Stop the API and run step 1 |
| `demo_reset` fails | PostgreSQL is not running, or `DATABASE_URL` is wrong |
