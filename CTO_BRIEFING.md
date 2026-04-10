# CTO Briefing -- Asymmetric Multi-Agent Debate Engine

## 1. Elevator Pitch

We built a multi-agent AI system that simulates a wealth management investment committee. A financial advisor types in a client scenario, and three AI agents -- a Risk Officer, a Growth Strategist, and a Committee Chair -- debate and synthesize a balanced recommendation in real time. It streams live, produces a downloadable client-ready memo, and runs on a single Python file with zero infrastructure cost.

---

## 2. The Business Problem

Financial advisors preparing client recommendations today face a structural blind spot: they think from one perspective. A good wealth management firm compensates for this with an investment committee -- multiple experts challenging each other before a recommendation reaches the client.

This tool **democratizes the investment committee process**. A solo advisor, a junior planner, or a branch office without deep specialist bench strength can now pressure-test a strategy against two adversarial viewpoints and receive a synthesized, actionable recommendation -- in under 60 seconds.

---

## 3. Architecture

```
                        ┌─────────────────────┐
                        │   User enters client │
                        │   scenario in UI     │
                        └─────────┬───────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │  Build prompt with full   │
                    │  conversation history     │
                    └──────────┬───────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
     ┌────────────┐   ┌────────────┐   ┌────────────────┐
     │  Agent A    │   │  Agent B    │   │  Synthesis      │
     │  Risk &     │   │  Alpha      │   │  Committee      │
     │  Compliance │   │  Strategist │   │  Chair          │
     │             │   │             │   │                 │
     │  Persona    │   │  Persona    │   │  Persona        │
     │  enforced   │   │  enforced   │   │  enforced via   │
     │  via system │   │  via system │   │  system         │
     │  instruction│   │  instruction│   │  instruction    │
     └──────┬─────┘   └──────┬─────┘   └───────┬────────┘
            │                │                  │
            └────────────────┼──────────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │  Gemini API          │
                  │  gemini-2.5-flash    │
                  │  or gemini-2.5-pro   │
                  │  stream=True         │
                  └─────────┬───────────┘
                            │
                            ▼
              ┌──────────────────────────┐
              │  Real-time streaming UI   │
              │  + progress bar           │
              │  + elapsed time badges    │
              │  + downloadable Markdown  │
              └──────────────────────────┘
```

### What makes this adversarial, not parallel

This is not three independent prompts. Each agent receives the *full conversation history* from all prior turns:

- **Round 1**: Agent A critiques the scenario. Agent B receives Agent A's critique and directly counters it.
- **Round 2**: Agent A receives Agent B's Round 1 rebuttal and strengthens its risk case. Agent B counters again.
- **Synthesis**: The Committee Chair reads the entire debate transcript and produces a structured, balanced recommendation.

The debate is contextual and adversarial. Each turn builds on the last.

---

## 4. Technical Decisions and Why

**Single file (app.py, 552 lines)**
Deliberate. No framework overhead, no microservices, no database. A technical reviewer can read the entire system in 10 minutes. This is a proof of architecture, not a proof of infrastructure.

**`system_instruction` for persona enforcement**
Gemini's `system_instruction` parameter is immutable per-request -- the agent cannot be prompted out of character by the conversation history. This is structurally more robust than prepending persona text to the user prompt.

**Streaming (stream=True + st.write_stream)**
Every token renders live. With 2 rounds + synthesis = 5 API calls, the total wait would be 30-60 seconds behind a spinner. Streaming makes it feel interactive instead of broken.

**Stateless deployment**
The app stores nothing server-side. `st.session_state` is per-browser-session and ephemeral. The API key is in Streamlit's encrypted secrets vault. There is no database, no user data retention, no PII storage -- which simplifies compliance conversations dramatically.

**Model toggle (Flash vs Pro)**
Flash runs the full debate in ~20 seconds at ~$0.01-0.03 per run. Pro takes ~45 seconds at ~$0.10-0.20 but produces deeper analysis. This lets the advisor choose speed vs. depth per scenario.

---

## 5. Live Demo Script (3 minutes)

**Setup**: Open the deployed app. Sidebar shows Model and Rounds only.

**Step 1 -- Select a template.** Pick "Concentrated Stock Position" (the biotech founder with 70% of her net worth in a single pre-IPO stock). This is relatable to anyone who has worked with equity-heavy tech executives.

**Step 2 -- Click Start Debate.** Narrate as it streams:
- "Agent A is the risk officer. Watch -- it's flagging concentration risk, liquidity risk on the pre-IPO, and the gap in retirement funding."
- "Now Agent B counters. It's not dismissing the risks -- it's proposing a collar strategy on the stock, a diversification timeline, and alternative allocations."
- "Round 2 -- they're directly arguing with each other now. Agent A is citing 2008 drawdowns. Agent B is quantifying the opportunity cost of sitting in cash."

**Step 3 -- Synthesis streams in.** "This is the committee chair. It doesn't take sides. It structures a 3-step action plan: immediate hedging, 3-month diversification, 12-month strategic allocation."

**Step 4 -- Click Download.** Open the Markdown file. "This is a client-ready memo the advisor can attach to a CRM record, email to the client, or bring to a review meeting."

**Closing line**: "The entire system is one Python file, one API key, and zero infrastructure. The architecture pattern -- adversarial multi-agent with synthesis -- is domain-agnostic. Swap the personas and you have legal contract review, M&A due diligence, or product strategy stress-testing."

---

## 6. Key Numbers

| Metric | Value |
|--------|-------|
| Latency per agent turn | ~4-6s (Flash), ~8-12s (Pro) |
| Cost per debate (2 rounds) | ~$0.01-0.03 (Flash), ~$0.10-0.20 (Pro) |
| Codebase | 1 file, 552 lines |
| Dependencies | 2 (Streamlit, google-generativeai) |
| Deployment | Streamlit Community Cloud, free tier |
| Infrastructure | Zero -- no database, no backend, no DevOps |
| Time to build | Hours, not sprints |

---

## 7. Forward Roadmap

**Near-term enhancements:**
- **Structured client intake** -- Replace free-text with a form (age, AUM, risk score, goals) for more consistent agent output
- **RAG integration** -- Ground agent responses in real market data, fund prospectuses, or firm-specific investment policy statements
- **Session history** -- Persist past debates so advisors can revisit and compare prior analyses

**Platform extensions:**
- **Scenario comparison** -- Side-by-side runs ("What if they retire at 55 vs 62?")
- **Compliance audit trail** -- Log every prompt and response for regulatory recordkeeping
- **Domain portability** -- Same architecture applied to legal contract review, M&A due diligence, product strategy stress-testing -- swap `system_instruction` and you have a new vertical
