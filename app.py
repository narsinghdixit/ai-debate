from google import genai
from google.genai import types
import streamlit as st
import time
import re
from datetime import datetime
from fpdf import FPDF

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


def _build_refinement_prompt(
    scenario: str,
    history: list[dict],
    current_synthesis: str,
    directive: str,
) -> str:
    """Assemble a prompt that asks the Synthesizer to revise its
    recommendation based on a user-provided directive."""
    parts = [f"## Client Scenario\n{scenario}", "## Full Debate Transcript"]
    for entry in history:
        agent = AGENTS[entry["role"]]
        parts.append(f"**{entry['role']} ({agent['title']}):**\n{entry['content']}")
    parts.append(f"## Your Previous Recommendation\n{current_synthesis}")
    parts.append(
        f"## Refinement Request\n"
        f"The advisor has requested: {directive}\n\n"
        "Revise your recommendation to incorporate this feedback. "
        "Maintain your standard format (Key Risks Acknowledged / "
        "Opportunities Worth Pursuing / Recommended 3-Step Action Plan)."
    )
    return "\n\n".join(parts)


def _escape_dollars(text: str) -> str:
    """Escape bare $ signs so Streamlit's markdown renderer doesn't
    interpret currency values like $250K as LaTeX math."""
    return text.replace("$", r"\$")


def _stream_chunks(
    client: genai.Client,
    model_name: str,
    prompt: str,
    system_instruction: str,
):
    """Yield text chunks from a streaming Gemini response."""
    for chunk in client.models.generate_content_stream(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
        ),
    ):
        if chunk.text:
            yield chunk.text


def _display_stream(generator) -> str:
    """Stream text into the UI with dollar signs escaped for display.
    Returns the raw (unescaped) text for storage."""
    placeholder = st.empty()
    raw_chunks: list[str] = []
    for chunk in generator:
        raw_chunks.append(chunk)
        placeholder.markdown(_escape_dollars("".join(raw_chunks)))
    return "".join(raw_chunks)


def _validate_api_key(api_key: str, model_name: str) -> tuple[bool, str]:
    """Fast-fail validation with a lightweight token-counting call."""
    try:
        client = genai.Client(api_key=api_key)
        client.models.count_tokens(model=model_name, contents="connection test")
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _strip_markdown(text: str) -> str:
    """Lightweight markdown-to-plain-text for PDF body content."""
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    for old, new in {
        "\u2014": "--", "\u2013": "-", "\u201c": '"', "\u201d": '"',
        "\u2018": "'", "\u2019": "'", "\u2022": "-", "\u2026": "...",
    }.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _build_transcript_pdf(
    scenario: str,
    history: list[dict],
    synthesis: dict | None,
    num_rounds: int,
    model_name: str,
) -> bytes:
    """Build a clean, professional PDF transcript."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Wealth Management Debate Transcript", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    meta = (
        f"Date: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}  |  "
        f"Model: {model_name}  |  Rounds: {num_rounds}"
    )
    pdf.cell(0, 5, meta, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(6)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Client Scenario", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, _strip_markdown(scenario))
    pdf.ln(4)

    entries_per_round = len(DEBATE_AGENTS)
    for i, entry in enumerate(history):
        if i % entries_per_round == 0:
            round_num = (i // entries_per_round) + 1
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 8, f"Round {round_num}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        agent = AGENTS[entry["role"]]
        elapsed_tag = f"  ({entry['elapsed']:.1f}s)" if "elapsed" in entry else ""
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(
            0, 7,
            f"{entry['role']} - {agent['title']}{elapsed_tag}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _strip_markdown(entry["content"]))
        pdf.ln(4)

    if synthesis:
        synth_agent = AGENTS["Synthesis"]
        elapsed_tag = f"  ({synthesis['elapsed']:.1f}s)" if "elapsed" in synthesis else ""
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(
            0, 8,
            f"Final Synthesis - {synth_agent['title']}{elapsed_tag}",
            new_x="LMARGIN", new_y="NEXT",
        )
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 5, _strip_markdown(synthesis["content"]))
        pdf.ln(4)

    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(130, 130, 130)
    pdf.multi_cell(
        0, 4,
        "AI-generated analysis for informational purposes only. "
        "Not financial, legal, or tax advice. Consult a qualified "
        "professional before making investment decisions.",
    )

    return pdf.output()


def _render_entry(entry: dict) -> None:
    """Render a single debate entry as a chat message."""
    role = entry["role"]
    agent = AGENTS[role]
    with st.chat_message(role, avatar=agent["avatar"]):
        st.markdown(f"**{role}** · *{agent['title']}*")
        st.markdown(_escape_dollars(entry["content"]))
        if "elapsed" in entry:
            st.caption(f"Responded in {entry['elapsed']:.1f}s")


def _render_post_debate_ui(key_prefix: str, pdf_data: bytes) -> None:
    """Render download, refinement input, and New Debate button."""
    st.download_button(
        label="📥 Download Transcript (PDF)",
        data=pdf_data,
        file_name=f"debate_transcript_{datetime.now():%Y%m%d_%H%M%S}.pdf",
        mime="application/pdf",
        use_container_width=True,
        key=f"{key_prefix}_download",
    )

    if st.session_state.synthesis:
        st.caption("Want adjustments? Describe what to change below.")
        refine_col, btn_col = st.columns([4, 1])
        refine_text = refine_col.text_input(
            "Refinement directive",
            placeholder="e.g., 'make step 2 more conservative' or 'add tax implications'",
            label_visibility="collapsed",
            key=f"{key_prefix}_refine_input",
        )
        if btn_col.button("🔄 Refine", use_container_width=True, key=f"{key_prefix}_refine_btn"):
            if refine_text.strip():
                st.session_state.pending_refinement = refine_text.strip()
                st.rerun()
            else:
                st.warning("Enter a refinement directive.")

    if st.button("✨ Start New Debate", use_container_width=True, key=f"{key_prefix}_new"):
        st.session_state.debate_history = []
        st.session_state.synthesis = None
        st.session_state.scenario = ""
        st.session_state.pending_refinement = ""
        st.rerun()


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
        "6. Refine the synthesis or download the transcript."
    )

# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------

_DEFAULTS: dict = {
    "debate_history": [],
    "synthesis": None,
    "scenario": "",
    "model_used": "gemini-2.5-flash",
    "pending_refinement": "",
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

has_history = bool(st.session_state.debate_history)
if has_history and st.session_state.scenario:
    scenario_default = st.session_state.scenario
    scenario_key = "scenario_area_replay"
else:
    scenario_default = template_text
    scenario_key = f"scenario_area_{template_choice}"

scenario = st.text_area(
    "Client Scenario",
    value=scenario_default,
    height=130,
    key=scenario_key,
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
    st.session_state.pending_refinement = ""
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
    st.session_state.pending_refinement = ""

    st.divider()

    total_steps = num_rounds * len(DEBATE_AGENTS) + 1
    current_step = 0
    progress = st.progress(0, text="Starting debate…")

    try:
        client = genai.Client(api_key=api_key)

        # ── Debate rounds ────────────────────────────────────────────────
        for round_idx in range(num_rounds):
            st.subheader(f"Round {round_idx + 1} of {num_rounds}")

            with st.container(border=True):
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

                    prompt = _build_debate_prompt(
                        role, scenario, st.session_state.debate_history
                    )

                    with st.chat_message(role, avatar=agent["avatar"]):
                        st.markdown(f"**{role}** · *{agent['title']}*")
                        t0 = time.time()
                        full_text = _display_stream(
                            _stream_chunks(client, model_name, prompt, agent["system_instruction"])
                        )
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
        synth_prompt = _build_synthesis_prompt(
            scenario, st.session_state.debate_history
        )

        with st.chat_message("Synthesis", avatar=synth_agent["avatar"]):
            st.markdown(f"**Synthesis** · *{synth_agent['title']}*")
            t0 = time.time()
            synth_text = _display_stream(
                _stream_chunks(client, model_name, synth_prompt, synth_agent["system_instruction"])
            )
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

        pdf_data = _build_transcript_pdf(
            scenario,
            st.session_state.debate_history,
            st.session_state.synthesis,
            num_rounds,
            model_name,
        )
        _render_post_debate_ui("live", pdf_data)

    except Exception as exc:
        msg = str(exc)
        if "blocked" in msg.lower() or "safety" in msg.lower():
            st.error(
                "The prompt was blocked by the model's safety filters. "
                "Try rephrasing the scenario."
            )
        elif "quota" in msg.lower():
            st.error("API quota exceeded. Please wait and try again later.")
        else:
            st.error(f"An error occurred: {msg}")

# ---------------------------------------------------------------------------
# Replay persisted history (reruns where the button is NOT pressed)
# ---------------------------------------------------------------------------

elif st.session_state.debate_history:
    pending = st.session_state.get("pending_refinement", "")
    if pending:
        st.session_state.pending_refinement = ""

    st.divider()

    entries_per_round = len(DEBATE_AGENTS)
    total_rounds = len(st.session_state.debate_history) // entries_per_round

    for round_idx in range(total_rounds):
        st.subheader(f"Round {round_idx + 1}")
        with st.container(border=True):
            for j in range(entries_per_round):
                _render_entry(st.session_state.debate_history[round_idx * entries_per_round + j])

    # ── Synthesis (or refinement) ────────────────────────────────────
    if pending and st.session_state.synthesis:
        st.divider()
        st.subheader("Revised Synthesis")
        try:
            client = genai.Client(api_key=api_key)
            synth_agent = AGENTS["Synthesis"]
            refine_prompt = _build_refinement_prompt(
                st.session_state.scenario,
                st.session_state.debate_history,
                st.session_state.synthesis["content"],
                pending,
            )
            with st.chat_message("Synthesis", avatar=synth_agent["avatar"]):
                st.markdown(f"**Revised Synthesis** · *{synth_agent['title']}*")
                t0 = time.time()
                synth_text = _display_stream(
                    _stream_chunks(
                        client,
                        st.session_state.model_used,
                        refine_prompt,
                        synth_agent["system_instruction"],
                    )
                )
                elapsed = time.time() - t0
                st.caption(f"Responded in {elapsed:.1f}s")
            st.session_state.synthesis = {"content": synth_text, "elapsed": elapsed}
        except Exception as exc:
            st.error(f"Refinement failed: {exc}")

    elif st.session_state.synthesis:
        st.divider()
        st.subheader("Final Synthesis")
        synth = st.session_state.synthesis
        synth_agent = AGENTS["Synthesis"]
        with st.chat_message("Synthesis", avatar=synth_agent["avatar"]):
            st.markdown(f"**Synthesis** · *{synth_agent['title']}*")
            st.markdown(_escape_dollars(synth["content"]))
            if "elapsed" in synth:
                st.caption(f"Responded in {synth['elapsed']:.1f}s")

    # ── Completion & export ──────────────────────────────────────────
    st.divider()
    st.success(
        f"Debate complete — {total_rounds} round(s), "
        f"{len(st.session_state.debate_history)} exchanges + final synthesis."
    )

    pdf_data = _build_transcript_pdf(
        st.session_state.scenario,
        st.session_state.debate_history,
        st.session_state.synthesis,
        total_rounds,
        st.session_state.model_used,
    )
    _render_post_debate_ui("replay", pdf_data)

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
