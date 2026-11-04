# AGENTS.md — Dalil frontend (short rules, read with HANDOFF.md)

Full context, decisions, backend contract and progress log: **HANDOFF.md** (read it first).

## Non-negotiables
1. **No emojis** anywhere in UI, copy, mock data or chat.
2. Arabic tone: calm, modern, not slang, not stiff. Never "باشا"-style language.
3. **Letter-spacing 0 on Arabic.** No `tracking-*` utilities on Arabic text.
4. Fonts: Reem Kufi (headings, 700), Readex Pro (body), IBM Plex Mono (dev panel only). Do not add others.
5. Colors: only the tokens in `tailwind.config.js` (paper/ink/green family + danger/warn). One accent: green.
6. Small radii, thin 1px borders, no shadows on cards, no gradients.
7. RTL with logical utilities only (`ms/me/ps/pe/start/end`).
8. Components never import mock data. Use `src/api/*` + hooks. Mock/real switch is `VITE_USE_MOCK`.
9. No Supabase / BaaS / extra global state libraries.
10. Run `npm run build` before saying anything is done.

## Working with the user (Esraa)
- Mentor mode: explain briefly why, one next action at a time, ask before running new commands or installing packages beyond the approved scope.
- Be honest about unverified backend details. Never invent endpoints.
- Update the Progress log in HANDOFF.md at the end of every batch and before you run out of budget.
