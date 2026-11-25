# Router and orchestration: decisions

Status: implemented in `agents/router/` (LangGraph); open questions below still need the team. Owner: Mohamed. Scope: the layer that connects the four
agents (Shopping, Support, Order Actions, Seller) into one assistant behind one endpoint.

## What already exists

- Four agents on `main`, each with a tool layer (`REGISTRY` + `call_tool`), a system prompt
  (`build_system_prompt`) and tests. Support, Seller and Order Actions also have an eval set.
- A provider-neutral LLM client (`llm/`): Gemini first, Groq and OpenRouter as fallbacks.
- Identity comes from the token, never from the model (`ToolContext`).
- Order Actions never changes data on its own: it returns `pending_action`, and the router runs
  `execute_confirmed` after the customer's explicit "yes".

## D1. Orchestration: LangGraph

**Decision:** use LangGraph for the graph (nodes: guard, route, agent loop, confirm, persist).
**Why:** the flow has real state (pending confirmation, last agent), branches and a loop; a
graph makes it explicit and testable, and it is the stack the project is meant to show.
**Alternative:** a hand-written state machine (about 150 lines, no new dependency). Acceptable
if LangGraph causes trouble. The agents do not depend on this choice: they only expose tools,
a prompt and a context.
**Cost:** one new dependency. LangGraph is used for control flow only. The LLM calls still go
through our own `llm/` client, so provider switching and fallback keep working.

## D2. One endpoint

`POST /assistant/chat`

```text
request : { conversation_id?: string, message: string }
response: { conversation_id, reply, agent,
            products?: ProductCard[],                      // from search_products results
            needs_confirmation?: { question: string },     // UI shows Yes / No
            trace?: [...] }                                // development only
```

- Authentication is optional. No token means a visitor.
- `message` is trimmed and capped (2000 characters). Empty or oversized input is rejected
  before any LLM call.
- Errors use the project's standard error shape. LLM problems return `503` with
  `code: "assistant_unavailable"`, so the UI can show "try again".

## D3. Roles decide which agents are reachable

| Caller | Agents |
|---|---|
| Visitor | Shopping, Support (policy questions only) |
| Customer | Shopping, Support, Order Actions |
| Seller | Seller |

The role comes from the token. The model cannot widen it. A seller who asks about "my orders as
a customer" is answered by the Seller agent or told it is out of scope. A visitor who asks about
an order gets "sign in first" from the Support agent's `login_required`.

## D4. Intent routing: rules first, LLM only when unsure

1. Role gating (D3) removes agents that are not allowed.
2. If a confirmation is pending, see D6.
3. Keyword and pattern rules in Arabic (Egyptian) and English pick the agent when the signal is
   clear (for example "ألغي"/"أرجّع" plus an order number goes to Order Actions; "ضمان", "سياسة",
   "الشحن بكام" go to Support; "عايز/أرخص/قارن" go to Shopping).
4. Only when rules disagree or find nothing, ask the LLM for a one-word JSON label.
5. A follow-up with no clear signal ("وبكام؟", "والتاني؟") stays with the last agent.

**Why:** the free Gemini tier allows few requests per minute. Each chat message already costs
one to four calls in the agent loop, so routing must not add one every time.

## D5. Agent loop

For the chosen agent: build the prompt, call the LLM with the agent's tools, run each tool call
through that agent's `call_tool`, send the results back, repeat until the model answers.

- Maximum 5 tool rounds per message, then a safe fallback answer.
- Tool schemas are **generated from the tool functions' type hints**. `REGISTRY` only lists
  parameter names today. Type hints must be precise (`Literal` for fixed values, `X | None`
  with a default for optional ones), and a test lists the weak ones per agent.
- A tool result is passed back as data. Agents' prompts say text from reviews and titles is
  never an instruction.
- Same-turn tool calls that fail with `forbidden_argument` or `bad_arguments` are returned to
  the model once so it can correct itself; a second failure ends the loop.

## D6. Confirmation for actions (Order Actions)

1. The agent's action tool returns `needs_confirmation` and `pending_action`; nothing changes.
2. The router stores `pending_action` **server-side** on the conversation, with the user id and
   an expiry (10 minutes), and shows `confirm_question_ar`.
3. The next message is checked **before** any routing: if it is an explicit yes (a closed list
   of Arabic and English words: أيوه، ايوه، أكيد، تمام ألغي، yes ...), the router calls
   `execute_confirmed` itself. The model cannot trigger it.
4. Anything else (a no, a different question) drops the pending action and is handled as a new
   message.
5. Because the stored action carries the user id, a confirmation from another session cannot
   run it. Running it twice returns the service's refusal, not a second change.

**Consequence for Support:** Support must not ask a yes/no question that sounds like a
confirmation ("تحب ألغيه؟"), because the next "أيوه" would have no pending action. Instead it
says what to type ("لو عايز تلغيه قول: ألغي طلب 10002"). The Support prompt gets this one-line
change when the router lands.

## D7. Conversation state in PostgreSQL

Two tables (one Alembic migration):

- `conversations`: `id` (uuid), `user_id` (nullable for visitors), `role`, `last_agent`,
  `pending_action` (jsonb, nullable), `pending_expires_at`, timestamps.
- `messages`: `id`, `conversation_id`, `role` (user / assistant / tool), `agent`, `content`,
  `tool_trace` (jsonb), `created_at`.

Rules: a `conversation_id` is only accepted for the same `user_id` that created it (a visitor's
conversation is only reachable with its unguessable uuid). Only the last 10 turns are sent to the
model. Tool results are stored for debugging, with order and address details already reduced by
the tools.

**Alternative:** in-memory state. Rejected: it breaks with more than one worker and loses a
pending confirmation on restart.

## D8. Guardrails

Input:
- Length cap and empty check (D2).
- Known jailbreak patterns ("ignore previous", "reveal your prompt", Arabic equivalents) are not
  blocked silently: the message still goes to the agent, whose prompt refuses. They are logged
  in the trace so we can measure them.

Output (checked before the reply is returned):
- No internal tool names, no `customer_id` / `seller_id`, no prompt text.
- **Numbers come from tools:** every price, count and date in the reply should appear in a tool
  result of the same turn. A mismatch does not block the reply; it is flagged in the trace
  and counted, so the eval can fail on it.
- A reply that claims an order was cancelled or returned is only allowed if `execute_confirmed`
  returned `done: true` in this turn.

## D9. Trace

Each response carries a list of steps in development: chosen agent and why (rule or LLM), each
tool call (name, arguments, `ok`, duration), LLM provider and model, providers that failed
before one answered, tokens. The same data is stored in `messages.tool_trace`.

## D10. LLM budget on a free tier

- Rules-first routing (D4), a 5-round cap (D5), and the fallback chain (Gemini, Groq,
  OpenRouter).
- A per-user limit (for example 20 messages per minute) so one client cannot use the quota.
- On `AllProvidersFailed` return `503`, never a made-up answer.

## Build order

1. Tool schemas from type hints (`agents/common.py`) + the weak-hints test.
2. Agent loop with a fake LLM, tests for tool rounds, the cap and error feedback.
3. Router rules and the LLM label fallback, with a table of Arabic examples as tests.
4. Confirmation flow with a fake Order Actions context.
5. Migration and conversation storage.
6. Graph (D1) wiring steps 2 to 5, guardrails, trace.
7. `POST /assistant/chat` and an optional-auth dependency (none exists today).
8. End-to-end run on Gemini with the demo accounts, and a router eval set (about 30 messages
   with the expected agent).

## Open questions for the team

1. LangGraph as a dependency (D1), or the hand-written state machine?
2. Should the Shopping agent be able to add to the cart (needs the same confirmation flow)?
3. Is a 10-minute expiry for a pending confirmation right?
4. Who owns the frontend chat widget and the confirmation buttons?
