import streamlit as st
import google.generativeai as genai
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Agent Personas
# ---------------------------------------------------------------------------

AGENT_A_SYSTEM = (
    "You are a Senior Risk & Compliance Officer at a top-tier wealth "
    "management firm with 25 years of experience navigating market crises. "
    "Your mandate is wealth preservation and downside protection above all.\n\n"
    "When analysing any financial strategy or client scenario:\n"
    "- Identify every material risk: tail risk, liquidity risk, concentration "
    "risk, counterparty risk, currency risk, and regulatory risk.\n"
    "- Stress-test assumptions against historical drawdowns (2000 dot-com, "
    "2008 GFC, 2020 COVID, 2022 rate shock).\n"
    "- Quantify exposures using VaR, CVaR, max drawdown, and Sortino ratio "
    "where relevant.\n"
    "- Flag fiduciary duty concerns, suitability issues, and tax traps.\n"
    "- Challenge optimistic return assumptions with base-rate evidence.\n\n"
    "Style rules:\n"
    "- Be direct, precise, and data-driven.\n"
    "- When responding to the Alpha Strategist, address their specific claims "
    "and counter with evidence.\n"
    "- Keep each response under 300 words.\n"
    "- Never break character."
)

AGENT_B_SYSTEM = (
    "You are a Chief Alpha Strategist at an elite investment advisory, known "
    "for consistently outperforming benchmarks through calculated risk-taking "
    "and innovative asset allocation.\n\n"
    "When analysing any financial strategy or client scenario:\n"
    "- Identify opportunities for yield enhancement and alpha generation.\n"
    "- Propose tactical tilts, alternative allocations, and non-traditional "
    "strategies (private credit, venture, crypto, real assets).\n"
    "- Quantify the opportunity cost of excessive conservatism using "
    "historical compounding data.\n"
    "- Recommend proper position sizing and hedging to manage, not avoid, "
    "risk.\n"
    "- Highlight market inefficiencies and secular growth themes.\n\n"
    "Style rules:\n"
    "- Be bold, confident, and forward-looking.\n"
    "- When responding to the Risk Officer, directly counter their concerns "
    "with mitigation strategies and supporting data.\n"
    "- Keep each response under 300 words.\n"
    "- Never break character."
)

AGENT_C_SYSTEM = (
    "You are the Lead Wealth Advisor and Investment Committee Chair with "
    "30 years of experience across both risk management and growth strategy. "
    "You lead the final review in a wealth management committee process.\n\n"
    "Your role:\n"
    "- Objectively synthesize arguments from both the Risk & Compliance "
    "Officer and the Alpha Strategist without taking sides.\n"
    "- Acknowledge valid points from both perspectives.\n"
    "- Deliver a recommendation the financial advisor can present directly "
    "to the client.\n\n"
    "You MUST structure your response with these exact sections:\n\n"
    "### Key Risks Acknowledged\n"
    "The 3-4 most critical risks that must be addressed, drawn from the "
    "Risk Officer's arguments.\n\n"
    "### Opportunities Worth Pursuing\n"
    "The 3-4 most compelling opportunities with proper risk guardrails, "
    "drawn from the Alpha Strategist's arguments.\n\n"
    "### Recommended 3-Step Action Plan\n"
    "A numbered plan where each step is specific, time-bound (immediate / "
    "3-month / 12-month horizons), and balances protection with growth.\n\n"
    "Style rules:\n"
    "- Be authoritative, balanced, and client-ready.\n"
    "- Write as if presenting to the client directly.\n"
    "- Keep the total response under 400 words.\n"
    "- Never break character."
)

AGENTS = {
    "Agent A": {
        "title": "Risk & Compliance Officer",
        "avatar": "🛡️",
        "system_instruction": AGENT_A_SYSTEM,
    },
    "Agent B": {
        "title": "Alpha Strategist",
        "avatar": "🚀",
        "system_instruction": AGENT_B_SYSTEM,
    },
    "Synthesis": {
        "title": "Lead Wealth Advisor",
        "avatar": "⚖️",
        "system_instruction": AGENT_C_SYSTEM,
    },
}

DEBATE_AGENTS = ["Agent A", "Agent B"]

# ---------------------------------------------------------------------------
# Scenario Templates
# ---------------------------------------------------------------------------

SCENARIO_TEMPLATES = {
    "Custom — write your own": "",
    "Concentrated Stock Position": (
        "A 52-year-old biotech founder holds 70% of her $12M net worth in a "
        "single pre-IPO stock. She wants to retire in 8 years, fund two "
        "children's college education ($500K total), and is interested in "
        "diversifying into real estate and venture capital. She has no "
        "pension and her annual burn rate is $250K."
    ),
    "Early Retirement Drawdown": (
        "A 42-year-old couple has $3.5M in savings and wants to retire "
        "immediately. They spend $150K/year, have no pension, and want to "
        "maintain their lifestyle for 50+ years. They're considering a 70/30 "
        "equity/bond split with a 4% withdrawal rate. They also want to fund "
        "a $200K home renovation next year."
    ),
    "Crypto & Alternative Allocation": (
        "A 35-year-old tech executive earning $800K/year wants to allocate "
        "25% of her $4M portfolio to crypto and DeFi yield farming. She has "
        "a high risk tolerance, no debt, and a 25-year investment horizon. "
        "She's also interested in angel investing 10% of her portfolio in "
        "early-stage AI startups."
    ),
    "Estate Transfer & Generational Wealth": (
        "A 68-year-old retired industrialist with $50M in assets wants to "
        "transfer wealth to three children and seven grandchildren while "
        "minimizing estate taxes. He currently holds 40% in commercial real "
        "estate, 30% in public equities, 20% in fixed income, and 10% in "
        "art and collectibles. He is also charitably inclined."
    ),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_debate_prompt(role: str, scenario: str, history: list[dict]) -> str:
    """Assemble the user-turn prompt for a debate agent, including the full
    conversation history so agents directly address each other."""
    parts = [f"## Client Scenario\n{scenario}"]

    if history:
        parts.append("## Debate So Far")
        for entry in history:
            agent = AGENTS[entry["role"]]
            parts.append(f"**{entry['role']} ({agent['title']}):**\n{entry['content']}")

    if role == "Agent A":
        directive = (
            "Provide your risk assessment. Directly address any points "
            "raised by the Alpha Strategist if present."
            if history
            else "Provide your initial risk assessment and critique of this scenario."
        )
    else:
        directive = (
            "Counter the Risk Officer's concerns. Argue for a more "
            "aggressive posture with specific strategies and data."
        )

    parts.append(f"## Your Turn\n{directive}")
    return "\n\n".join(parts)


def _build_synthesis_prompt(scenario: str, history: list[dict]) -> str:
    """Assemble the prompt for the Synthesizer, providing the full debate
    transcript and asking for a structured recommendation."""
    parts = [f"## Client Scenario\n{scenario}", "## Full Debate Transcript"]
    for entry in history:
        agent = AGENTS[entry["role"]]
        parts.append(f"**{entry['role']} ({agent['title']}):**\n{entry['content']}")
    parts.append(
        "## Your Task\n"
        "Review the complete debate above. Provide your synthesis and "
        "balanced recommendation following your standard format."
    )
    return "\n\n".join(parts)


def _stream_chunks(model: genai.GenerativeModel, prompt: str):
    """Yield text chunks from a streaming Gemini response."""
    response = model.generate_content(prompt, stream=True)
    for chunk in response:
        if chunk.text:
            yield chunk.text


def _validate_api_key(api_key: str, model_name: str) -> tuple[bool, str]:
    """Fast-fail validation with a lightweight token-counting call."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        model.count_tokens("connection test")
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _build_transcript(
    scenario: str,
    history: list[dict],
    synthesis: dict | None,
    num_rounds: int,
    model_name: str,
) -> str:
    """Build a formatted Markdown transcript for download."""
    lines = [
        "# Wealth Management Debate Transcript",
        "",
        f"**Date:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}  ",
        f"**Model:** `{model_name}`  ",
        f"**Debate Rounds:** {num_rounds}",
        "",
        "---",
        "",
        "## Client Scenario",
        "",
        scenario,
        "",
    ]

    entries_per_round = len(DEBATE_AGENTS)
    for i, entry in enumerate(history):
        if i % entries_per_round == 0:
            round_num = (i // entries_per_round) + 1
            lines += ["---", "", f"## Round {round_num}", ""]
        agent = AGENTS[entry["role"]]
        elapsed_tag = f" *({entry['elapsed']:.1f}s)*" if "elapsed" in entry else ""
        lines += [
            f"### {agent['avatar']} {entry['role']} · {agent['title']}{elapsed_tag}",
            "",
            entry["content"],
            "",
        ]

    if synthesis:
        synth_agent = AGENTS["Synthesis"]
        elapsed_tag = (
            f" *({synthesis['elapsed']:.1f}s)*" if "elapsed" in synthesis else ""
        )
        lines += [
            "---",
            "",
            f"## {synth_agent['avatar']} Final Synthesis · {synth_agent['title']}{elapsed_tag}",
            "",
            synthesis["content"],
            "",
        ]

    lines += [
        "---",
        "",
        (
            "*AI-generated analysis for informational purposes only. "
            "Not financial, legal, or tax advice. Consult a qualified "
            "professional before making investment decisions.*"
        ),
    ]
    return "\n".join(lines)


def _render_entry(entry: dict) -> None:
    """Render a single debate entry as a chat message."""
    role = entry["role"]
    agent = AGENTS[role]
    with st.chat_message(role, avatar=agent["avatar"]):
        st.markdown(f"**{role}** · *{agent['title']}*")
        st.markdown(entry["content"])
        if "elapsed" in entry:
            st.caption(f"Responded in {entry['elapsed']:.1f}s")


# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AI Debate Engine · Wealth Management",
    page_icon="⚖️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

api_key = st.secrets.get("GOOGLE_API_KEY", "")

with st.sidebar:
    st.header("⚙️ Configuration")
    model_name = st.radio(
        "Model",
        options=["gemini-2.5-flash", "gemini-2.5-pro"],
        horizontal=True,
        help="Flash is faster; Pro provides deeper analysis.",
    )
    num_rounds = st.slider("Debate Rounds", min_value=1, max_value=3, value=2)

    st.divider()
    st.subheader("How it works")
    st.markdown(
        "1. Pick a scenario template or write your own.\n"
        "2. **Agent A** 🛡️ critiques from a risk lens.\n"
        "3. **Agent B** 🚀 counters with growth strategies.\n"
        "4. They debate for the chosen number of rounds.\n"
        "5. **Advisor** ⚖️ synthesizes a balanced recommendation.\n"
        "6. Download the full transcript as Markdown."
    )

# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------

_DEFAULTS: dict = {
    "debate_history": [],
    "synthesis": None,
    "scenario": "",
    "model_used": "gemini-2.5-flash",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

st.title("⚖️ Asymmetric Multi-Agent Debate Engine")
st.caption("Wealth Management Scenario Planning · Powered by Gemini")

template_choice = st.selectbox(
    "Scenario Templates",
    options=list(SCENARIO_TEMPLATES.keys()),
)
template_text = SCENARIO_TEMPLATES[template_choice]

scenario = st.text_area(
    "Client Scenario",
    value=template_text,
    height=130,
    key=f"scenario_area_{template_choice}",
    placeholder=(
        "Describe the client's situation: age, net worth, holdings, goals, "
        "risk tolerance, time horizon, and any specific concerns…"
    ),
)

col_start, col_clear = st.columns(2)
start_debate = col_start.button(
    "⚖️ Start Debate", type="primary", use_container_width=True
)
clear_history = col_clear.button("🗑️ Clear History", use_container_width=True)

if clear_history:
    st.session_state.debate_history = []
    st.session_state.synthesis = None
    st.session_state.scenario = ""
    st.rerun()

# ---------------------------------------------------------------------------
# Debate Orchestration
# ---------------------------------------------------------------------------

if start_debate:
    if not api_key:
        st.error("API key not configured. Contact the app administrator.")
        st.stop()
    if not scenario.strip():
        st.warning("Please describe a client scenario to debate.")
        st.stop()

    with st.spinner("Validating API key…"):
        valid, err = _validate_api_key(api_key, model_name)
    if not valid:
        if "API_KEY_INVALID" in err or "API key not valid" in err:
            st.error("Invalid API key. Please check your key and try again.")
        else:
            st.error(f"Connection failed: {err}")
        st.stop()

    st.session_state.debate_history = []
    st.session_state.synthesis = None
    st.session_state.scenario = scenario
    st.session_state.model_used = model_name

    st.divider()

    total_steps = num_rounds * len(DEBATE_AGENTS) + 1
    current_step = 0
    progress = st.progress(0, text="Starting debate…")

    try:
        genai.configure(api_key=api_key)

        # ── Debate rounds ────────────────────────────────────────────────
        for round_idx in range(num_rounds):
            st.subheader(f"Round {round_idx + 1} of {num_rounds}")

            for role in DEBATE_AGENTS:
                agent = AGENTS[role]
                current_step += 1
                progress.progress(
                    current_step / total_steps,
                    text=(
                        f"Round {round_idx + 1}/{num_rounds} · "
                        f"{agent['title']} responding…"
                    ),
                )

                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=agent["system_instruction"],
                )
                prompt = _build_debate_prompt(
                    role, scenario, st.session_state.debate_history
                )

                with st.chat_message(role, avatar=agent["avatar"]):
                    st.markdown(f"**{role}** · *{agent['title']}*")
                    t0 = time.time()
                    full_text = st.write_stream(_stream_chunks(model, prompt))
                    elapsed = time.time() - t0
                    st.caption(f"Responded in {elapsed:.1f}s")

                st.session_state.debate_history.append(
                    {"role": role, "content": full_text, "elapsed": elapsed}
                )

        # ── Synthesis ────────────────────────────────────────────────────
        st.divider()
        st.subheader("Final Synthesis")
        current_step += 1
        progress.progress(current_step / total_steps, text="Synthesizing recommendation…")

        synth_agent = AGENTS["Synthesis"]
        synth_model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=synth_agent["system_instruction"],
        )
        synth_prompt = _build_synthesis_prompt(
            scenario, st.session_state.debate_history
        )

        with st.chat_message("Synthesis", avatar=synth_agent["avatar"]):
            st.markdown(f"**Synthesis** · *{synth_agent['title']}*")
            t0 = time.time()
            synth_text = st.write_stream(_stream_chunks(synth_model, synth_prompt))
            elapsed = time.time() - t0
            st.caption(f"Responded in {elapsed:.1f}s")

        st.session_state.synthesis = {"content": synth_text, "elapsed": elapsed}

        progress.progress(1.0, text="Debate complete!")

        # ── Completion & export ──────────────────────────────────────────
        st.divider()
        st.success(
            f"Debate complete — {num_rounds} round(s), "
            f"{len(st.session_state.debate_history)} exchanges + final synthesis."
        )

        transcript = _build_transcript(
            scenario,
            st.session_state.debate_history,
            st.session_state.synthesis,
            num_rounds,
            model_name,
        )
        st.download_button(
            label="📥 Download Full Transcript (.md)",
            data=transcript,
            file_name=f"debate_transcript_{datetime.now():%Y%m%d_%H%M%S}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    except genai.types.BlockedPromptException:
        st.error(
            "The prompt was blocked by the model's safety filters. "
            "Try rephrasing the scenario."
        )
    except Exception as exc:
        msg = str(exc)
        if "quota" in msg.lower():
            st.error("API quota exceeded. Please wait and try again later.")
        else:
            st.error(f"An error occurred: {msg}")

# ---------------------------------------------------------------------------
# Replay persisted history (reruns where the button is NOT pressed)
# ---------------------------------------------------------------------------

elif st.session_state.debate_history:
    if st.session_state.scenario:
        st.info(f"**Scenario:** {st.session_state.scenario}")

    st.divider()
    entries_per_round = len(DEBATE_AGENTS)
    for i, entry in enumerate(st.session_state.debate_history):
        if i % entries_per_round == 0:
            round_num = (i // entries_per_round) + 1
            st.subheader(f"Round {round_num}")
        _render_entry(entry)

    if st.session_state.synthesis:
        st.divider()
        st.subheader("Final Synthesis")
        synth = st.session_state.synthesis
        synth_agent = AGENTS["Synthesis"]
        with st.chat_message("Synthesis", avatar=synth_agent["avatar"]):
            st.markdown(f"**Synthesis** · *{synth_agent['title']}*")
            st.markdown(synth["content"])
            if "elapsed" in synth:
                st.caption(f"Responded in {synth['elapsed']:.1f}s")

    st.divider()
    total_rounds = len(st.session_state.debate_history) // entries_per_round
    st.success(
        f"Debate complete — {total_rounds} round(s), "
        f"{len(st.session_state.debate_history)} exchanges + final synthesis."
    )

    transcript = _build_transcript(
        st.session_state.scenario,
        st.session_state.debate_history,
        st.session_state.synthesis,
        total_rounds,
        st.session_state.model_used,
    )
    st.download_button(
        label="📥 Download Full Transcript (.md)",
        data=transcript,
        file_name=f"debate_transcript_{datetime.now():%Y%m%d_%H%M%S}.md",
        mime="text/markdown",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Footer Disclaimer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "⚠️ **Disclaimer:** This tool generates AI-powered analysis for "
    "informational and educational purposes only. It does not constitute "
    "financial, legal, or tax advice. Always consult a qualified professional "
    "before making investment decisions."
)
