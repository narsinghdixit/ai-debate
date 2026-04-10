# Asymmetric Multi-Agent Debate Engine

A wealth management scenario planning tool where three AI agents debate a financial strategy in real time and deliver a balanced, client-ready recommendation.

**[Live Demo](https://narsinghdixit-ai-debate.streamlit.app)**

---

## What It Does

A financial advisor enters a client scenario. Three AI agents -- each with a distinct persona enforced via Gemini's `system_instruction` -- take over:

| Agent | Role | Mandate |
|-------|------|---------|
| **Agent A** | Risk & Compliance Officer | Downside protection, regulatory risk, stress-testing against historical crises |
| **Agent B** | Alpha Strategist | Growth opportunities, yield generation, calculated risk-taking |
| **Synthesis** | Lead Wealth Advisor | Reviews the full debate, produces a structured 3-step action plan |

The agents debate for 1-3 rounds, each directly addressing the other's arguments using the full conversation history. After the debate, the Synthesizer delivers a balanced recommendation the advisor can present to the client.

## Key Features

- **Real-time streaming** -- every token renders live via `st.write_stream`
- **Adversarial context** -- each agent sees the full debate history and directly counters the other's points
- **Structured synthesis** -- the final recommendation follows a fixed format: Key Risks / Opportunities / 3-Step Action Plan
- **Markdown export** -- download the full transcript as a client-ready memo
- **Scenario templates** -- four pre-built wealth management scenarios for quick demos
- **Model selection** -- toggle between `gemini-2.5-flash` (speed) and `gemini-2.5-pro` (depth)

## Architecture

```
User Scenario
     │
     ▼
┌─────────────────────────────────────────────┐
│          Orchestration Loop (Python)         │
│                                             │
│  Round 1..N:                                │
│    ┌──────────┐  full history  ┌──────────┐ │
│    │ Agent A   │──────────────▶│ Agent B   │ │
│    │ (Risk)    │◀──────────────│ (Growth)  │ │
│    └──────────┘               └──────────┘  │
│                                             │
│  After all rounds:                          │
│    ┌──────────────────────────────────────┐  │
│    │ Synthesizer (Committee Chair)        │  │
│    │ Receives full transcript             │  │
│    │ Produces structured recommendation   │  │
│    └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
     │
     ▼
Streaming UI + Downloadable Transcript
```

Each agent is a separate `GenerativeModel` instance with its own `system_instruction`. The orchestration loop passes the growing conversation history to each agent so they build on -- and argue against -- each other's specific points.

## Quick Start

```bash
# Clone
git clone https://github.com/narsinghdixit/ai-debate.git
cd ai-debate

# Install
pip install -r requirements.txt

# Add your Gemini API key
echo 'GOOGLE_API_KEY = "your-key-here"' > .streamlit/secrets.toml

# Run
streamlit run app.py
```

## Project Structure

```
ai-debate/
├── app.py                    # Complete application (single file)
├── requirements.txt          # streamlit, google-generativeai
├── .streamlit/
│   ├── config.toml           # Dark theme configuration
│   └── secrets.toml          # API key (gitignored)
├── CTO_BRIEFING.md           # Architecture & presentation guide
└── .gitignore
```

## Tech Stack

- **Frontend**: Streamlit
- **LLM**: Google Gemini (`gemini-2.5-flash` / `gemini-2.5-pro`)
- **Deployment**: Streamlit Community Cloud
- **Language**: Python 3.10+
