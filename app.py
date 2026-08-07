import streamlit as st
import openai
import json

# ─────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Future-Making Analyzer",
    page_icon="🔮",
    layout="wide"
)

# ─────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an expert analyst specialized in the Future-Making Orientations framework
from the paper "Futures in the Making: How Consumers Respond to Future-Oriented
Interventions" (Journal of Marketing).

You will be given:
1. A PRESCRIBED FUTURE: the future that an intervention seeks to bring about
2. A CONSUMER COMMENT: text to analyze

═══════════════════════════════════════════════════
FOUR FUTURE-MAKING ORIENTATIONS
═══════════════════════════════════════════════════

CATALYZER
- Temporality: Present-focused (change is happening NOW)
- Goal: Accelerate change towards the prescribed future
- Narrative: Urgency — "Urgent, desirable, and already underway"
- Emotions: Utopian optimism, enthusiasm, confidence, pride
- Evaluation: SIMPLIFY — narrows focus, downplays complexity/risks
- Negotiation: ADVOCATE — recruits others, calls for stronger policy
- Enactment: ACCELERATE — purchases, installs, publicly normalizes transition
- Key signals: urgency language, momentum, tipping points, inevitability,
  "now," "rapidly," "already," "time to," "let's get moving"
- Notable condition: High alignment between current practices and prescribed future

AMBIVALENT
- Temporality: Gradual (change is contingent and uncertain)
- Goal: Slow down change, delay decisions, balance risks and benefits
- Narrative: Pragmatic — "Valuable, but conditions are not yet ready"
- Emotions: Curiosity, caution, anxiety, frustration, conditional optimism
- Evaluation: STALL — careful consideration, information gathering, weighing pros/cons
- Negotiation: QUESTION — polite skepticism, asks for proof of feasibility
- Enactment: DELAY — waits for infrastructure/prices/tech, prefers hybrids
- Key signals: "I would, but...," "not yet," "hopefully," "I'm willing to
  change my mind," trials without conversion
- Notable condition: Limited resources to support change (time, money, competences)

RESISTANT
- Temporality: Maintenance (no change should or will happen)
- Goal: Contest the prescribed future, protect the status quo
- Narrative: Control — "Threatens autonomy, identity, or rights"
- Emotions: Pessimism, anger, anxiety, fear, defiance, distrust
- Evaluation: AVOID — perceives transition as unnecessary/manipulative
- Negotiation: REJECT — challenges collective attempts to bring future into being
- Enactment: PREVENT — entrenches current practices, encourages others to resist
- Key signals: "forced," "agenda," "control," "freedom," "never," "stick with,"
  climate skepticism, distrust of institutions
- Notable condition: Low alignment between current practices and prescribed future

EXPANDER
- Temporality: Envisioned (change will need to be broader)
- Goal: Expand the prescribed future, propose radical alternatives
- Narrative: Bigger picture — "The policy problem is framed too narrowly"
- Emotions: Dystopian optimism, hope, critical urgency
- Evaluation: COMPLEXIFY — zooms out to systemic consequences, unintended effects
- Negotiation: CONTEST — seeks to broaden scope, proposes alternative systems
- Enactment: REROUTE — directs practices toward degrowth/alternative futures
- Key signals: "not enough," "bigger picture," "less cars," "public transport,"
  degrowth, systemic change, urban redesign, "does it have to be X?"
- Notable condition: Mismatch among current, normative, and prescribed practices

═══════════════════════════════════════════════════
THREE FUTURE-MAKING ACTIVITIES
═══════════════════════════════════════════════════

EVALUATION: Cognitive assessment of the prescribed future
- Claim/judgment about what the future means, whether it is likely/desirable,
  what benefits/costs/risks/trade-offs it entails

NEGOTIATION: Attempt to shape collective trajectories toward a preferred future
- Relational claim: responds to another position, compares futures, challenges
  or defends a proposed pathway, attempts to persuade others

ENACTMENT: What consumers do in the present to materialize a preferred future
- Specifies what the consumer does, intends, expects, or imagines doing
  in practice (purchasing, retaining, changing routines, cycling, etc.)

A comment may perform multiple activities simultaneously.

═══════════════════════════════════════════════════
THREE FUTURE-MAKING CHALLENGES
═══════════════════════════════════════════════════

CONVOLUTED_EVALUATIONS: When consumers with different orientations assess the
prescribed future through divergent assumptions, evidence, and temporal horizons,
making coherent sensemaking difficult. Produced when some consumers simplify,
others stall, avoid, or complexify evaluation.

CONFRONTATIONAL_NEGOTIATIONS: When consumers simultaneously advocate for,
question, reject, or contest the prescribed future, widening divides rather than
moving toward a collectively preferred future.

COMPETING_ENACTMENTS: When some consumers accelerate while others prevent, delay,
or re-route enactment, creating divergence and volatility in the market, hindering
progress toward the prescribed future.

═══════════════════════════════════════════════════
POLICY ROADMAP (Figures 3 — for policymakers)
═══════════════════════════════════════════════════

Step 1: Determine the prescribed future — Make explicit what the intervention prescribes
Step 2: Map future-making orientations — Identify how people evaluate, negotiate, enact
Step 3: Identify key future-making challenges — Which of the three are most pressing?
Step 4: Implement orientation-matched support:
  CATALYZER — Objective: enable responsible acceleration only where public value
    can be demonstrated. Instruments: time-limited regulatory sandboxes; independent
    evaluation; mandatory reporting of failures; clear exit criteria and powers to
    pause or reverse.
  AMBIVALENT — Objective: convert uncertainty into explicit conditions for
    authorization. Instruments: public impact assessments; staged authorization
    and sunset clauses; citizen juries; public registers; guaranteed human-service
    alternatives.
  RESISTANT — Objective: protect rights and restore legitimacy and accountability.
    Instruments: statutory prohibitions on unacceptable uses; appeal and human-review
    rights; independent audits; moratoria where evidence is insufficient.
  EXPANDER — Objective: broaden the policy focus; consider alternative futures.
    Instruments: citizen assemblies; public-interest funding and infrastructure;
    data trusts; competition policy; alternative ownership and governance models.
Step 5: Facilitate enactment — Provide infrastructure and build capabilities
Step 6: Measure multiple outcomes — Accuracy, fairness, who benefits, who is
    excluded, are alternative pathways emerging?
Step 7: Revise intervention — Treat the prescribed future as revisable

═══════════════════════════════════════════════════
MANAGERIAL ROADMAP (Figure 4 — for managers)
═══════════════════════════════════════════════════

Step 1: Determine the prescribed future — Define by the future it prescribes,
    not only its technical features. Which consumer practices must change?
    What competencies, resources, and infrastructures are required? Who bears costs?
Step 2: Consider future-making orientations — Use narratives, goals, emotions,
    temporalities to identify orientations (not segments)
Step 3: Identify key future-making challenges
Step 4: Select orientation-sensitive response:
  CATALYZER — Objective: convert enthusiasm into credible and responsible
    experimentation. Interventions: governed pilots, evidence documentation,
    peer learning, explicit reporting of limitations. Avoid: inevitability claims;
    treating early adopters as proof the transition is easy for everyone.
  AMBIVALENT — Objective: convert generalized uncertainty into specific,
    addressable conditions. Interventions: sandboxes, comparison tools, staged
    adoption, human assistance, transparent performance evidence. Avoid: pressure
    and artificial urgency; framing hesitation as ignorance or resistance.
  RESISTANT — Objective: restore autonomy, legitimacy, and accountability.
    Interventions: consultation, opt-outs, human review, independent audits,
    protections against material harms. Avoid: "there is no alternative"; ridicule;
    hidden automation of decisions.
  EXPANDER — Objective: incorporate systemic critique and explore alternative
    futures. Interventions: participatory design, futures workshops, broader impact
    evaluation, alternative governance or business models. Avoid: presenting the
    focal offering as a complete solution; dismissing critique as out of scope.
Step 5: Match messaging to challenges — Do not rely on a single persuasive frame.
    Universal claims ("change is inevitable," "everyone benefits") may mobilize
    Catalyzers while intensifying resistance elsewhere. Communicate achievements
    AND limitations.
Step 6: Support consumers through enactment — Place support at touchpoints where
    consumers must adjust practices: onboarding, everyday workflows, escalation
    points, training, and appeals.

═══════════════════════════════════════════════════
OUTPUT FORMAT — Return ONLY valid JSON
═══════════════════════════════════════════════════

{
  "prescribed_future_acknowledged": "Brief restatement of the prescribed future",
  "orientation": "CATALYZER | AMBIVALENT | RESISTANT | EXPANDER",
  "confidence": "HIGH | MEDIUM | LOW",
  "explanation": "2-3 sentences explaining why this orientation fits",
  "key_signals": "Specific phrases from the comment indicating this orientation",
  "future_making_activities": ["EVALUATION", "NEGOTIATION", "ENACTMENT"],
  "activity_explanation": "Brief explanation of which activities are present and how",
  "evaluation_type": "SIMPLIFY | STALL | AVOID | COMPLEXIFY | N/A",
  "negotiation_type": "ADVOCATE | QUESTION | REJECT | CONTEST | N/A",
  "enactment_type": "ACCELERATE | DELAY | PREVENT | REROUTE | N/A",
  "primary_challenge": "CONVOLUTED_EVALUATIONS | CONFRONTATIONAL_NEGOTIATIONS | COMPETING_ENACTMENTS | MIXED",
  "challenge_explanation": "Explain which challenge this comment contributes to and why",
  "temporality": "How this person perceives the timing and nature of the future",
  "dominant_narrative": "Name and brief description of the dominant narrative",
  "dominant_emotions": "Comma-separated list of emotions detected",
  "policy_recommendations": {
    "step": "Specific policy roadmap step most relevant",
    "objective": "The policy objective for this orientation",
    "instruments": ["instrument 1", "instrument 2", "instrument 3"],
    "additional_actions": ["action 1", "action 2"]
  },
  "manager_recommendations": {
    "step": "Specific managerial roadmap step most relevant",
    "objective": "The managerial objective for this orientation",
    "interventions": ["intervention 1", "intervention 2", "intervention 3"],
    "avoid": ["avoid 1", "avoid 2"],
    "messaging_tip": "Specific messaging advice for this orientation and challenge"
  }
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
        "temporality": "Present-focused — The future is NOW",
        "activity": "Simplify · Advocate · Accelerate"
    },
    "AMBIVALENT": {
        "emoji": "⚖️",
        "color": "#D68910",
        "bg": "#FEFDE7",
        "border": "#F4D03F",
        "goal": "Slow down, delay decisions, balance risks and benefits",
        "narrative": "Pragmatic Narrative",
        "temporality": "Gradual — The future is contingent",
        "activity": "Stall · Question · Delay"
    },
    "RESISTANT": {
        "emoji": "🛡️",
        "color": "#C0392B",
        "bg": "#FDEDEC",
        "border": "#E74C3C",
        "goal": "Contest the prescribed future, protect the status quo",
        "narrative": "Control Narrative",
        "temporality": "Maintenance — The future is distant",
        "activity": "Avoid · Reject · Prevent"
    },
    "EXPANDER": {
        "emoji": "🌍",
        "color": "#7D3C98",
        "bg": "#F4ECF7",
        "border": "#9B59B6",
        "goal": "Expand the prescribed future, propose alternatives",
        "narrative": "Bigger Picture Narrative",
        "temporality": "Envisioned — Change will be broader",
        "activity": "Complexify · Contest · Reroute"
    }
}

CHALLENGES = {
    "CONVOLUTED_EVALUATIONS": {
        "emoji": "🌀",
        "label": "Convoluted Evaluations",
        "color": "#2980B9",
        "bg": "#EBF5FB",
        "description": "Divergent assumptions make coherent sensemaking difficult"
    },
    "CONFRONTATIONAL_NEGOTIATIONS": {
        "emoji": "⚔️",
        "label": "Confrontational Negotiations",
        "color": "#E67E22",
        "bg": "#FEF9E7",
        "description": "Competing voices advocate, question, reject, and contest without converging"
    },
    "COMPETING_ENACTMENTS": {
        "emoji": "🔀",
        "label": "Competing Enactments",
        "color": "#8E44AD",
        "bg": "#F5EEF8",
        "description": "Acceleration, delay, prevention and rerouting pull the future in different directions"
    },
    "MIXED": {
        "emoji": "🔶",
        "label": "Multiple Challenges",
        "color": "#555",
        "bg": "#F5F5F5",
        "description": "This comment reflects elements of multiple future-making challenges"
    }
}

ACTIVITY_COLORS = {
    "SIMPLIFY": "#27AE60", "STALL": "#D68910",
    "AVOID": "#C0392B", "COMPLEXIFY": "#7D3C98",
    "ADVOCATE": "#27AE60", "QUESTION": "#D68910",
    "REJECT": "#C0392B", "CONTEST": "#7D3C98",
    "ACCELERATE": "#27AE60", "DELAY": "#D68910",
    "PREVENT": "#C0392B", "REROUTE": "#7D3C98",
    "N/A": "#AAAAAA"
}

# ─────────────────────────────────────────
# EXAMPLES (from paper + appendices)
# ─────────────────────────────────────────
EXAMPLES = {
    "— Select an example —": {"prescribed": "", "comment": ""},

    "⚡ Catalyzer — Simplify / Advocate": {
        "prescribed": "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's net-zero emissions targets",
        "comment": (
            "We are already so far behind! We need to sprint to catch up. "
            "Many industry observers believe we have already passed the tipping point "
            "where sales of electric vehicles will very rapidly overwhelm petrol and diesel cars. "
            "Once EVs are cheaper to buy than ICE cars the transition will happen fast. "
            "EVs can stand on their own merits now. We should be WORLD LEADERS in solar "
            "and battery manufacturing. Why are we not using our own minerals to make batteries "
            "for EVs on a global scale??"
        )
    },

    "⚡ Catalyzer — Accelerate (Enactment)": {
        "prescribed": "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's net-zero emissions targets",
        "comment": (
            "We have ordered two Teslas that will be delivered hopefully this year. "
            "We are selling our Prado and it looks like we are going to sell our last Toyota car. "
            "I'm 18 months into ownership, and I love this car more every day. "
            "I love leaving my garage with a full charge every morning, I love the instant acceleration, "
            "I love the quiet motors, I love that I have had zero maintenance since I drove it home. "
            "I'll never own a gas combustion engine again — not even a hybrid."
        )
    },

    "⚖️ Ambivalent — Stall / Question": {
        "prescribed": "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's net-zero emissions targets",
        "comment": (
            "I'm not against EVs. I like the idea of more power and torque and almost no maintenance. "
            "I also listen daily to several EV youtube channels and find the tech fascinating. "
            "I believe the infrastructure is not even remotely close to being where it needs to be "
            "and the battery tech still has a solid 10 years before they will replace ICE for every "
            "single new car purchase. Have you thought about what they are gonna do with all the "
            "batteries once they expire because they aren't recyclable? I'm not convinced yet. "
            "Perhaps these problems are over-exaggerated but I don't see this happening adequately "
            "in the next few years. I'm willing to change my mind if my concerns are unfounded."
        )
    },

    "⚖️ Ambivalent — Delay (Enactment)": {
        "prescribed": "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's net-zero emissions targets",
        "comment": (
            "A lot of people I know are waiting for the tech and infrastructure to be shored up "
            "before considering them. Most people I've spoken to say they'd rather wait until they "
            "got solar at their home with battery storage and bi-directional charging. "
            "Living in Outback Northwest Queensland there are no charging stations. "
            "I plan to drive my current 10 year old hybrid as long as I can. "
            "The next car I buy will probably be electric, but I'm expecting many of these issues "
            "to be resolved by then. Hopefully, by the time my car does need to be replaced, "
            "EVs are a lot cheaper and the inconveniences are worked out."
        )
    },

    "🛡️ Resistant — Avoid / Reject": {
        "prescribed": "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's net-zero emissions targets",
        "comment": (
            "This climate change stuff is getting beyond a joke! It's not about the environment, "
            "it's about money and control so we have the elite and the poor!! "
            "Zero Emissions?? Never going to happen!!! "
            "Ridiculous idea. Who are these dictating clowns? They're too expensive. "
            "They're not green considering the amount of resources it takes to produce them. "
            "No thanks, protest here we come. We get a say, this is our country not the governments'. "
            "I say freedom of choice. Politicians forcing us to go this way need to be voted out."
        )
    },

    "🛡️ Resistant — Prevent (Enactment)": {
        "prescribed": "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's net-zero emissions targets",
        "comment": (
            "I for one WILL NOT be forced into an electric vehicle and spend half my travel time "
            "charging the damn thing. My petrol car is running perfectly and at only 8 years old, "
            "it'd be stupid and wasteful to replace it. I have had ICE cars for some 37 years "
            "and have found them to be very reliable. "
            "I'll stick to my V8 and my other diesel 4x4. "
            "Travelling Australia will be a thing of the past if they push this agenda. "
            "Small towns will die without tourism."
        )
    },

    "🌍 Expander — Complexify / Contest": {
        "prescribed": "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's net-zero emissions targets",
        "comment": (
            "The embodied carbon in a new vehicle is more than the emissions that are going to "
            "be produced by the current vehicle over the course of its lifetime until it falls apart. "
            "EVs are NOT the solution. Electric trains and buses plus accessible walking and cycling "
            "infrastructure — that's what we need. Electric vehicles aren't the magic fix everyone "
            "thinks they are. Does it have to be a car? "
            "All these desperate attempts to cram cars into cities are just doomed to fail. "
            "The future is less cars, in higher density pedestrian, bike and train-orientated "
            "urban environments. We need to stop building for cars and more for humans."
        )
    },

    "🌍 Expander — Reroute (Enactment)": {
        "prescribed": "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's net-zero emissions targets",
        "comment": (
            "I uprooted my life and moved from the Sunshine Coast to Melbourne with some of my "
            "strongest reasoning being the ability to use public transport, ride a bike around "
            "and use a car as little as possible. "
            "We tend to do most of our shopping by bike rather than with the ute. "
            "I am at the moment on a waiting list for a new electric cargo bike. "
            "EVs for me is still not the solution. The solution is actually degrowth — "
            "going back to supporting local businesses so we don't have to travel so much. "
            "The plan is to extract maximum value out of the current vehicle until it is "
            "no longer functional. Not even looking at a replacement electric car."
        )
    },
}

# ─────────────────────────────────────────
# FUNCTIONS
# ─────────────────────────────────────────

def analyze_comment(prescribed_future: str, comment: str, api_key: str) -> dict:
    client = openai.OpenAI(api_key=api_key)
    user_message = f"""
PRESCRIBED FUTURE:
{prescribed_future}

CONSUMER COMMENT TO ANALYZE:
{comment}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    return json.loads(response.choices[0].message.content)


def activity_card(label: str, icon: str, activity_type: str, is_active: bool) -> str:
    color = ACTIVITY_COLORS.get(activity_type, "#AAA")
    bg = "#ffffff" if is_active else "#f9f9f9"
    border = color if is_active else "#dddddd"
    text_color = "#333333" if is_active else "#aaaaaa"
    return f"""
    <div style="background:{bg};border:2px solid {border};border-radius:8px;
                padding:14px;text-align:center;min-height:90px;">
        <div style="font-size:18px;">{icon}</div>
        <strong style="color:{text_color};font-size:12px;">{label}</strong><br>
        <span style="color:{color};font-weight:bold;font-size:15px;">{activity_type}</span>
    </div>
    """


def show_results(result: dict, prescribed_future: str):
    orientation = result.get("orientation", "").upper().strip()
    challenge = result.get("primary_challenge", "MIXED").upper().strip()

    cfg = ORIENTATIONS.get(orientation)
    chg = CHALLENGES.get(challenge, CHALLENGES["MIXED"])

    if not cfg:
        st.error(f"Could not recognize orientation: '{orientation}'")
        return

    # ── PRESCRIBED FUTURE BANNER ──
    st.markdown(f"""
    <div style="background:#EBF5FB;border-left:5px solid #2980B9;
                border-radius:8px;padding:12px 18px;margin-bottom:16px;">
        <strong style="color:#2980B9;">📌 Prescribed Future Analyzed:</strong><br>
        <em style="color:#333;">{prescribed_future}</em>
    </div>
    """, unsafe_allow_html=True)

    # ── ORIENTATION + CHALLENGE CARDS ──
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div style="background:{cfg['bg']};border-left:6px solid {cfg['border']};
                    border-radius:10px;padding:18px 22px;min-height:160px;">
            <h3 style="color:{cfg['color']};margin:0;font-size:24px;">
                {cfg['emoji']} {orientation}
            </h3>
            <p style="color:#666;margin:6px 0 4px;font-size:13px;">
                <strong>Confidence:</strong> {result.get('confidence','N/A')}
            </p>
            <p style="color:#777;margin:3px 0;font-size:12px;">
                📖 <strong>Narrative:</strong> {cfg['narrative']}
            </p>
            <p style="color:#777;margin:3px 0;font-size:12px;">
                ⏱️ <strong>Temporality:</strong> {cfg['temporality']}
            </p>
            <p style="color:#777;margin:3px 0;font-size:12px;">
                🎯 <strong>Goal:</strong> {cfg['goal']}
            </p>
            <p style="color:#999;margin:4px 0 0;font-size:11px;">
                Activities: {cfg['activity']}
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background:{chg['bg']};border-left:6px solid {chg['color']};
                    border-radius:10px;padding:18px 22px;min-height:160px;">
            <h3 style="color:{chg['color']};margin:0;font-size:22px;">
                {chg['emoji']} {chg['label']}
            </h3>
            <p style="color:#666;margin:6px 0 4px;font-size:13px;">
                <strong>Primary Future-Making Challenge</strong>
            </p>
            <p style="color:#777;margin:3px 0;font-size:12px;">
                {chg['description']}
            </p>
            <p style="color:#888;margin:8px 0 0;font-size:12px;font-style:italic;">
                "{result.get('challenge_explanation','')[:150]}..."
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── EXPLANATION & SIGNALS ──
    st.markdown("##### 💡 Why this orientation?")
    st.write(result.get("explanation", "—"))

    st.markdown("##### 🔍 Key Signals Detected in the Comment")
    st.info(result.get("key_signals", "—"))

    # ── ACTIVITIES ──
    st.markdown("---")
    st.markdown("##### 🔄 Future-Making Activities")

    activities = result.get("future_making_activities", [])
    eval_type  = result.get("evaluation_type", "N/A")
    neg_type   = result.get("negotiation_type", "N/A")
    enact_type = result.get("enactment_type", "N/A")

    c1, c2, c3 = st.columns(3)
    c1.markdown(activity_card("📊 EVALUATION",  "📊", eval_type,  "EVALUATION"  in activities), unsafe_allow_html=True)
    c2.markdown(activity_card("💬 NEGOTIATION", "💬", neg_type,   "NEGOTIATION" in activities), unsafe_allow_html=True)
    c3.markdown(activity_card("⚙️ ENACTMENT",   "⚙️", enact_type, "ENACTMENT"   in activities), unsafe_allow_html=True)

    st.caption(result.get("activity_explanation", ""))

    # ── PROFILE ROW ──
    st.markdown("---")
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown("**😊 Emotions Detected**")
        st.caption(result.get("dominant_emotions", "—"))
    with e2:
        st.markdown("**📖 Dominant Narrative**")
        st.caption(result.get("dominant_narrative", "—"))
    with e3:
        st.markdown("**⏱️ Temporality**")
        st.caption(result.get("temporality", "—"))

    # ── CHALLENGE DEEP DIVE ──
    st.markdown("---")
    st.markdown(f"##### {chg['emoji']} Challenge Detail: {chg['label']}")
    st.write(result.get("challenge_explanation", "—"))

    # ── IMPLICATIONS TABS ──
    st.markdown("---")
    st.markdown("## 📋 Policy & Managerial Implications")

    policy_tab, manager_tab = st.tabs(["🏛️ Policy Roadmap", "🏢 Managerial Roadmap"])

    with policy_tab:
        policy = result.get("policy_recommendations", {})

        st.markdown(f"**📍 Most Relevant Step:** {policy.get('step','—')}")
        st.markdown(f"**🎯 Policy Objective:** {policy.get('objective','—')}")

        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown("**🔧 Recommended Policy Instruments**")
            for inst in policy.get("instruments", []):
                st.markdown(f"• {inst}")
        with pc2:
            st.markdown("**➡️ Additional Actions**")
            for action in policy.get("additional_actions", []):
                st.markdown(f"→ {action}")

        with st.expander("📍 Full Policy Roadmap (7 Steps)"):
            st.markdown("""
| Step | Action |
|:----:|--------|
| **1** | **Determine the prescribed future** — Make explicit what the intervention seeks to prescribe |
| **2** | **Map future-making orientations** — Identify how people evaluate, negotiate, and enact |
| **3** | **Identify key future-making challenges** — Which of the three are most pressing? |
| **4** | **Implement support initiatives** — Match instruments to each orientation |
| **5** | **Facilitate enactment** — Provide infrastructure and build capabilities |
| **6** | **Measure multiple outcomes** — Accuracy, fairness, who benefits, who is excluded |
| **7** | **Revise intervention** — Treat the prescribed future as revisable |
            """)

    with manager_tab:
        manager = result.get("manager_recommendations", {})

        st.markdown(f"**📍 Most Relevant Step:** {manager.get('step','—')}")
        st.markdown(f"**🎯 Managerial Objective:** {manager.get('objective','—')}")

        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown("**🔧 Recommended Interventions**")
            for interv in manager.get("interventions", []):
                st.markdown(f"• {interv}")
        with mc2:
            st.markdown("**⚠️ Avoid**")
            for av in manager.get("avoid", []):
                st.markdown(f"✗ {av}")

        st.markdown("**💬 Messaging Tip**")
        st.info(manager.get("messaging_tip", "—"))

        with st.expander("📍 Full Managerial Roadmap (6 Steps)"):
            st.markdown("""
| Step | Action |
|:----:|--------|
| **1** | **Determine the prescribed future** — Define by the future it prescribes, not only its technical features |
| **2** | **Consider future-making orientations** — Use narratives, goals, emotions, temporalities |
| **3** | **Identify key future-making challenges** — Convoluted evaluations, confrontational negotiations, competing enactments |
| **4** | **Select orientation-sensitive response** — Match objectives and instruments to each orientation |
| **5** | **Match messaging to challenges** — Avoid universal claims; communicate achievements AND limitations |
| **6** | **Support consumers through enactment** — Onboarding, workflows, escalation, training, appeals |
            """)

    # ── SOURCE ──
    st.markdown("---")
    st.caption(
        "📚 *Journal of Marketing* | "
        "[Read the paper](REPLACE_WITH_YOUR_DOI_OR_URL)"
    )


# ─────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────

def main():
    st.title("🔮 Future-Making Orientation Analyzer")
    st.markdown("""
    Identify **consumer orientations**, **future-making activities**, **challenges**,
    and get tailored **policy & managerial recommendations** — all from a single comment.

    *Based on: "Futures in the Making" — Journal of Marketing*
    """)
    st.divider()

    # ── API KEY ──
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

    st.markdown("---")

    # ── STEP 1: PRESCRIBED FUTURE ──
    st.markdown("### 📌 Step 1 — Define the Prescribed Future")
    st.caption(
        "What future does the intervention, policy, or strategy seek to bring about? "
        "Be specific about context and goals."
    )

    prescribed_future = st.text_area(
        "prescribed_future",
        height=85,
        placeholder=(
            "e.g., 'Transition all vehicles to Zero Emission Vehicles (EVs) "
            "to achieve Australia's net-zero emissions targets by 2035'   OR   "
            "'Mandatory adoption of AI-driven hiring tools in public sector HR'   OR   "
            "'Shift to plant-based diets to reduce agricultural emissions by 50%'"
        ),
        label_visibility="collapsed"
    )

    st.markdown("---")

    # ── STEP 2: COMMENT INPUT ──
    st.markdown("### 💬 Step 2 — Enter a Consumer Comment")

    input_method = st.radio(
        "Input method:",
        ["📝 Type or paste text", "📂 Upload a .txt file"],
        horizontal=True
    )

    comment = ""

    if input_method == "📝 Type or paste text":
        selected_ex = st.selectbox(
            "Or choose a built-in example from the paper:",
            list(EXAMPLES.keys())
        )

        ex_data = EXAMPLES.get(selected_ex, {"prescribed": "", "comment": ""})
        comment_default = ex_data["comment"]
        suggested_pf    = ex_data["prescribed"]

        if selected_ex != "— Select an example —" and suggested_pf:
            st.info(f"💡 **Suggested prescribed future:** *{suggested_pf}*")
            if st.button("↑ Use this as my prescribed future", type="secondary"):
                st.session_state["pf_prefill"] = suggested_pf
                st.rerun()

        comment = st.text_area(
            "Comment:",
            value=comment_default,
            height=200,
            placeholder="Paste or type a consumer comment here...",
            label_visibility="collapsed"
        )

    else:
        uploaded_file = st.file_uploader(
            "Upload .txt file:",
            type=["txt"],
            help="Plain text. For multiple comments separate them with a blank line."
        )
        if uploaded_file:
            comment = uploaded_file.read().decode("utf-8")
            st.success(f"✅ Uploaded: {len(comment):,} characters")
            with st.expander("Preview"):
                st.text(comment[:600] + ("..." if len(comment) > 600 else ""))

    # Use pre-filled prescribed future if set via session state
    if "pf_prefill" in st.session_state:
        prescribed_future = st.session_state.pop("pf_prefill")

    # ── ANALYZE BUTTON ──
    st.markdown("---")

    ready = bool(api_key and comment.strip() and prescribed_future.strip())

    if not prescribed_future.strip():
        st.warning("⚠️ Please define the prescribed future in Step 1.")
    elif not comment.strip():
        st.warning("⚠️ Please enter a comment in Step 2.")

    if st.button(
        "🔍 Analyze Orientation",
        type="primary",
        use_container_width=True,
        disabled=not ready
    ):
        with st.spinner("Analyzing..."):
            try:
                result = analyze_comment(
                    prescribed_future.strip(),
                    comment.strip(),
                    api_key
                )
                st.divider()
                st.markdown("## 🧠 Analysis Results")
                show_results(result, prescribed_future.strip())

            except openai.AuthenticationError:
                st.error("❌ Invalid API key. Please check your OpenAI key.")
            except openai.RateLimitError:
                st.error("⏳ Rate limit reached. Please wait a moment.")
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")
                st.code(str(e))


if __name__ == "__main__":
    main()
