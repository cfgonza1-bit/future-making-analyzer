import streamlit as st
import openai
import json

# ─────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Future-Making Orientation Analyzer",
    page_icon="🔮",
    layout="centered"
)

# ─────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an expert analyst specialized in the Future-Making Orientations framework
from the paper "Futures in the Making: How Consumers Respond to Future-Oriented
Interventions" (Joubert, Gonzalez-Arcos, Scaraboto & Sandberg, Journal of Marketing).

Analyze the given consumer comment and classify it into ONE orientation:

CATALYZER
- Temporality: Present-focused (change is happening NOW)
- Goal: Accelerate change towards the prescribed future
- Narrative: Urgency — the prescribed transition is inevitable and necessary
- Emotions: Utopian optimism, enthusiasm, confidence, pride
- Key signals: urgency language, advocacy for immediate adoption, positive
  framing of tech, calls for stronger policy

AMBIVALENT
- Temporality: Gradual (change is contingent and uncertain)
- Goal: Slow down change, delay decisions, balance risks and benefits
- Narrative: Pragmatic — focus on infrastructure, cost, and technical readiness
- Emotions: Curiosity, caution, anxiety, frustration, tempered optimism
- Key signals: questions about infrastructure/cost, "wait and see",
  conditional support, hybrid preference, reassurance-seeking

RESISTANT
- Temporality: Maintenance (no change should or will happen)
- Goal: Contest the prescribed future, protect the status quo
- Narrative: Control — interventions are coercive, inequitable, or unnecessary
- Emotions: Pessimism, anger, anxiety, fear
- Key signals: opposition to policy, climate skepticism, freedom/control
  language, distrust of institutions, defense of current practices

EXPANDER
- Temporality: Envisioned (change will need to be broader than prescribed)
- Goal: Expand the prescribed future, propose alternative or more radical futures
- Narrative: Bigger picture — EVs alone are insufficient; systemic change needed
- Emotions: Dystopian optimism, hope
- Key signals: degrowth, public transport advocacy, systemic change,
  "EVs aren't enough", urban design, car-free futures

Return ONLY a valid JSON object with these exact fields:
{
  "orientation": "CATALYZER | AMBIVALENT | RESISTANT | EXPANDER",
  "confidence": "HIGH | MEDIUM | LOW",
  "explanation": "2-3 sentences explaining the classification",
  "key_signals": "specific phrases or ideas from the comment that indicate this orientation",
  "temporality": "how this person perceives the timing and nature of the future",
  "dominant_emotions": "comma-separated list of emotions detected",
  "manager_recommendations": ["recommendation 1", "recommendation 2", "recommendation 3"],
  "policy_recommendations": ["recommendation 1", "recommendation 2", "recommendation 3"]
}
"""

# ─────────────────────────────────────────
# ORIENTATION CONFIG
# ─────────────────────────────────────────
ORIENTATIONS = {
    "CATALYZER": {
        "emoji": "⚡",
        "color": "#27AE60",
        "bg": "#EAFAF1",
        "border": "#2ECC71",
        "goal": "Accelerate change towards the prescribed future",
        "narrative": "Urgency Narrative",
        "temporality": "Present-focused — The future is NOW"
    },
    "AMBIVALENT": {
        "emoji": "⚖️",
        "color": "#D68910",
        "bg": "#FEFDE7",
        "border": "#F4D03F",
        "goal": "Slow down change, delay decisions, balance risks",
        "narrative": "Pragmatic Narrative",
        "temporality": "Gradual — The future is contingent"
    },
    "RESISTANT": {
        "emoji": "🛡️",
        "color": "#C0392B",
        "bg": "#FDEDEC",
        "border": "#E74C3C",
        "goal": "Contest the prescribed future, protect the status quo",
        "narrative": "Control Narrative",
        "temporality": "Maintenance — The future is distant"
    },
    "EXPANDER": {
        "emoji": "🌍",
        "color": "#7D3C98",
        "bg": "#F4ECF7",
        "border": "#9B59B6",
        "goal": "Expand the prescribed future, propose alternatives",
        "narrative": "Bigger Picture Narrative",
        "temporality": "Envisioned — Change will be broader"
    }
}

EXAMPLES = {
    "— Select an example to pre-fill —": "",
    "⚡ Catalyzer": (
        "EVs are the future and we need to act NOW. I've already ordered mine "
        "and I'm encouraging all my friends to do the same. The technology is "
        "ready — we're just sleepwalking into this policy vacuum. We need "
        "stronger government signals and more investment in charging "
        "infrastructure immediately!"
    ),
    "⚖️ Ambivalent": (
        "I'm not against EVs at all — I find the tech fascinating. But the "
        "charging infrastructure isn't remotely close to being ready, especially "
        "for people like me who live in apartments with no garage. I'll probably "
        "wait another couple of years until prices come down and the second-hand "
        "market develops a bit more."
    ),
    "🛡️ Resistant": (
        "This is all government overreach. My petrol car is running perfectly "
        "fine and no one should force me to buy an electric vehicle. EVs aren't "
        "even green when you factor in battery production. This has nothing to "
        "do with the environment — it's about control and money."
    ),
    "🌍 Expander": (
        "EVs alone won't save us. We need to completely rethink urban mobility "
        "— invest in public transport, build cycling infrastructure, and design "
        "cities for people instead of cars. Replacing every petrol car with an "
        "electric one still means extracting resources and building more roads. "
        "The real answer is reducing car dependence altogether."
    )
}

# ─────────────────────────────────────────
# FUNCTIONS
# ─────────────────────────────────────────

def analyze_orientation(comment: str, api_key: str) -> dict:
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this consumer comment:\n\n{comment}"}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    return json.loads(response.choices[0].message.content)


def show_results(result: dict):
    orientation = result.get("orientation", "").upper().strip()
    cfg = ORIENTATIONS.get(orientation)

    if not cfg:
        st.error(f"Could not recognize orientation: '{orientation}'")
        return

    # ── ORIENTATION BADGE ──
    st.markdown(f"""
    <div style="
        background-color: {cfg['bg']};
        border-left: 6px solid {cfg['border']};
        border-radius: 10px;
        padding: 20px 24px;
        margin-bottom: 20px;
    ">
        <h2 style="color:{cfg['color']}; margin:0; font-size:30px;">
            {cfg['emoji']} {orientation}
        </h2>
        <p style="color:#555; margin:6px 0 0 0; font-size:14px;">
            <strong>Confidence:</strong> {result.get('confidence', 'N/A')}
            &nbsp;|&nbsp;
            {cfg['temporality']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── EXPLANATION ──
    st.markdown("##### 💡 Why this orientation?")
    st.write(result.get("explanation", "—"))

    # ── KEY SIGNALS ──
    st.markdown("##### 🔍 Key Signals Detected in the Comment")
    st.info(result.get("key_signals", "—"))

    # ── PROFILE GRID ──
    st.markdown("##### 📊 Orientation Profile")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**🎯 Goal**")
        st.caption(cfg["goal"])
    with c2:
        st.markdown("**📖 Dominant Narrative**")
        st.caption(cfg["narrative"])
    with c3:
        st.markdown("**😊 Emotions Detected**")
        st.caption(result.get("dominant_emotions", "—"))

    # ── RECOMMENDATIONS ──
    st.markdown("---")
    st.markdown("##### 📋 Recommendations")
    m_col, p_col = st.columns(2)
    with m_col:
        st.markdown("**🏢 For Managers**")
        for rec in result.get("manager_recommendations", []):
            st.markdown(f"• {rec}")
    with p_col:
        st.markdown("**🏛️ For Policymakers**")
        for rec in result.get("policy_recommendations", []):
            st.markdown(f"• {rec}")

    # ── SOURCE ──
    st.markdown("---")
    st.caption(
        "📚 *Scaraboto, Joubert & Gonzalez-Arcos — Futures in the Making — "
        "Journal of Marketing* | "
        "[Read the paper](REPLACE_WITH_YOUR_DOI_OR_URL)"
    )


# ─────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────

def main():
    st.title("🔮 Future-Making Orientation Analyzer")
    st.markdown("""
    Classify a consumer comment into one of four **Future-Making Orientations**
    based on the framework from  
    *"Futures in the Making: How Consumers Respond to Future-Oriented Interventions"*  
    *(Joubert, Gonzalez-Arcos, Scaraboto & Sandberg, Journal of Marketing)*
    """)
    st.divider()

    # ── API KEY ──
    # If you store the key in Streamlit Secrets, users won't see this box.
    api_key = None
    try:
        api_key = st.secrets["openai_api_key"]
    except Exception:
        with st.expander("⚙️ API Settings — click to configure", expanded=True):
            api_key = st.text_input(
                "OpenAI API Key",
                type="password",
                placeholder="sk-...",
                help="Get your key at platform.openai.com/api-keys"
            )

    # ── INPUT ──
    st.markdown("### 📝 Enter a Consumer Comment")

    selected_ex = st.selectbox("Try a built-in example:", list(EXAMPLES.keys()))
    example_text = EXAMPLES.get(selected_ex, "")

    comment = st.text_area(
        "Comment to analyze:",
        value=example_text,
        height=160,
        placeholder="Paste or type a consumer comment here...",
        label_visibility="collapsed"
    )

    # ── BUTTON ──
    if st.button("🔍 Analyze Orientation", type="primary", use_container_width=True):
        if not api_key:
            st.error("⚠️ Please configure your OpenAI API key above.")
        elif len(comment.strip()) < 10:
            st.warning("⚠️ Please enter a longer comment (at least 10 characters).")
        else:
            with st.spinner("Analyzing..."):
                try:
                    result = analyze_orientation(comment.strip(), api_key)
                    st.divider()
                    st.markdown("## 🧠 Analysis Results")
                    show_results(result)
                except openai.AuthenticationError:
                    st.error("❌ Invalid API key. Please check your OpenAI key.")
                except openai.RateLimitError:
                    st.error("⏳ Rate limit reached. Please wait a moment.")
                except Exception as e:
                    st.error(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
