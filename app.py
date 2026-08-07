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
# CITATION CONSTANTS (no author names)
# ─────────────────────────────────────────
PAPER_TITLE  = "Futures in the Making: How Consumers Respond to Future-Oriented Interventions"
PAPER_JOURNAL = "Journal of Marketing"

# ─────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an expert analyst specialized in the Future-Making Orientations framework
from the paper "Futures in the Making: How Consumers Respond to Future-Oriented
Interventions" published in the Journal of Marketing.

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

EVALUATION: Cognitive assessment of the prescribed future.
  Contains a claim or judgment about what the future means, whether it is
  likely or desirable, what benefits/costs/risks/trade-offs it entails.

NEGOTIATION: Attempt to shape collective trajectories toward a preferred future.
  Makes a relational claim: responds to another position, compares futures,
  challenges or defends a proposed pathway, attempts to persuade others.

ENACTMENT: What consumers do in the present to materialize a preferred future.
  Specifies what the consumer does, intends, expects, or imagines doing
  in practice (purchasing, retaining vehicles, changing routines, cycling, etc.)

A comment may perform multiple activities simultaneously.

═══════════════════════════════════════════════════
THREE FUTURE-MAKING CHALLENGES
═══════════════════════════════════════════════════

CONVOLUTED_EVALUATIONS: When consumers with different orientations assess the
prescribed future through divergent assumptions, evidence, and temporal horizons,
making coherent sensemaking difficult.

CONFRONTATIONAL_NEGOTIATIONS: When consumers simultaneously advocate for,
question, reject, or contest the prescribed future, widening divides rather
than moving toward a collectively preferred future.

COMPETING_ENACTMENTS: When some consumers accelerate while others prevent, delay,
or re-route enactment, creating divergence and volatility in the market.

═══════════════════════════════════════════════════
POLICY ROADMAP (Figure 3)
═══════════════════════════════════════════════════

Step 1: Determine the prescribed future — Make explicit what the intervention prescribes
Step 2: Map future-making orientations — Identify how people evaluate, negotiate, enact
Step 3: Identify key future-making challenges — Which of the three are most pressing?
Step 4: Implement orientation-matched support:
  CATALYZER — Objective: enable responsible acceleration only where public value
    can be demonstrated. Instruments: time-limited regulatory sandboxes; independent
    evaluation; mandatory reporting of failures; clear exit criteria and powers to pause or reverse.
  AMBIVALENT — Objective: convert uncertainty into explicit conditions for authorization.
    Instruments: public impact assessments; staged authorization and sunset clauses;
    citizen juries; public registers; guaranteed human-service alternatives.
  RESISTANT — Objective: protect rights and restore legitimacy and accountability.
    Instruments: statutory prohibitions on unacceptable uses; appeal and human-review
    rights; independent audits; moratoria where evidence is insufficient.
  EXPANDER — Objective: broaden the policy focus; consider alternative futures.
    Instruments: citizen assemblies; public-interest funding and infrastructure;
    data trusts; competition policy; alternative ownership and governance models.
Step 5: Facilitate enactment — Provide infrastructure and build capabilities
Step 6: Measure multiple outcomes — Accuracy, fairness, who benefits, who is excluded,
    are alternative pathways emerging?
Step 7: Revise intervention — Treat the prescribed future as revisable

═══════════════════════════════════════════════════
MANAGERIAL ROADMAP (Figure 4)
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
    peer learning, explicit reporting of limitations.
    Avoid: inevitability claims; treating early adopters as proof the transition
    is easy for everyone.
  AMBIVALENT — Objective: convert generalized uncertainty into specific,
    addressable conditions. Interventions: sandboxes, comparison tools, staged
    adoption, human assistance, transparent performance evidence.
    Avoid: pressure and artificial urgency; framing hesitation as ignorance or resistance.
  RESISTANT — Objective: restore autonomy, legitimacy, and accountability.
    Interventions: consultation, opt-outs, human review, independent audits,
    protections against material harms.
    Avoid: "there is no alternative"; ridicule; hidden automation of decisions.
  EXPANDER — Objective: incorporate systemic critique and explore alternative futures.
    Interventions: participatory design, futures workshops, broader impact evaluation,
    alternative governance or business models.
    Avoid: presenting the focal offering as a complete solution; dismissing critique
    as out of scope.
Step 5: Match messaging to challenges — Do not rely on a single persuasive frame.
    Universal claims may mobilize Catalyzers while intensifying resistance elsewhere.
    Communicate achievements AND limitations.
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
    "SIMPLIFY": "#27AE60",  "STALL": "#D68910",
    "AVOID": "#C0392B",     "COMPLEXIFY": "#7D3C98",
    "ADVOCATE": "#27AE60",  "QUESTION": "#D68910",
    "REJECT": "#C0392B",    "CONTEST": "#7D3C98",
    "ACCELERATE": "#27AE60","DELAY": "#D68910",
    "PREVENT": "#C0392B",   "REROUTE": "#7D3C98",
    "N/A": "#AAAAAA"
}

ACTIVITY_META = {
    "EVALUATION":  {"icon": "📊", "color": "#2980B9", "bg": "#EBF5FB"},
    "NEGOTIATION": {"icon": "💬", "color": "#E67E22", "bg": "#FEF9E7"},
    "ENACTMENT":   {"icon": "⚙️", "color": "#8E44AD", "bg": "#F5EEF8"},
}

# ─────────────────────────────────────────
# PRESCRIBED FUTURE — shared for all EV examples
# ─────────────────────────────────────────
PF_EV = (
    "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's "
    "net-zero emissions targets, as prescribed by Australia's National Electric Vehicle Strategy (2023)"
)

# ─────────────────────────────────────────
# EXAMPLES — 12 separate entries (3 per orientation)
# Each example represents ONE orientation × ONE activity type
# All quotes drawn directly from the paper and web appendices
# ─────────────────────────────────────────
EXAMPLES = {

    "— Select an example from the paper —": {
        "prescribed": "", "comment": "",
        "activity": "", "subtype": "", "orientation": ""
    },

    # ══════════════════════════════════════
    # ⚡ CATALYZER
    # ══════════════════════════════════════

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
            "Many industry observers believe we have already passed the tipping point where sales "
            "of electric vehicles will very rapidly overwhelm petrol and diesel cars. "
            "Once EVs are cheaper to buy than ICE cars the transition will happen fast. "
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
            "There are many advantages and few disadvantages, apart from fictitious scenarios "
            "non-EV owners make up. "
            "Road trips up and down the East Coast are simple in a Tesla — with superchargers "
            "it is easy, just a stop every 2.5 hours or so. "
            "Bought our first EV largely for the environment, partly for fuel cost savings. "
            "Bought our second EV because they're just far better cars to own and drive. "
            "Proud owner of a Model 3. I'll never own a gas combustion engine again — not even a hybrid."
        )
    },

    # ══════════════════════════════════════
    # ⚖️ AMBIVALENT
    # ══════════════════════════════════════

    "⚖️ AMBIVALENT  |  📊 Evaluation  →  Stall": {
        "prescribed": PF_EV,
        "activity":   "EVALUATION",
        "subtype":    "STALL",
        "orientation":"AMBIVALENT",
        "comment": (
            "I'm not against EVs. I like the idea of more power and torque and almost no maintenance. "
            "I also listen daily to several EV YouTube channels and find the tech fascinating. "
            "I believe the infrastructure is not even remotely close to being where it needs to be "
            "for today, let alone in 10 years, and the battery tech still has a solid 10 years "
            "before they will replace ICE for every single new car purchase. "
            "I am far from being anti EV — I want one! — but I am also trying to weigh up all the facts. "
            "I'm not convinced yet that full EVs are the way to go. They seem to have quite a few "
            "problems, you know, battery disposal and other things. "
            "Perhaps these problems are over-exaggerated and I realise they will eventually be resolved "
            "with infrastructure and improvements in technology. "
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
            "Times like this one needs a crystal ball to ascertain how soon Australia will get up to speed "
            "with EVs, especially long-range fuelling stations in this vast country. "
            "It's doing my head in trying to decide on a car that will again last me another 20 years."
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
            "Yep, the cost is indeed a huge hurdle. I think I'll be running my 12 year old Subaru Outback a bit longer! "
            "I plan to drive my current 10 year old hybrid as long as I can. "
            "The next car I buy will probably be electric, but I'm expecting many of these issues "
            "to be resolved by then. "
            "Hopefully, by the time my car does need to be replaced, EVs are a lot cheaper "
            "and the inconveniences are worked out."
        )
    },

    # ══════════════════════════════════════
    # 🛡️ RESISTANT
    # ══════════════════════════════════════

    "🛡️ RESISTANT  |  📊 Evaluation  →  Avoid": {
        "prescribed": PF_EV,
        "activity":   "EVALUATION",
        "subtype":    "AVOID",
        "orientation":"RESISTANT",
        "comment": (
            "This climate change stuff is getting beyond a joke! "
            "It's not about the environment, it's about money and control so we have the elite and the poor!! "
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
            "and hybrids just can't do. "
            "Electric vehicles are not the future, just a muddle point."
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
            "There's always big corporations behind any government move and if this country is taxed "
            "just for an ideology then the potential for even greater social unrest is likely. "
            "I think it's like being a vegan of the car world. People think it's a virtue signal — "
            "that you must be a snooty holier-than-thou type judging their non-participation and lifestyle "
            "which they take pride in and identify with. "
            "It's social policing because you're deviating from the norm."
        )
    },

    "🛡️ RESISTANT  |  ⚙️ Enactment  →  Prevent": {
        "prescribed": PF_EV,
        "activity":   "ENACTMENT",
        "subtype":    "PREVENT",
        "orientation":"RESISTANT",
        "comment": (
            "I for one WILL NOT be forced into an electric vehicle and spend half my travel time "
            "charging the damn thing. "
            "I have had ICE cars for some 37 years and have found them to be very reliable. "
            "Why buy a new EV when my old car is doing all right — 13 years and 130,000 km, "
            "so good for another 13 years because it's diesel. "
            "No matter what the price of an EV it's still cheaper to keep the car I own and repair. "
            "Me, I'm sticking to my petrol vehicle til it dies. "
            "At least if it runs out of petrol I have a good chance of either fixing the problem "
            "or getting to the nearest help. "
            "With an EV or hybrid you can't fix it and nor can anyone else apart from an EV mechanic — "
            "and make sure you're sitting down when they give you the repair bill. "
            "I'll stick to my V8 and my other diesel 4x4. "
            "From the start of manufacturing to the end of the vehicle's life I'd easily put my money "
            "on ICE being a far better investment."
        )
    },

    # ══════════════════════════════════════
    # 🌍 EXPANDER
    # ══════════════════════════════════════

    "🌍 EXPANDER  |  📊 Evaluation  →  Complexify": {
        "prescribed": PF_EV,
        "activity":   "EVALUATION",
        "subtype":    "COMPLEXIFY",
        "orientation":"EXPANDER",
        "comment": (
            "The embodied carbon in a new vehicle is more than the emissions that are going to be "
            "produced by the current vehicle over the course of its lifetime until it falls apart. "
            "So that's the plan: extract maximum value out of that current vehicle until it is no longer functional. "
            "This doesn't cover the destruction of the fabric of cities to accommodate cars. "
            "Gasoline or electric, the most significant environmental destruction caused by cars "
            "is the blight it causes to cities. "
            "60% of the land in car-dependent cities is dedicated to cars, mainly parking and roads. "
            "The externalities cost of cars doesn't really change whether it's gasoline or electric. "
            "Electric vehicle is a false solution if you care about the environment at all. "
            "Facilitating greater use of active, shared and public transport can cut climate pollution "
            "further and faster than electrifying vehicles — and do so this decade — because the effects "
            "are seen immediately through reduced use of private motor vehicle travel. "
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
            "we're saving the planet, we're just picking a lesser evil but it's still not good for the planet. "
            "Why save the environment by keeping the car you already own and using it less, when you can "
            "spend money on that flash new hybrid/EV/hydrogen powered four wheeled status symbol "
            "that shows you earn more money than you need? "
            "Cars are a tremendously inefficient way of moving people at scale and generate congestion. "
            "Are we ready to have electric cars claiming our public spaces? "
            "And what about communities that may not be able to afford cars, let alone electric cars? "
            "Time to rethink public transport! We need to stop building for cars and more for humans."
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
            "EVs for me is still not the solution. The solution is actually degrowth — like going back "
            "to supporting local businesses so we don't have to travel so much. "
            "Because we're going to just drive this vehicle into the ground, I'm not even looking at "
            "the moment for a replacement electric car or ute. "
            "I am at the moment on a waiting list for a new electric cargo bike because my current "
            "electric cargo bike is about seven years old. "
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


def activity_card(label: str, icon: str, activity_type: str, is_active: bool) -> str:
    color  = ACTIVITY_COLORS.get(activity_type, "#AAA")
    bg     = "#ffffff" if is_active else "#f9f9f9"
    border = color if is_active else "#dddddd"
    tc     = "#333333" if is_active else "#aaaaaa"
    return f"""
    <div style="background:{bg};border:2px solid {border};border-radius:8px;
                padding:14px;text-align:center;min-height:90px;">
        <div style="font-size:18px;">{icon}</div>
        <strong style="color:{tc};font-size:12px;">{label}</strong><br>
        <span style="color:{color};font-weight:bold;font-size:15px;">{activity_type}</span>
    </div>
    """


def show_example_badge(ex_data: dict):
    """Show a colored badge when an example is pre-selected."""
    if not ex_data.get("activity"):
        return
    ori  = ex_data.get("orientation", "")
    act  = ex_data.get("activity", "")
    sub  = ex_data.get("subtype", "")
    cfg  = ORIENTATIONS.get(ori, {})
    ameta= ACTIVITY_META.get(act, {})
    if not cfg or not ameta:
        return
    st.markdown(f"""
    <div style="display:flex;gap:10px;align-items:center;
                margin-bottom:10px;flex-wrap:wrap;">
        <span style="background:{cfg['bg']};border:2px solid {cfg['border']};
                     color:{cfg['color']};border-radius:20px;
                     padding:4px 14px;font-weight:bold;font-size:13px;">
            {cfg['emoji']} {ori}
        </span>
        <span style="background:{ameta['bg']};border:2px solid {ameta['color']};
                     color:{ameta['color']};border-radius:20px;
                     padding:4px 14px;font-weight:bold;font-size:13px;">
            {ameta['icon']} {act}
        </span>
        <span style="background:#f0f0f0;border:2px solid #ccc;
                     color:#444;border-radius:20px;
                     padding:4px 14px;font-weight:bold;font-size:13px;">
            → {sub}
        </span>
    </div>
    """, unsafe_allow_html=True)


def show_results(result: dict, prescribed_future: str):
    orientation = result.get("orientation", "").upper().strip()
    challenge   = result.get("primary_challenge", "MIXED").upper().strip()
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
                    border-radius:10px;padding:18px 22px;min-height:170px;">
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
                    border-radius:10px;padding:18px 22px;min-height:170px;">
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
                "{result.get('challenge_explanation','')[:160]}..."
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
    st.markdown("##### 🔄 Future-Making Activities Identified")

    activities  = result.get("future_making_activities", [])
    eval_type   = result.get("evaluation_type",  "N/A")
    neg_type    = result.get("negotiation_type", "N/A")
    enact_type  = result.get("enactment_type",   "N/A")

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

    # ── CHALLENGE DETAIL ──
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
| **1** | **Determine the prescribed future** — Define by the future it prescribes, not only technical features |
| **2** | **Consider future-making orientations** — Use narratives, goals, emotions, temporalities |
| **3** | **Identify key future-making challenges** — Convoluted evaluations, confrontational negotiations, competing enactments |
| **4** | **Select orientation-sensitive response** — Match objectives and instruments to each orientation |
| **5** | **Match messaging to challenges** — Avoid universal claims; communicate achievements AND limitations |
| **6** | **Support consumers through enactment** — Onboarding, workflows, escalation, training, appeals |
            """)

    # ── CITATION ──
    st.markdown("---")
    st.caption(
        f"📚 *\"{PAPER_TITLE}\"* — {PAPER_JOURNAL} | "
        "[Read the paper](REPLACE_WITH_YOUR_DOI_OR_URL)"
    )


# ─────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────

def main():
    st.title("🔮 Future-Making Orientation Analyzer")
    st.markdown(f"""
    Identify **consumer orientations**, **future-making activities**, **challenges**,
    and get tailored **policy & managerial recommendations** from a single comment.

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

    # Handle pre-fill from session state
    pf_default = st.session_state.pop("pf_prefill", "")

    prescribed_future = st.text_area(
        "prescribed_future",
        value=pf_default,
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

        # Example selector — 12 separate examples
        ex_keys = list(EXAMPLES.keys())
        selected_ex = st.selectbox(
            "Or try a built-in example (each represents ONE orientation × ONE activity):",
            ex_keys
        )

        ex_data = EXAMPLES.get(selected_ex, {
            "prescribed": "", "comment": "",
            "activity": "", "subtype": "", "orientation": ""
        })

        # Show activity badge if an example is selected
        if selected_ex != "— Select an example from the paper —":
            show_example_badge(ex_data)

        # Suggest prescribed future
        suggested_pf = ex_data.get("prescribed", "")
        if selected_ex != "— Select an example from the paper —" and suggested_pf:
            st.info(f"💡 **Suggested prescribed future:** *{suggested_pf[:120]}...*")
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
            help="Plain text file. For multiple comments separate them with a blank line."
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
