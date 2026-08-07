import streamlit as st
import openai
import json

# ─────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Future-Making Orientation Analyzer",
    page_icon="🔮",
    layout="wide"
)

# ─────────────────────────────────────────
# CITATION CONSTANTS
# ─────────────────────────────────────────
PAPER_TITLE   = "Futures in the Making: How Consumers Respond to Future-Oriented Interventions"
PAPER_JOURNAL = "Journal of Marketing"

# ─────────────────────────────────────────
# SYSTEM PROMPT — uses exact coding criteria from the paper
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an expert qualitative coder applying the Future-Making framework from the paper
"Futures in the Making: How Consumers Respond to Future-Oriented Interventions"
published in the Journal of Marketing.

You will be given:
1. A PRESCRIBED FUTURE: the future that a policy or market intervention seeks to bring about
2. A CONSUMER COMMENT: text to analyze

Your task is to identify:
  A) The MAIN future-making activity (one primary activity)
  B) The MAIN future-making orientation (one primary orientation)
  C) The primary future-making challenge this comment contributes to
  D) Policy and managerial implications

Apply the following coding criteria rigorously and precisely.

════════════════════════════════════════════════════════════════
A. FUTURE-MAKING ACTIVITIES — Select the ONE primary activity
════════════════════════════════════════════════════════════════

Select the activity that is MOST dominant in the comment.
A comment may touch on more than one, but you must identify the primary one.

─── EVALUATION ───────────────────────────────────────────────
Operational definition:
  References to how consumers made sense of the prescribed future.

Coding criteria (ALL must apply to classify as Evaluation):
  • Contains a claim or judgment about what the future means,
    whether it is likely or desirable, or what benefits, costs,
    risks, assumptions, and trade-offs it entails.
  • The assessment must have an identifiable object: EVs,
    infrastructure, regulation, environmental impacts, or the
    proposed transition timeline.

Sub-types by orientation:
  SIMPLIFY  (Catalyzer)  — narrows focus, treats difficulties as
    temporary, downplays complexity or risks
  STALL     (Ambivalent) — careful consideration, information gathering,
    weighing pros and cons without deciding
  AVOID     (Resistant)  — perceives transition as unnecessary or
    manipulative; emphasis on preserving existing practices
  COMPLEXIFY (Expander)  — zooms out to systemic trade-offs, unintended
    consequences, and alternative framings

Example: "I am far from being anti EV (I want one!) but I am also
trying to weigh up all the facts."

─── NEGOTIATION ──────────────────────────────────────────────
Operational definition:
  References to how consumers compared, contested, defended,
  or expanded preferred futures.

Coding criteria (ALL must apply to classify as Negotiation):
  • Makes a RELATIONAL claim: responds to another position,
    compares alternative futures, challenges or defends a
    proposed pathway, attributes responsibility or authority,
    or attempts to persuade others regarding what future
    should be pursued.

Sub-types by orientation:
  ADVOCATE  (Catalyzer)  — recruits others, calls for stronger policy,
    frames the prescribed future as a collective endeavor
  QUESTION  (Ambivalent) — polite skepticism, asks for proof of
    feasibility, affordability, social fairness
  REJECT    (Resistant)  — challenges collective attempts to bring the
    prescribed future into being; frames adoption as coercive imposition
  CONTEST   (Expander)   — contests the scope of the prescribed future;
    proposes broader or alternative futures

Example: "We should not place all our attention on EVs now as most of
the electricity used to charge them is from burning coal. We should
transition to hybrid vehicles instead of EVs until 2030."

─── ENACTMENT ────────────────────────────────────────────────
Operational definition:
  References to how consumers gave form to futures through imagined,
  planned, or actual changes in everyday practices and their material
  arrangements.

Coding criteria (ALL must apply to classify as Enactment):
  • Specifies what the consumer does, intends to do, expects to do,
    or imagines doing in practice.
  • At least ONE practice element must be identifiable:
    — an action or routine
    — a material arrangement or technology
    — a competence
    — a temporally situated commitment
  Examples of practice elements: purchasing or retaining a vehicle,
  installing or using chargers, changing travel routines, delaying
  replacement, cycling, or using public transport.

Sub-types by orientation:
  ACCELERATE (Catalyzer)  — purchases EVs, divests ICE, installs chargers,
    publicly normalizes transition
  DELAY      (Ambivalent) — continues ICE use, monitors EV market, waits
    for conditions to improve, considers hybrids
  PREVENT    (Resistant)  — explicitly retains ICE vehicles, encourages
    others to resist, refuses change
  REROUTE    (Expander)   — adopts cargo bikes, uses public transport,
    relocates to reduce car dependence, maintains ICE only for necessity

Example: "Bought our first EV largely for the environment, partly for
fuel cost savings. Bought our second EV because they're just far better
cars to own and drive."

════════════════════════════════════════════════════════════════
B. FUTURE-MAKING ORIENTATIONS — Select the ONE primary orientation
════════════════════════════════════════════════════════════════

Select the orientation that BEST fits the comment as a whole.
Apply ALL four dimensions: narrative, goal, emotions, temporality,
and empirical indicators.

─── CATALYZER ────────────────────────────────────────────────
Main narrative:
  Urgency narrative. Climate change requires rapid action; EV transition
  is necessary, feasible, and already gaining momentum. Technological or
  infrastructural difficulties are treated as temporary, manageable,
  or outweighed by the benefits.

Future-making goal:
  Accelerate change toward the prescribed future. The preferred future
  is closely aligned with the EV-dominant future prescribed by
  policymakers and market actors.

Emotions:
  Utopian optimism; enthusiasm; confidence; pride.

Temporality:
  Present-focused: the future is close and change is already occurring
  or must occur immediately.

Empirical coding indicators:
  References to urgency, momentum, tipping points, inevitability,
  technological progress, and the demonstrated feasibility of EV adoption.
  Consumers simplify trade-offs, advocate for faster change, and describe
  practices that normalize or accelerate EV adoption.
  Typical temporal markers: "now," "rapidly," "already," "time to,"
  "let's get moving."

─── AMBIVALENT ───────────────────────────────────────────────
Main narrative:
  Pragmatic narrative. The desirability of the EV future is assessed
  against everyday feasibility: price, range, charging access, servicing,
  battery performance, electricity supply, resale value, and compatibility
  with household routines.

Future-making goal:
  Slow or stage movement toward the prescribed future. Consumers do not
  necessarily oppose EV adoption, but delay decisions while balancing
  benefits, risks, and unresolved practical conditions.

Emotions:
  Curiosity; caution; anxiety; frustration; conditional optimism.

Temporality:
  Gradual and contingent: change may occur, but its timing depends on
  infrastructure, affordability, technological development, and the
  actions of other market actors.

Empirical coding indicators:
  Conditional support; simultaneous recognition of benefits and drawbacks;
  information seeking; unanswered questions; waiting for prices or
  technology to improve; preference for hybrids or transitional
  arrangements; imagined adoption only under particular conditions.
  Typical linguistic markers: "but," "if," "when," "not yet,"
  "hopefully," "I'm willing to change my mind."

─── RESISTANT ────────────────────────────────────────────────
Main narrative:
  Control narrative. EV interventions are framed as coercive, inequitable,
  ideologically motivated, environmentally misleading, or imposed by
  governments, elites, and corporations. Existing technologies and
  practices are defended as more reliable, affordable, autonomous,
  or appropriate to current conditions.

Future-making goal:
  Contest the prescribed future and protect the status quo. Consumers
  seek to preserve ICE-based mobility practices and resist policy or
  market pressures to change them.

Emotions:
  Pessimism; anger; anxiety; fear; defiance; distrust.

Temporality:
  Maintenance-oriented: the preferred future reproduces the present,
  while the prescribed future is represented as distant, implausible,
  or something that should be prevented.

Empirical coding indicators:
  Categorical rejection of EVs or transition targets; distrust of
  policymakers, experts, industry, or environmental claims; defense
  of consumer freedom and existing practices; accusations of manipulation
  or social control; commitments to retain ICE vehicles.
  Typical markers: "forced," "agenda," "control," "freedom," "never,"
  "stick with."

─── EXPANDER ─────────────────────────────────────────────────
Main narrative:
  Bigger-picture narrative. The EV intervention is situated within wider
  systems of production, consumption, urban design, inequality, resource
  extraction, and car dependence. The relevant question shifts from
  "How can cars become electric?" to "How should mobility and consumption
  be reorganized?"

Future-making goal:
  Expand and reroute the prescribed future. Consumers regard EV adoption
  as insufficient and propose alternative pathways involving reduced car
  dependence, public transportation, active travel, shared mobility,
  urban redesign, repair, longevity, or degrowth.

Emotions:
  Dystopian optimism; concern; hope; critical urgency.

Temporality:
  Envisioned and system-oriented: broader change must begin in the present,
  but the preferred future extends beyond the temporal and substantive
  boundaries of the prescribed EV transition.

Empirical coding indicators:
  Zooming out from EV characteristics to systemic consequences; challenging
  the assumption that private cars must remain central; identifying rebound
  effects or unintended consequences; proposing alternative mobility
  arrangements; describing reduced-car practices.
  Typical formulations: "EVs are not enough," "bigger picture," "less cars,"
  "public transport," "buy less," "does it have to be a car?"

════════════════════════════════════════════════════════════════
C. FUTURE-MAKING CHALLENGES
════════════════════════════════════════════════════════════════

CONVOLUTED_EVALUATIONS:
  When consumers with different orientations assess the prescribed future
  through divergent assumptions, evidence, and temporal horizons,
  making coherent sensemaking difficult.
  Produced when: some simplify, others stall, avoid, or complexify.

CONFRONTATIONAL_NEGOTIATIONS:
  When consumers simultaneously advocate for, question, reject, or contest
  the prescribed future, widening divides rather than converging.

COMPETING_ENACTMENTS:
  When some consumers accelerate while others prevent, delay, or reroute,
  creating divergence and volatility that hinders progress toward the
  prescribed future.

════════════════════════════════════════════════════════════════
D. ROADMAPS
════════════════════════════════════════════════════════════════

POLICY ROADMAP (Figure 3 — 7 steps):
  Step 1: Determine the prescribed future
  Step 2: Map future-making orientations
  Step 3: Identify key future-making challenges
  Step 4: Implement orientation-matched support:
    CATALYZER — enable responsible acceleration; instruments: regulatory
      sandboxes; independent evaluation; mandatory reporting of failures;
      exit criteria and powers to pause or reverse.
    AMBIVALENT — convert uncertainty into explicit conditions;
      instruments: public impact assessments; staged authorization;
      citizen juries; public registers; human-service alternatives.
    RESISTANT — protect rights and restore legitimacy;
      instruments: prohibitions on unacceptable uses; appeal and
      human-review rights; independent audits; moratoria.
    EXPANDER — broaden the policy focus;
      instruments: citizen assemblies; public-interest funding;
      data trusts; competition policy; alternative governance models.
  Step 5: Facilitate enactment — infrastructure and capability building
  Step 6: Measure multiple outcomes
  Step 7: Revise intervention — treat the prescribed future as revisable

MANAGERIAL ROADMAP (Figure 4 — 6 steps):
  Step 1: Determine the prescribed future
  Step 2: Consider future-making orientations (not segments)
  Step 3: Identify key future-making challenges
  Step 4: Select orientation-sensitive response:
    CATALYZER — convert enthusiasm into responsible experimentation;
      interventions: governed pilots, evidence documentation, peer learning,
      explicit reporting of limitations.
      Avoid: inevitability claims; treating early adopters as universal proof.
    AMBIVALENT — convert uncertainty into addressable conditions;
      interventions: sandboxes, comparison tools, staged adoption,
      human assistance, transparent performance evidence.
      Avoid: pressure and artificial urgency; framing hesitation as ignorance.
    RESISTANT — restore autonomy, legitimacy, accountability;
      interventions: consultation, opt-outs, human review, independent audits,
      protections against material harms.
      Avoid: "there is no alternative"; ridicule; hidden automation.
    EXPANDER — incorporate systemic critique;
      interventions: participatory design, futures workshops, broader
      impact evaluation, alternative governance or business models.
      Avoid: presenting the focal offering as a complete solution;
      dismissing critique as out of scope.
  Step 5: Match messaging to challenges — avoid universal frames;
    communicate achievements AND limitations.
  Step 6: Support consumers through enactment touchpoints.

════════════════════════════════════════════════════════════════
OUTPUT FORMAT — Return ONLY valid JSON
════════════════════════════════════════════════════════════════

{
  "prescribed_future_acknowledged": "Brief restatement of the prescribed future",

  "main_activity": "EVALUATION | NEGOTIATION | ENACTMENT",
  "activity_subtype": "SIMPLIFY | STALL | AVOID | COMPLEXIFY | ADVOCATE | QUESTION | REJECT | CONTEST | ACCELERATE | DELAY | PREVENT | REROUTE",
  "activity_rationale": "Explain which coding criterion from the table is met and cite the specific phrase(s) from the comment that triggered this classification",
  "secondary_activities": ["list", "of", "other", "activities", "present", "if", "any"],

  "main_orientation": "CATALYZER | AMBIVALENT | RESISTANT | EXPANDER",
  "orientation_confidence": "HIGH | MEDIUM | LOW",
  "orientation_rationale": "Identify which empirical indicators are present, which emotions are detected, what temporality is expressed, and cite specific phrases from the comment",
  "narrative_identified": "Name of the dominant narrative and a brief description of how it appears in the comment",
  "dominant_emotions": "Comma-separated list of emotions detected",
  "temporality_expressed": "How this person perceives the timing and nature of the future",

  "primary_challenge": "CONVOLUTED_EVALUATIONS | CONFRONTATIONAL_NEGOTIATIONS | COMPETING_ENACTMENTS | MIXED",
  "challenge_rationale": "Explain which challenge this comment contributes to and why, using the challenge definitions",

  "policy_recommendations": {
    "step": "Most relevant policy roadmap step (e.g., Step 4 — Implement support initiatives)",
    "objective": "Specific policy objective for this orientation",
    "instruments": ["instrument 1", "instrument 2", "instrument 3"],
    "additional_actions": ["action 1", "action 2"]
  },
  "manager_recommendations": {
    "step": "Most relevant managerial roadmap step",
    "objective": "Specific managerial objective for this orientation",
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
        "goal": "Accelerate change toward the prescribed future",
        "narrative": "Urgency Narrative",
        "temporality": "Present-focused — The future is NOW",
        "activities": "Simplify · Advocate · Accelerate"
    },
    "AMBIVALENT": {
        "emoji": "⚖️",
        "color": "#D68910",
        "bg": "#FEFDE7",
        "border": "#F4D03F",
        "goal": "Slow or stage movement; delay decisions; balance risks and benefits",
        "narrative": "Pragmatic Narrative",
        "temporality": "Gradual — The future is contingent",
        "activities": "Stall · Question · Delay"
    },
    "RESISTANT": {
        "emoji": "🛡️",
        "color": "#C0392B",
        "bg": "#FDEDEC",
        "border": "#E74C3C",
        "goal": "Contest the prescribed future; protect the status quo",
        "narrative": "Control Narrative",
        "temporality": "Maintenance — The future is distant / should not happen",
        "activities": "Avoid · Reject · Prevent"
    },
    "EXPANDER": {
        "emoji": "🌍",
        "color": "#7D3C98",
        "bg": "#F4ECF7",
        "border": "#9B59B6",
        "goal": "Expand and reroute the prescribed future; propose alternatives",
        "narrative": "Bigger Picture Narrative",
        "temporality": "Envisioned — Change will be broader than prescribed",
        "activities": "Complexify · Contest · Reroute"
    }
}

CHALLENGES = {
    "CONVOLUTED_EVALUATIONS": {
        "emoji": "🌀",
        "label": "Convoluted Evaluations",
        "color": "#2980B9",
        "bg": "#EBF5FB",
        "description": "Divergent assumptions, evidence, and temporal horizons make coherent sensemaking difficult"
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

ACTIVITY_META = {
    "EVALUATION":  {
        "icon": "📊", "color": "#2980B9", "bg": "#EBF5FB",
        "definition": "Claim or judgment about what the prescribed future means, whether it is likely or desirable, what benefits/costs/risks/trade-offs it entails. Must have an identifiable object (EVs, infrastructure, regulation, environment, timeline).",
        "subtypes": {
            "SIMPLIFY":    ("⚡ Catalyzer", "#27AE60"),
            "STALL":       ("⚖️ Ambivalent", "#D68910"),
            "AVOID":       ("🛡️ Resistant",  "#C0392B"),
            "COMPLEXIFY":  ("🌍 Expander",   "#7D3C98"),
        }
    },
    "NEGOTIATION": {
        "icon": "💬", "color": "#E67E22", "bg": "#FEF9E7",
        "definition": "Relational claim: responds to another position, compares futures, challenges or defends a pathway, attributes responsibility, or attempts to persuade others about what future should be pursued.",
        "subtypes": {
            "ADVOCATE":  ("⚡ Catalyzer", "#27AE60"),
            "QUESTION":  ("⚖️ Ambivalent", "#D68910"),
            "REJECT":    ("🛡️ Resistant",  "#C0392B"),
            "CONTEST":   ("🌍 Expander",   "#7D3C98"),
        }
    },
    "ENACTMENT":   {
        "icon": "⚙️", "color": "#8E44AD", "bg": "#F5EEF8",
        "definition": "Specifies what the consumer does, intends, expects, or imagines doing in practice. At least one practice element must be identifiable: an action/routine, a material arrangement/technology, a competence, or a temporally situated commitment.",
        "subtypes": {
            "ACCELERATE": ("⚡ Catalyzer", "#27AE60"),
            "DELAY":      ("⚖️ Ambivalent", "#D68910"),
            "PREVENT":    ("🛡️ Resistant",  "#C0392B"),
            "REROUTE":    ("🌍 Expander",   "#7D3C98"),
        }
    },
}

# ─────────────────────────────────────────
# PRESCRIBED FUTURE — shared for all EV examples
# ─────────────────────────────────────────
PF_EV = (
    "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's "
    "net-zero emissions targets, as prescribed by Australia's National Electric "
    "Vehicle Strategy (2023)"
)

# ─────────────────────────────────────────
# EXAMPLES — 12 entries, one per orientation × activity
# All quotes drawn directly from the paper and web appendices
# ─────────────────────────────────────────
EXAMPLES = {
    "— Select an example from the paper —": {
        "prescribed": "", "comment": "",
        "activity": "", "subtype": "", "orientation": ""
    },

    # ══════ ⚡ CATALYZER ══════
    "⚡ CATALYZER  |  📊 Evaluation  →  Simplify": {
        "prescribed": PF_EV,
        "activity":   "EVALUATION",
        "subtype":    "SIMPLIFY",
        "orientation":"CATALYZER",
        "comment": (
            "There's no discussion about whether they're better for the environment. "
            "The math and science is extremely clear and it's ridiculous to even compare them "
            "with how much better EVs are. "
            "Every EV doesn't need its own charging place. If you got one that's great! "
            "If you haven't got one that's not the end of the world. Most will charge in public "
            "chargers weekly, while we shop/dine/work just like we fill up petrol. "
            "When it becomes unsustainable financially to own an ICE car, people will start to "
            "make room for EV. "
            "Once EVs are cheaper to buy than ICE cars the transition will happen fast. "
            "Many industry observers believe we have already passed the tipping point where sales "
            "of electric vehicles will very rapidly overwhelm petrol and diesel cars. "
            "EVs can stand on their own merits now."
        )
    },
    "⚡ CATALYZER  |  💬 Negotiation  →  Advocate": {
        "prescribed": PF_EV,
        "activity":   "NEGOTIATION",
        "subtype":    "ADVOCATE",
        "orientation":"CATALYZER",
        "comment": (
            "We are already so far behind! We need to sprint to catch up. "
            "We should be WORLD LEADERS in solar and battery manufacturing. "
            "Why are we not using our own minerals to make batteries for EVs on a global scale?? "
            "#ClimateCrisis is real. It's time to look at #solarenergy and #ElectricVehicles "
            "not the energy sources of the past like #fossilfuels. "
            "We need to act on transport emissions as quickly as possible. "
            "People are still buying new ICE vehicles due to the lack of choice of Electric Vehicles. "
            "Australia has demonstrated that it has an appetite for EVs, so let's get moving. "
            "Climate change is an urgent threat, and we need to accelerate the decarbonisation "
            "of transport quickly and efficiently. Let's lift the ambition."
        )
    },
    "⚡ CATALYZER  |  ⚙️ Enactment  →  Accelerate": {
        "prescribed": PF_EV,
        "activity":   "ENACTMENT",
        "subtype":    "ACCELERATE",
        "orientation":"CATALYZER",
        "comment": (
            "We have ordered two Teslas that will be delivered hopefully this year. "
            "We are selling our Prado and it looks like we are going to sell our last Toyota car. "
            "Guess we will not be the only ones leaving Toyota behind. "
            "Our family has been living with an EV and a PHEV for 3 years and they are fantastic. "
            "Road trips up and down the East Coast are simple in a Tesla — with superchargers "
            "it is easy, just a stop every 2.5 hours or so. "
            "Bought our first EV largely for the environment, partly for fuel cost savings. "
            "Bought our second EV because they're just far better cars to own and drive. "
            "Proud owner of a Model 3. I'll never own a gas combustion engine again — not even a hybrid."
        )
    },

    # ══════ ⚖️ AMBIVALENT ══════
    "⚖️ AMBIVALENT  |  📊 Evaluation  →  Stall": {
        "prescribed": PF_EV,
        "activity":   "EVALUATION",
        "subtype":    "STALL",
        "orientation":"AMBIVALENT",
        "comment": (
            "I'm not against EVs. I like the idea of more power and torque and almost no maintenance. "
            "I also listen daily to several EV YouTube channels and find the tech fascinating. "
            "I believe the infrastructure is not even remotely close to being where it needs to be "
            "for today, let alone in 10 years. "
            "I am far from being anti EV — I want one! — but I am also trying to weigh up all the facts. "
            "I'm not convinced yet that full EVs are the way to go. They seem to have quite a few "
            "problems, you know, battery disposal and other things. "
            "Range anxiety has been replaced by charger anxiety. "
            "Will the charger be working when I get there? Will the charger exist where I want to be? "
            "Perhaps these problems will eventually be resolved with improvements in technology. "
            "I just don't see this happening adequately in the next few years. "
            "I'm willing to change my mind if my concerns are unfounded."
        )
    },
    "⚖️ AMBIVALENT  |  💬 Negotiation  →  Question": {
        "prescribed": PF_EV,
        "activity":   "NEGOTIATION",
        "subtype":    "QUESTION",
        "orientation":"AMBIVALENT",
        "comment": (
            "Have you thought about what they are gonna do with all the batteries once they expire "
            "because they aren't recyclable? "
            "To legislate in their favour is a further disadvantage to those already struggling. "
            "We rely on our trusty old Corollas to get to medical appointments and job interviews, "
            "and keeping them maintained is a struggle. "
            "So where do we get the $50k to buy the cheapest new EV? "
            "It will not be possible for us to make the transition until a huge number of second hand "
            "EVs hit the market. "
            "We need to invest in infrastructure but at the same time not put all eggs in the one basket. "
            "We should not place all our attention on EVs now as most of the electricity used to charge "
            "them is from burning coal. We should transition to hybrid vehicles instead of EVs until 2030. "
            "It's doing my head in trying to decide on a car that will last me another 20 years. "
            "Some say it will be a very long time before Australia fully embraces EV cars due to the distance."
        )
    },
    "⚖️ AMBIVALENT  |  ⚙️ Enactment  →  Delay": {
        "prescribed": PF_EV,
        "activity":   "ENACTMENT",
        "subtype":    "DELAY",
        "orientation":"AMBIVALENT",
        "comment": (
            "A lot of people I know are waiting for the tech and infrastructure to be shored up "
            "before considering them. Most people I've spoken to say they'd rather wait until they "
            "got solar at their home with battery storage and bi-directional charging. "
            "Or once the range is more efficient and there are more opportunities to charge in public "
            "for a shorter amount of time. It seems pretty valid to me — I think it's only a matter of time. "
            "Just bought a new petrol car as the infrastructure still isn't in place. "
            "I think I'll be running my 12 year old Subaru Outback a bit longer! "
            "I plan to drive my current 10 year old hybrid as long as I can. "
            "The next car I buy will probably be electric, but I'm expecting many of these issues "
            "to be resolved by then. Until the charging infrastructure improves drastically, "
            "perhaps hybrids are the way to go until then."
        )
    },

    # ══════ 🛡️ RESISTANT ══════
    "🛡️ RESISTANT  |  📊 Evaluation  →  Avoid": {
        "prescribed": PF_EV,
        "activity":   "EVALUATION",
        "subtype":    "AVOID",
        "orientation":"RESISTANT",
        "comment": (
            "This climate change stuff is getting beyond a joke! "
            "It's not about the environment, it's about money and control. "
            "Zero Emissions?? Never going to happen!!! "
            "Electric vehicles are not the solution — for Australia to take this up we are going to have to "
            "increase mining of precious minerals at a considerable amount, which in itself will contribute "
            "to greenhouse gases. "
            "The current electricity infrastructure can't keep up with the demand now, let alone if everyone "
            "in inner city want electric cars being recharged in high rise complexes. "
            "I feel this is a lazy policy just appealing to city people and is just going to result in "
            "expensive car prices. "
            "EV and hybrid technology has a long way to go especially here in Australia. "
            "Petrol and diesel vehicles will be around for many decades to come doing the jobs that EVs "
            "and hybrids just can't do. Electric vehicles are not the future, just a muddle point."
        )
    },
    "🛡️ RESISTANT  |  💬 Negotiation  →  Reject": {
        "prescribed": PF_EV,
        "activity":   "NEGOTIATION",
        "subtype":    "REJECT",
        "orientation":"RESISTANT",
        "comment": (
            "No thanks, protest here we come. We get a say, this is our country not the governments'. "
            "I say freedom of choice, freedom to speak — some people don't even like electric cars. "
            "The big green lie to cost taxpayers billions. "
            "Politicians forcing us to go this way need to be voted out. "
            "Is this communism — take away our freedom of choice! "
            "Australians are not as ignorant as the politicians think, and they research government push "
            "and now question the purpose behind these pushes. "
            "There's always big corporations behind any government move. "
            "If this country is taxed just for an ideology then the potential for even greater social "
            "unrest is likely. "
            "It's social policing because you're deviating from the norm. "
            "We don't need politicians and their cronies telling us what sort of car we can have."
        )
    },
    "🛡️ RESISTANT  |  ⚙️ Enactment  →  Prevent": {
        "prescribed": PF_EV,
        "activity":   "ENACTMENT",
        "subtype":    "PREVENT",
        "orientation":"RESISTANT",
        "comment": (
            "I for one WILL NOT be forced into an electric vehicle. "
            "I have had ICE cars for some 37 years and have found them to be very reliable. "
            "My petrol car is running perfectly and at only 8 years old, it'd be stupid and wasteful "
            "to replace it. "
            "Why buy a new EV when my old car is doing all right — 13 years and 130,000 km, "
            "so good for another 13 years because it's diesel. "
            "No matter what the price of an EV it's still cheaper to keep the car I own and repair. "
            "Me, I'm sticking to my petrol vehicle til it dies. "
            "I'll stick to my V8 and my other diesel 4x4. "
            "From the start of manufacturing to the end of the vehicle's life I'd easily put my money "
            "on ICE being a far better investment."
        )
    },

    # ══════ 🌍 EXPANDER ══════
    "🌍 EXPANDER  |  📊 Evaluation  →  Complexify": {
        "prescribed": PF_EV,
        "activity":   "EVALUATION",
        "subtype":    "COMPLEXIFY",
        "orientation":"EXPANDER",
        "comment": (
            "The embodied carbon in a new vehicle is more than the emissions that are going to be "
            "produced by the current vehicle over the course of its lifetime until it falls apart. "
            "So the plan is to extract maximum value out of that current vehicle until it is no longer functional. "
            "This doesn't cover the destruction of the fabric of cities to accommodate cars. "
            "Gasoline or electric, the most significant environmental destruction caused by cars "
            "is the blight it causes to cities — 60% of the land in car-dependent cities is dedicated "
            "to cars, mainly parking and roads. "
            "The externalities cost of cars doesn't really change whether it's gasoline or electric. "
            "Electric vehicle is a false solution if you care about the environment at all. "
            "Facilitating greater use of active, shared and public transport can cut climate pollution "
            "further and faster than electrifying vehicles, and do so this decade. "
            "Yes EVs will help but they're not gonna save us. "
            "Electric vehicles aren't the magic fix everyone thinks they are."
        )
    },
    "🌍 EXPANDER  |  💬 Negotiation  →  Contest": {
        "prescribed": PF_EV,
        "activity":   "NEGOTIATION",
        "subtype":    "CONTEST",
        "orientation":"EXPANDER",
        "comment": (
            "The future is less cars, in higher density pedestrian, bike and train-orientated "
            "urban environments, where cars are secondary transport really only for those who really need it. "
            "Does it have to be a car? "
            "If your main priority was the environment, ride a bicycle. "
            "You're buying a 2-tonne metal box powered by a giant battery — let's not pretend "
            "we're saving the planet, we're just picking a lesser evil. "
            "Are we ready to have electric cars claiming our public spaces? "
            "And what about communities that may not be able to afford cars, let alone electric cars? "
            "Time to rethink public transport! "
            "Cars are a tremendously inefficient way of moving people at scale and generate congestion. "
            "We need to stop building for cars and more for humans. "
            "EVs are NOT the solution. Electric trains and buses plus accessible walking and cycling "
            "infrastructure — that's what we actually need."
        )
    },
    "🌍 EXPANDER  |  ⚙️ Enactment  →  Reroute": {
        "prescribed": PF_EV,
        "activity":   "ENACTMENT",
        "subtype":    "REROUTE",
        "orientation":"EXPANDER",
        "comment": (
            "I uprooted my life and moved from the Sunshine Coast to Melbourne with some of my strongest "
            "reasoning being the ability to use public transport, ride a bike around and use a car as "
            "little as possible. "
            "EVs for me is still not the solution. The solution is actually degrowth — going back to "
            "supporting local businesses so we don't have to travel so much. "
            "Because we're going to just drive this vehicle into the ground, I'm not even looking at "
            "the moment for a replacement electric car or ute. "
            "I am at the moment on a waiting list for a new electric cargo bike. "
            "We tend to do most of our shopping by bike rather than with the ute because the ute's "
            "inconvenient to park and navigate in small car parks. "
            "We need more viable alternatives to driving. An investment in bicycle infrastructure and "
            "public transport will greatly help this cause. "
            "If we continue to invest in car infrastructure we set ourselves up for failure."
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
            {"role": "user",   "content": user_message}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    return json.loads(response.choices[0].message.content)


def show_example_badge(ex_data: dict):
    """Show colored orientation + activity + subtype badges."""
    if not ex_data.get("activity"):
        return
    ori   = ex_data.get("orientation", "")
    act   = ex_data.get("activity", "")
    sub   = ex_data.get("subtype", "")
    cfg   = ORIENTATIONS.get(ori, {})
    ameta = ACTIVITY_META.get(act, {})
    if not cfg or not ameta:
        return
    st.markdown(f"""
    <div style="display:flex;gap:8px;align-items:center;
                margin-bottom:10px;flex-wrap:wrap;">
        <span style="background:{cfg['bg']};border:2px solid {cfg['border']};
                     color:{cfg['color']};border-radius:20px;
                     padding:4px 14px;font-weight:bold;font-size:13px;">
            {cfg['emoji']} {ori}
        </span>
        <span style="font-size:16px;color:#aaa;">→</span>
        <span style="background:{ameta['bg']};border:2px solid {ameta['color']};
                     color:{ameta['color']};border-radius:20px;
                     padding:4px 14px;font-weight:bold;font-size:13px;">
            {ameta['icon']} {act}
        </span>
        <span style="font-size:16px;color:#aaa;">→</span>
        <span style="background:#f0f0f0;border:2px solid #bbb;
                     color:#444;border-radius:20px;
                     padding:4px 14px;font-weight:bold;font-size:13px;">
            {sub}
        </span>
    </div>
    """, unsafe_allow_html=True)


def show_results(result: dict, prescribed_future: str):
    orientation = result.get("main_orientation", "").upper().strip()
    challenge   = result.get("primary_challenge", "MIXED").upper().strip()
    main_act    = result.get("main_activity", "").upper().strip()
    act_sub     = result.get("activity_subtype", "N/A").upper().strip()

    cfg   = ORIENTATIONS.get(orientation)
    chg   = CHALLENGES.get(challenge, CHALLENGES["MIXED"])
    ameta = ACTIVITY_META.get(main_act, {})

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

    # ── TOP ROW: Orientation + Activity + Challenge ──
    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        st.markdown(f"""
        <div style="background:{cfg['bg']};border-left:6px solid {cfg['border']};
                    border-radius:10px;padding:16px 18px;min-height:190px;">
            <h3 style="color:{cfg['color']};margin:0;font-size:22px;">
                {cfg['emoji']} {orientation}
            </h3>
            <p style="color:#666;margin:4px 0 3px;font-size:12px;">
                <strong>Confidence:</strong> {result.get('orientation_confidence','N/A')}
            </p>
            <p style="color:#777;margin:2px 0;font-size:11px;">
                📖 {cfg['narrative']}
            </p>
            <p style="color:#777;margin:2px 0;font-size:11px;">
                ⏱️ {cfg['temporality']}
            </p>
            <p style="color:#777;margin:2px 0;font-size:11px;">
                🎯 {cfg['goal']}
            </p>
            <p style="color:#999;margin:4px 0 0;font-size:10px;">
                {cfg['activities']}
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        act_color = ameta.get("color", "#555")
        act_bg    = ameta.get("bg",    "#f5f5f5")
        act_icon  = ameta.get("icon",  "🔄")
        # subtype color from orientation
        sub_color = cfg["color"]
        sub_bg    = cfg["bg"]
        st.markdown(f"""
        <div style="background:{act_bg};border-left:6px solid {act_color};
                    border-radius:10px;padding:16px 18px;min-height:190px;">
            <h3 style="color:{act_color};margin:0;font-size:20px;">
                {act_icon} {main_act}
            </h3>
            <p style="color:#555;margin:4px 0 3px;font-size:12px;">
                <strong>Main Future-Making Activity</strong>
            </p>
            <span style="background:{sub_bg};border:1.5px solid {sub_color};
                         color:{sub_color};border-radius:12px;
                         padding:3px 10px;font-weight:bold;font-size:12px;">
                → {act_sub}
            </span>
            <p style="color:#777;margin:8px 0 0;font-size:11px;font-style:italic;">
                {ameta.get('definition','')[:180]}...
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="background:{chg['bg']};border-left:6px solid {chg['color']};
                    border-radius:10px;padding:16px 18px;min-height:190px;">
            <h3 style="color:{chg['color']};margin:0;font-size:20px;">
                {chg['emoji']} {chg['label']}
            </h3>
            <p style="color:#555;margin:4px 0 3px;font-size:12px;">
                <strong>Primary Future-Making Challenge</strong>
            </p>
            <p style="color:#777;margin:3px 0;font-size:11px;">
                {chg['description']}
            </p>
            <p style="color:#888;margin:8px 0 0;font-size:11px;font-style:italic;">
                "{result.get('challenge_rationale','')[:130]}..."
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── CODING RATIONALES ──
    tab_ori, tab_act, tab_chg = st.tabs([
        "🔍 Orientation Rationale",
        "🔄 Activity Rationale",
        "⚡ Challenge Rationale"
    ])

    with tab_ori:
        st.markdown("**Why this orientation? (applied coding criteria)**")
        st.write(result.get("orientation_rationale", "—"))
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**📖 Narrative Identified**")
            st.caption(result.get("narrative_identified", "—"))
        with c2:
            st.markdown("**😊 Emotions Detected**")
            st.caption(result.get("dominant_emotions", "—"))
        with c3:
            st.markdown("**⏱️ Temporality Expressed**")
            st.caption(result.get("temporality_expressed", "—"))

    with tab_act:
        st.markdown("**Why this activity is primary? (applied coding criteria)**")
        st.write(result.get("activity_rationale", "—"))
        sec = result.get("secondary_activities", [])
        if sec:
            st.markdown(f"**Secondary activities also present:** {', '.join(sec)}")

        # Coding criteria reference box
        st.markdown("---")
        st.markdown("**📋 Coding Criteria Applied**")
        for act_name, meta in ACTIVITY_META.items():
            is_main = (act_name == main_act)
            border  = f"3px solid {meta['color']}" if is_main else "1px solid #ddd"
            weight  = "bold" if is_main else "normal"
            st.markdown(f"""
            <div style="border:{border};border-radius:8px;padding:10px 14px;
                        margin-bottom:8px;background:{'#fff' if is_main else '#fafafa'};">
                <strong style="color:{meta['color']};">{meta['icon']} {act_name}</strong>
                {'<span style="background:#27AE60;color:white;border-radius:8px;'
                 'padding:1px 8px;font-size:11px;margin-left:8px;">PRIMARY</span>'
                 if is_main else ''}<br>
                <span style="font-size:11px;color:#555;">{meta['definition']}</span>
            </div>
            """, unsafe_allow_html=True)

    with tab_chg:
        st.markdown("**Which future-making challenge does this comment contribute to?**")
        st.write(result.get("challenge_rationale", "—"))

    # ── IMPLICATIONS ──
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
| **4** | **Implement orientation-matched support** — Match instruments to each orientation |
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
| **1** | **Determine the prescribed future** — Define by the future it prescribes, not only technical features |
| **2** | **Consider future-making orientations** — Use narratives, goals, emotions, temporalities |
| **3** | **Identify key future-making challenges** |
| **4** | **Select orientation-sensitive response** — Match objectives and instruments |
| **5** | **Match messaging to challenges** — Avoid universal claims; communicate achievements AND limitations |
| **6** | **Support consumers through enactment** — Onboarding, workflows, escalation, training, appeals |
            """)

    # ── CITATION ──
    st.markdown("---")
    st.caption(
        f"📚 *\"{PAPER_TITLE}\"* — *{PAPER_JOURNAL}* | "
        "[Read the paper](REPLACE_WITH_YOUR_DOI_OR_URL)"
    )


# ─────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────

def main():
    st.title("🔮 Future-Making Orientation Analyzer")
    st.markdown(f"""
    Identify the **main future-making orientation**, **primary activity**,
    **emergent challenge**, and get tailored **policy & managerial recommendations**
    — grounded in the paper's coding criteria.

    *Based on:* **"{PAPER_TITLE}"** — *{PAPER_JOURNAL}*
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

    pf_default = st.session_state.pop("pf_prefill", "")
    prescribed_future = st.text_area(
        "prescribed_future",
        value=pf_default,
        height=85,
        placeholder=(
            "e.g., 'Transition all vehicles to Zero Emission Vehicles (EVs) "
            "to achieve Australia's net-zero emissions targets by 2035'  OR  "
            "'Mandatory adoption of AI-driven hiring tools in public sector HR'"
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
            "Or try a built-in example (each represents ONE orientation × ONE primary activity):",
            list(EXAMPLES.keys())
        )
        ex_data = EXAMPLES.get(selected_ex, {
            "prescribed": "", "comment": "",
            "activity": "", "subtype": "", "orientation": ""
        })

        if selected_ex != "— Select an example from the paper —":
            show_example_badge(ex_data)
            suggested_pf = ex_data.get("prescribed", "")
            if suggested_pf:
                st.info(f"💡 **Suggested prescribed future:** *{suggested_pf[:130]}...*")
                if st.button("↑ Use this as my prescribed future", type="secondary"):
                    st.session_state["pf_prefill"] = suggested_pf
                    st.rerun()

        comment = st.text_area(
            "Comment:",
            value=ex_data.get("comment", ""),
            height=220,
            placeholder="Paste or type a consumer comment here...",
            label_visibility="collapsed"
        )
    else:
        uploaded_file = st.file_uploader(
            "Upload .txt file:",
            type=["txt"],
            help="Plain text file."
        )
        if uploaded_file:
            comment = uploaded_file.read().decode("utf-8")
            st.success(f"✅ Uploaded: {len(comment):,} characters")
            with st.expander("Preview"):
                st.text(comment[:600] + ("..." if len(comment) > 600 else ""))

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
        with st.spinner("Analyzing with paper coding criteria..."):
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
                st.error("❌ Invalid API key.")
            except openai.RateLimitError:
                st.error("⏳ Rate limit reached. Please wait a moment.")
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")
                st.code(str(e))


if __name__ == "__main__":
    main()
