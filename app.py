import streamlit as st
import openai
import json
import re
import concurrent.futures
import pandas as pd

# ─────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Future-Making Analyzer",
    page_icon="FM",
    layout="wide"
)

# ─────────────────────────────────────────
# CITATION CONSTANTS
# ─────────────────────────────────────────
PAPER_TITLE = "Futures in the Making: How Consumers Respond to Future-Oriented Interventions"
PAPER_URL   = "REPLACE_WITH_YOUR_DOI_OR_URL"

DOC_MAX_WORKERS = 5  # parallel API calls for document analysis

# ─────────────────────────────────────────
# INTERPRETIVE-USE NOTE (shown near input and before corpus results)
# ─────────────────────────────────────────
INTERPRETIVE_USE_NOTE = (
    "**Interpretive-use note.** For comparability, the application assigns a "
    "dominant orientation and activity to each analyzed segment. This is an "
    "analytical simplification: future-making activities are interdependent "
    "and recursive, and consumers may adopt, combine, or move between "
    "orientations across contexts and over time. Review outputs alongside "
    "the complete text, the surrounding interaction, the specified "
    "intervention, and relevant behavioral evidence. Corpus percentages "
    "refer only to analyzed segments and should not be interpreted as "
    "population estimates. Future-making challenges and Fragile Futures "
    "require evidence that differently oriented performances coexist, "
    "clash, or interfere with one another."
)

HOMEPAGE_DESCRIPTION = """
Use this application to support the diagnosis of consumer future-making in
response to a policy or market intervention. After defining the prescribed
future, users can analyze a single meaning-bearing text segment or selected
segments from a document or corpus. The application identifies the dominant
future-making orientation -- Catalyzer, Ambivalent, Resistant, or Expander --
and examines how evaluation, negotiation, or enactment is being performed.
Across multiple texts, it maps recurring patterns and flags where differently
oriented performances may contribute to convoluted evaluations,
confrontational negotiations, or competing enactments.

The framework was developed through qualitative research on Australian Zero
Emission Vehicle interventions. Its application to AI-integrated healthcare
illustrates its expected transferability to another future-oriented context;
it does not constitute independent empirical validation. Orientations are
situated ways of performing future-making, not fixed consumer types or
stable market segments. Results support interpretive diagnosis and should
be reviewed in context: corpus summaries describe only the analyzed text
segments and do not, by themselves, demonstrate population prevalence,
future-making challenges, or Fragile Futures.

*Based on: "Futures in the Making: How Consumers Respond to Future-Oriented
Interventions."*
"""

# ─────────────────────────────────────────
# MODE LABELS
# ─────────────────────────────────────────
MODE_SINGLE = "single"
MODE_DOC = "document"
MODE_SINGLE_LABEL = "Analyze a Single Comment"
MODE_DOC_LABEL = "Map Orientations Across Selected Segments"

# ─────────────────────────────────────────
# DETERMINISTIC ACTIVITY -> POTENTIAL CHALLENGE PATHWAY MAPPING
# ─────────────────────────────────────────
ACTIVITY_TO_CHALLENGE_PATHWAY = {
    "EVALUATION":  "CONVOLUTED_EVALUATIONS",
    "NEGOTIATION": "CONFRONTATIONAL_NEGOTIATIONS",
    "ENACTMENT":   "COMPETING_ENACTMENTS",
}


def _clean_enum(value) -> str:
    if not value:
        return ""
    value = str(value)
    for sep in ["|", "/", " or "]:
        if sep in value:
            return value.split(sep)[0].strip()
    return value.strip()


def derive_potential_challenge_pathway(main_activity: str) -> str:
    """Deterministic mapping. Returns the pathway KEY, not a claim that the
    challenge has been observed -- the pathway is only a potential
    contribution to friction if a differently oriented performance of the
    same activity is also present elsewhere in the discussion or market."""
    act = _clean_enum(main_activity).upper() if main_activity else ""
    return ACTIVITY_TO_CHALLENGE_PATHWAY.get(act, "N/A")


def derive_challenge_pathways(main_activity: str, secondary_classifications: list) -> list:
    """Returns a deduplicated, ordered list of potential challenge pathway
    keys derived from the primary activity plus any secondary
    classifications attached to the same segment."""
    pathways = []
    primary = derive_potential_challenge_pathway(main_activity)
    if primary != "N/A":
        pathways.append(primary)
    for sec in (secondary_classifications or []):
        act = _clean_enum(sec.get("activity", "")).upper()
        p = derive_potential_challenge_pathway(act)
        if p != "N/A" and p not in pathways:
            pathways.append(p)
    return pathways


# ─────────────────────────────────────────
# BACKWARD-COMPATIBILITY GETTERS
# (handle results generated under older field names)
# ─────────────────────────────────────────

def get_secondary_classifications(result: dict) -> list:
    sec = result.get("secondary_classifications")
    if sec:
        cleaned = []
        for item in sec:
            if isinstance(item, dict):
                cleaned.append({
                    "activity": _clean_enum(item.get("activity", "")).upper(),
                    "activity_subtype": _clean_enum(item.get("activity_subtype", "")).upper(),
                    "orientation": _clean_enum(item.get("orientation", "")).upper(),
                    "rationale": item.get("rationale", "")
                })
        return cleaned
    # Backward compatibility: older versions used "secondary_activities" as
    # a flat list of activity strings with no subtype/orientation/rationale.
    legacy = result.get("secondary_activities")
    if legacy:
        return [
            {"activity": _clean_enum(str(a)).upper(), "activity_subtype": "",
             "orientation": "", "rationale": "(legacy field -- no detail available)"}
            for a in legacy if a
        ]
    return []


def get_contrasting_orientation(result: dict) -> str:
    val = result.get("theoretically_contrasting_orientation")
    if not val:
        # Backward compatibility with the earlier field name.
        val = result.get("likely_opposing_orientation", "")
    return _clean_enum(val).upper()


def get_policy_considerations(result: dict) -> dict:
    return (result.get("policy_diagnostic_considerations")
            or result.get("policy_recommendations")
            or {})


def get_manager_considerations(result: dict) -> dict:
    return (result.get("manager_diagnostic_considerations")
            or result.get("manager_recommendations")
            or {})


def get_input_scope_warning(result: dict) -> str:
    return result.get("input_scope_warning", "") or ""


# ─────────────────────────────────────────
# SCOPE AND DEGREE OF PRESCRIPTION OF INTERVENTIONS (context typology)
# Purely descriptive -- does not predetermine expected orientations,
# activities, or challenge pathways.
# ─────────────────────────────────────────
INTERVENTION_TYPES = {
    "Fixed Intervention (Narrow scope, Highly prescriptive)": {
        "scope": "Narrow", "prescriptiveness": "Highly",
        "example": "Ban on single-use plastic bags (Gonzalez-Arcos et al. 2021)",
        "note": (
            "Predominantly initiated by governmental policies or laws with "
            "clear targets and strong regulatory specification. Requires "
            "consumers to change one or a few interconnected practices."
        )
    },
    "Bounded Intervention (Broad scope, Highly prescriptive)": {
        "scope": "Broad", "prescriptiveness": "Highly",
        "example": "ZEV policies and strategies (Holtsmark and Skonhoft 2014)",
        "note": (
            "Highly prescriptive and predominantly initiated by governmental "
            "targets, followed by incentives, penalties, and firm strategies "
            "that move consumers and market actors across a wide range of "
            "practices."
        )
    },
    "Flexible Intervention (Narrow scope, Lowly prescriptive)": {
        "scope": "Narrow", "prescriptiveness": "Lowly",
        "example": "Meat-free Mondays (Semba et al. 2024)",
        "note": (
            "New behavioral guidelines for a specific consumption practice, "
            "often arising from consumer movements or social marketers "
            "rather than regulation."
        )
    },
    "Open Intervention (Broad scope, Lowly prescriptive)": {
        "scope": "Broad", "prescriptiveness": "Lowly",
        "example": "Decentralized adoption of AI in healthcare (Poon et al. 2025)",
        "note": (
            "Arises primarily from technological or societal developments "
            "rather than explicit policy goals; characterized by high "
            "uncertainty, multiple possible trajectories, and no predefined "
            "societal outcome."
        )
    },
}


def augment_prescribed_future(base_pf: str, it_key: str) -> str:
    """If the user selected an intervention type, append its scope/
    prescriptiveness classification to the prescribed future text so the
    model has this contextual information available. This context helps
    interpret what the prescribed future requires; it does not predetermine
    which orientations, activities, or challenge pathways will be found."""
    base_pf = (base_pf or "").strip()
    if not it_key or it_key not in INTERVENTION_TYPES:
        return base_pf
    it_data = INTERVENTION_TYPES[it_key]
    type_name = it_key.split(" (")[0]
    addition = (
        f"[Intervention type (context only, not predictive): {type_name} -- "
        f"{it_data['scope']} scope, {it_data['prescriptiveness']} "
        f"prescriptive.]"
    )
    if addition in base_pf:
        return base_pf
    return f"{base_pf} {addition}".strip()


# ─────────────────────────────────────────
# SYSTEM PROMPT v12 -- conceptually realigned with manuscript R1
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an analytical assistant supporting the diagnosis of consumer
future-making in response to policy or market interventions, grounded in
a practice-theoretical framework developed through qualitative research
on Australian Zero Emission Vehicle (ZEV) interventions.

This framework was developed through qualitative research in the ZEV
context. Its application below to AI-integrated healthcare illustrates
the framework's expected transferability to another future-oriented
context; it does not constitute independent empirical validation in that
domain. Apply the same conceptual logic across domains, while remaining
attentive to context-specific differences.

You will be given a single meaning-bearing text segment (which may
internally contain more than one sentence) and the prescribed future it
responds to. Your task is to identify a PRIMARY classification, any
substantively separable SECONDARY classification(s), and to support
interpretive diagnosis -- not to issue definitive prescriptions.

====================================================================
A. SCOPE AND DEGREE OF PRESCRIPTION OF INTERVENTIONS (context)
====================================================================

Interventions vary along two dimensions: the SCOPE of intended change to
consumer practices (Narrow vs. Broad) and HOW PRESCRIPTIVE the
intervention is (Highly vs. Lowly):

  FIXED (Narrow, Highly prescriptive)   -- e.g., ban on single-use plastic bags
  BOUNDED (Broad, Highly prescriptive)  -- e.g., ZEV policies and strategies
  FLEXIBLE (Narrow, Lowly prescriptive) -- e.g., Meat-free Mondays
  OPEN (Broad, Lowly prescriptive)      -- e.g., decentralized adoption of AI in healthcare

This typology helps interpret what the prescribed future asks of
consumers. It CONTEXTUALIZES the prescribed future; it does NOT
predetermine which orientations, activities, or potential challenge
pathways will appear in a given text or dataset. Classification of a
specific intervention depends on how it is actually specified (e.g.,
generic, decentralized AI adoption in healthcare is typically an Open
intervention, whereas a specific mandate requiring all primary-care
patients to enter through AI-supported triage by a stated date may be a
Bounded intervention), not on the general domain to which it belongs.

====================================================================
B. FUTURE-MAKING ACTIVITIES
====================================================================

--- EVALUATION ---
Operational definition: how consumers make sense of the prescribed
future -- assessing its meaning, desirability, feasibility, credibility,
consequences, risks, assumptions, or trade-offs.
  - The assessment must have an identifiable object (e.g., EVs, AI
    diagnostic tools, infrastructure, regulation, environmental or health
    impacts, transition timeline).
  - Rhetorical or self-directed questions used to weigh complexity
    ("The question is...", "What about...") typically function as
    Evaluation.
  - Strong, categorical, or negative language ("not the solution,"
    "false solution," "muddle point") does not, by itself, indicate
    Negotiation. A firmly worded standalone opinion about the topic can
    still be Evaluation if its primary work is assessment rather than an
    attempt to shape a collective trajectory (see Section H).
  - A conditional "if you..." clause used merely to qualify a declarative
    claim does not, by itself, convert Evaluation into Negotiation.
Sub-types by orientation:
  SIMPLIFY   (Catalyzer)  -- narrows focus, treats difficulties as
    temporary or already solved
  STALL      (Ambivalent) -- careful consideration, information
    gathering, unresolved technical/ethical/institutional conditions
  AVOID      (Resistant)  -- a narrow, categorical, dismissive standalone
    judgment WITHOUT elaborated systemic reasoning connecting it to wider
    systems
  COMPLEXIFY (Expander)   -- zooms out to systemic trade-offs, WITH
    elaborated reasoning connecting the topic to wider systems

  DISAMBIGUATION -- AVOID vs. COMPLEXIFY: A brief categorical dismissal
  with no elaborated systemic reasoning ("not the solution... just a
  muddle point") is typically AVOID. A dismissal that elaborates a
  systemic argument connecting the topic to wider systems (city design,
  land use, production/consumption patterns, structural inequality) is
  typically COMPLEXIFY, even if it uses similarly strong language. The
  presence of elaborated systemic reasoning, not the strength of the
  dismissal, is what distinguishes the two.

--- NEGOTIATION ---
Operational definition: how consumers attempt to shape a collective
trajectory toward a preferred future by comparing, defending,
questioning, rejecting, contesting, or expanding it in relation to other
actors, authorities, or positions.
IMPORTANT: Negotiation MAY BE PURELY DECLARATIVE. An imperative, command,
or direct address is A COMMON signal of Negotiation but is NOT REQUIRED.
A confidently stated systemic alternative that stakes out a different
collective trajectory (e.g., "the future is less cars, in higher density
pedestrian/bike and train orientated urban environments") functions as
Negotiation/Contest even without imperative phrasing, because its primary
work is to advance an alternative trajectory in relation to the
prescribed one, not merely to assess it.
Sub-types by orientation:
  ADVOCATE  (Catalyzer)  -- recruits others, calls for stronger
    policy/rollout, often (but not necessarily) using evidentiary claims
    in support of a call to action
  QUESTION  (Ambivalent) -- polite skepticism, asks for proof from
    others, or proposes a STAGED/INTERIM compromise pathway WITHIN THE
    SAME PARADIGM (e.g., hybrid vehicles as a bridge to full EVs)
  REJECT    (Resistant)  -- refuses a demand or frames the intervention
    (or the authority behind it) as illegitimate or coercive; no
    alternative future is proposed. This applies even in third person --
    a literal direct address is not required.
  CONTEST   (Expander)   -- contests the current paradigm itself and
    proposes a SYSTEMIC alternative outside it, whether phrased as an
    imperative or as a confident declarative claim

  DISAMBIGUATION -- REJECT vs. CONTEST: REJECT refuses an
  imposition/authority without proposing an alternative future. CONTEST
  proposes a different, broader future outside the current paradigm.

Sub-types by orientation (Enactment):
  ACCELERATE (Catalyzer)  -- adopts the prescribed future early, divests
    from the status quo, installs/uses new infrastructure
  DELAY      (Ambivalent) -- continues status-quo practice, ties
    non-adoption to specific resolvable conditions, with an implied
    "for now"
  PREVENT    (Resistant)  -- retains status-quo practice, frames
    non-adoption as identity-based, largely independent of future
    conditions
  REROUTE    (Expander)   -- adopts an entirely different
    practice/pathway (e.g., community care, active transport,
    alternative infrastructure)

  DISAMBIGUATION -- DELAY vs. PREVENT: DELAY ties non-adoption to a
  resolvable condition; PREVENT frames it as a durable, identity-based
  stance ("no matter what," "til it dies," "will never").

--- ENACTMENT ---
Operational definition: how consumers give material or practical form to
a preferred future through actual, planned, imagined, delayed, refused,
or reconfigured practices and material arrangements, typically described
in the first person or clearly attributed to the speaker's own practice.
Enactment content is a strong signal for the primary classification, but
it does not categorically override other substantial content in the same
passage. If a passage contains both substantial evaluative or negotiating
content AND substantial enactment content, determine which constitutes
the DOMINANT analytical function of the passage as a whole (Section H),
and capture the other as a SECONDARY classification rather than
discarding it.

====================================================================
C. FUTURE-MAKING ORIENTATIONS
====================================================================

--- CATALYZER ---
Main narrative: Urgency narrative -- the future is now, transition is
necessary, feasible, and already gaining momentum.
Tagline: "Urgent, desirable, and already underway."
Goal: Accelerate change toward the prescribed future.
Emotions: Utopian optimism; enthusiasm; confidence; pride.
Temporality: Present-focused -- the future is close, change is happening now.
Notable conditions of adoption: High degree of alignment between current
practices and the prescribed future.
Markers: "now," "rapidly," "already," "let's get moving," "catch up,"
"behind," "urgent," "inevitable."
VALID SUBTYPES: SIMPLIFY (Evaluation), ADVOCATE (Negotiation), ACCELERATE
(Enactment).

--- AMBIVALENT ---
Main narrative: Pragmatic narrative -- desirability assessed against
everyday feasibility (price, evidence, infrastructure, liability, safety).
Tagline: "Valuable, but conditions are not yet ready."
Goal: Slow or stage movement; delay decisions; balance risks and benefits.
Emotions: Curiosity; caution; anxiety; frustration; conditional optimism.
Temporality: Gradual and contingent.
Notable conditions of adoption: Limited resources to support change.
Markers: "but," "if," "when," "not yet," "hopefully," "compromise,"
"flexible," "pragmatic."
VALID SUBTYPES: STALL (Evaluation), QUESTION (Negotiation), DELAY (Enactment).

DISAMBIGUATION -- AMBIVALENT vs. EXPANDER on proposed alternatives: When a
passage proposes an alternative, ask whether it stays WITHIN the current
paradigm as a temporary/interim bridge (still a car, just hybrid instead
of full EV, "until 2030") -- typically AMBIVALENT -- or REJECTS the
paradigm itself as a durable reframing (no car at all, public transport,
degrowth) -- typically EXPANDER.

--- RESISTANT ---
Main narrative: Control narrative -- interventions framed as coercive,
inequitable, ideologically motivated, or misleading.
Tagline: "Threatens autonomy, identity, or rights."
Goal: Contest the prescribed future and protect the status quo.
Emotions: Pessimism; anger; anxiety; fear; defiance; distrust.
Temporality: Maintenance-oriented.
Notable conditions of adoption: Low degree of alignment between current
practices and prescribed future.
Markers: "forced," "agenda," "control," "freedom," "never," "not the
solution," "communism," "surveillance," "government overreach," "big
corporations," "social unrest," "social policing."
VALID SUBTYPES: AVOID (Evaluation), REJECT (Negotiation), PREVENT
(Enactment). AVOID should not be assigned to any orientation other than
RESISTANT.

--- EXPANDER ---
Main narrative: Bigger-picture narrative -- situates the intervention
within wider systems (production, consumption, urban design,
institutional structures, access/equity).
Tagline: "The problem is framed too narrowly."
Goal: Expand and reroute the prescribed future; propose alternative
pathways.
Emotions: Dystopian optimism; concern; hope; critical urgency.
Temporality: Envisioned and system-oriented.
Notable conditions of adoption: Mismatch among current practices,
normative practices, and those directed by the prescribed future.
Formulations: "does not solve the real problem," "bigger picture,"
"false solution [with elaborated systemic reasoning]."
VALID SUBTYPES: COMPLEXIFY (Evaluation), CONTEST (Negotiation), REROUTE
(Enactment).

DO NOT infer orientation from sentiment or tone alone. An enthusiastic
tone alone is not sufficient to establish Catalyzer; a critical tone
alone is not sufficient to establish Resistant or Expander. Ground the
orientation in the configuration of narrative, goal, emotion,
temporality, relationship to the prescribed future, and practice
implications described above.

====================================================================
D. FUTURE-MAKING CHALLENGES AS POTENTIAL PATHWAYS
====================================================================

Each future-making activity can, IF it clashes with differently oriented
performances of the same activity elsewhere in a discussion or market,
contribute to one of three future-making challenges:

  EVALUATION  -> may contribute to CONVOLUTED_EVALUATIONS
  NEGOTIATION -> may contribute to CONFRONTATIONAL_NEGOTIATIONS
  ENACTMENT   -> may contribute to COMPETING_ENACTMENTS

A single analyzed segment provides evidence of ONE performance of an
activity -- it is not evidence that the challenge itself has occurred.
Whether these challenges actually materialize, and whether they aggregate
into FRAGILE FUTURES (multiple, volatile, and conflicting preferred
futures that may interfere with the actualization of the prescribed
one), requires evidence that differently oriented performances actually
coexist, clash, or interfere with one another -- which a single segment
cannot establish on its own. This activity -> pathway mapping is applied
deterministically by the calling application based on your main_activity
and secondary_classifications. Your task in Section I is to explain, for
THIS specific text, how its content could plausibly contribute to
friction with a differently oriented performance, IF such a performance
were also present in the discussion or market.

====================================================================
E. POLICY ROADMAP (7 steps, diagnostic support only)
====================================================================

This application primarily supports the first three, largely diagnostic,
roadmap steps. It does not issue definitive policy instruments from a
single text segment.

Step 1: Determine the prescribed future -- define what it means for
  existing consumer practices.
Step 2: Map future-making orientations across the available data
  (diagnostic; requires more than one segment).
Step 3: Diagnose which future-making challenges are most pressing
  (diagnostic; requires evidence of clashing performances, not a single
  segment).
Step 4: Implement support initiatives matched to orientations
  (requires steps 1-3 plus organizational decision-making).
Step 5: Facilitate enactment through infrastructure and capabilities.
Step 6: Measure multiple outcomes over time.
Step 7: Revise the intervention based on evidence.

====================================================================
F. MANAGERIAL ROADMAP (6 steps, diagnostic support only)
====================================================================

Step 1: Determine the prescribed future for the customer journey.
Step 2: Consider future-making orientations as a diagnostic lens, not
  fixed segments.
Step 3: Monitor future-making challenges using discursive, experiential,
  and behavioral evidence.
Step 4: Select an orientation-sensitive response (requires organizational
  decision-making beyond a single text segment).
Step 5: Match messaging to future-making challenges.
Step 6: Support consumers through enactment at relevant touchpoints.

====================================================================
G. GROUNDING EXAMPLES
====================================================================

Example 1 (EVALUATION):
"Once EVs are cheaper to buy than ICE cars the transition will happen
fast... EVs can stand on their own merits now."
-> Primary: EVALUATION / SIMPLIFY / CATALYZER

Example 2 (NEGOTIATION -- substantial, elaborated call to action; evidence
functions in support of the call to action rather than as a self-standing
judgment):
"We need to act on transport emissions as quickly as possible... so
let's get moving."
-> Primary: NEGOTIATION / ADVOCATE / CATALYZER

Example 3 (ENACTMENT):
"I won't be getting one, I'll stick to my V8 and my other diesel 4x4..."
This is a strong, self-contained signal of Enactment (a durable,
identity-based refusal). If a passage like this also contains separable
evaluative content elsewhere, capture that content as a secondary
classification rather than omitting it.
-> Primary: ENACTMENT / PREVENT / RESISTANT

Example 4 (ENACTMENT):
"We tend to do most of our shopping by bike rather than with the ute
because the ute's inconvenient to park..."
-> Primary: ENACTMENT / REROUTE / EXPANDER

Example 5 (EVALUATION despite questions -- self-directed, does not
attempt to shape a collective trajectory in relation to another
position):
"The question is: what is the difference pollution-wise between making
an EV and making an ICE car?... It's a complex issue..."
-> Primary: EVALUATION / STALL / AMBIVALENT

Example 6 (NEGOTIATION -- direct address demanding accountability):
"Have you thought about what they are gonna do with all the batteries
once they expire because they aren't recyclable?"
-> Primary: NEGOTIATION / QUESTION / AMBIVALENT

Example 7 (NEGOTIATION/REJECT -- third-person adversarial framing of
named authority actors is sufficient; direct address is not required):
"We don't need politicians and their cronies telling us what sort of
car we can have."
-> Primary: NEGOTIATION / REJECT / RESISTANT

Example 8 (NEGOTIATION/REJECT via adversarial third-person framing, no
first-person address, no alternative future proposed -- hence REJECT,
not CONTEST):
"Is this communism -- take away our freedom of choice! ... There's
always big corporations behind any government move... What are you
going to do if your EV shits itself out in the middle of nowhere?"
-> Primary: NEGOTIATION / REJECT / RESISTANT

Example 9 (NEGOTIATION/CONTEST -- named direct address plus an
imperative proposing a non-car alternative -- a systemic reframing,
hence CONTEST not REJECT):
"John you are so right... Does it have to be a car? If your main
priority was the environment, ride a bicycle..."
-> Primary: NEGOTIATION / CONTEST / EXPANDER

Example 10 (EVALUATION/AVOID -- narrow dismissal, no elaborated systemic
reasoning):
"Electric vehicles are not the solution... Electric vehicles are not the
future, just a muddle point."
-> Primary: EVALUATION / AVOID / RESISTANT

Example 11 (EVALUATION/COMPLEXIFY -- similarly strong language, but WITH
elaborated systemic reasoning connecting the topic to city design and
land use):
"This doesn't cover the destruction of the fabric of cities to
accommodate cars... 60% of the land in car-dependent cities are
dedicated to cars... Electric vehicle is a false solution if you care
about the environment at all."
-> Primary: EVALUATION / COMPLEXIFY / EXPANDER

Example 12 (PRIMARY + SECONDARY -- a passage with both substantial
evaluative content and substantial enactment content; capture both):
"I am wanting to upgrade the car and I am umming and aahing over PHEV or
EV [evaluative]. Just bought a new petrol car as the infrastructure
still isn't in place [concrete action]. I plan to drive my current 10
year old hybrid as long as I can [firm intention]."
Here, the concrete, decisive actions ("just bought," "I plan to drive...
as long as I can") constitute the dominant analytical function, so the
primary classification is Enactment. The "umming and aahing over PHEV or
EV" is a substantial, separable body of evaluative content and should be
captured as a secondary classification.
-> Primary: ENACTMENT / DELAY / AMBIVALENT
-> Secondary: EVALUATION / STALL / AMBIVALENT

Example 13 (STRUCTURAL EMPHASIS HEURISTIC for Evaluation vs. Negotiation
when urgency language co-occurs with evidentiary content -- this is a
useful heuristic, not an automatic rule):
  PASSAGE 13a: "We need to move on climate with urgency [...] All the
  studies I've seen say about 12,000 miles or 3 to 5 years for lifetime
  emissions to be better than ICE... The math and science is extremely
  clear... Let's lift the ambition."
  Heuristic: mentally set aside the urgency phrases ("we need to move on
  climate with urgency," "let's lift the ambition"). What remains is a
  substantial, self-standing evaluative judgment about scientific
  evidence that does not depend on the urgency framing to be meaningful.
  This favors reading the passage as EVALUATION, with the urgency phrases
  functioning as framing rather than as the primary work of the passage.
  -> Primary: EVALUATION / SIMPLIFY / CATALYZER

  PASSAGE 13b: "We need to act on transport emissions as quickly as
  possible. People are still buying new Internal Combustion Energy
  vehicles due to the lack of choice of Electric Vehicles. Australia has
  demonstrated that it has an appetite for EVs, so let's get moving."
  Heuristic: mentally set aside the call-to-action phrases. What remains
  ("people are still buying...", "Australia has demonstrated...") does
  not stand as an independent judgment -- it functions as a reason
  supporting the call to action. This favors reading the passage as
  NEGOTIATION, since its primary work is to advance a collective call to
  action rather than to offer a self-standing assessment.
  -> Primary: NEGOTIATION / ADVOCATE / CATALYZER
This heuristic is one useful signal among several, not a mechanical
rule. The presence or absence of an imperative is likewise only one
signal -- Negotiation may be purely declarative (see Section B).

Example 14 (AMBIVALENT vs. EXPANDER -- staged/interim compromise within
the same paradigm, despite an elaborated collective call to action):
"We need to invest in infrastructure but at the same time limit the
cost... We should transition to hybrid vehicles instead of EVs until
2030."
The alternative (hybrid) stays within the same paradigm (still a car)
and is framed as a temporary staging measure, not a systemic critique of
car-centrality.
-> Primary: NEGOTIATION / QUESTION / AMBIVALENT

Example 15 (cross-domain, AI healthcare, illustrative of expected
transferability, not independent validation):
"AI is already more accurate than humans and will inevitably improve
healthcare."
-> Primary: EVALUATION / SIMPLIFY / CATALYZER

Example 16 (cross-domain, AI healthcare):
"AI is a tool for surveillance, cost reduction, and a poor replacement
for expert judgment."
-> Primary: EVALUATION / AVOID / RESISTANT

Example 17 (cross-domain, AI healthcare):
"A more efficient algorithm does not solve unequal access to healthcare."
-> Primary: EVALUATION / COMPLEXIFY / EXPANDER

Example 18 (NEGOTIATION without any imperative -- purely declarative
systemic contestation; Peter-like Expander enactment example extended):
"The future is less cars, in higher density pedestrian/bike and train
orientated urban environments, where cars are a secondary transport
really only for those who really need it."
This passage contains no imperative or direct address, yet its primary
work is to advance an alternative collective trajectory in contrast to
the prescribed future -- this is Negotiation/Contest, not Evaluation,
because it stakes out a position rather than merely assessing one.
-> Primary: NEGOTIATION / CONTEST / EXPANDER

====================================================================
H. DECISION PROCEDURE -- Apply for EVERY text
====================================================================

STEP 1 -- Read the entire meaning-bearing segment (and any available
surrounding conversational context) before classifying anything.

STEP 2 -- Identify ALL substantive evidence of evaluation, negotiation,
and enactment present in the text. A single passage may legitimately
contain more than one activity (e.g., an extended passage may evaluate
trade-offs AND describe a concrete practice change). Do not force a
single-activity reading if genuine, substantial evidence of more than
one activity is present.

STEP 3 -- Select the PRIMARY activity according to which analytical
function is DOMINANT in the passage as a whole:
  - EVALUATION is dominant when the passage's primary work is assessing
    meaning, desirability, feasibility, credibility, consequences,
    risks, assumptions, or trade-offs.
  - NEGOTIATION is dominant when the passage's primary work is
    attempting to shape a collective trajectory by comparing, defending,
    questioning, rejecting, contesting, or expanding preferred futures in
    relation to other actors, authorities, or positions. Negotiation may
    be purely declarative (see Section B and Example 18) -- an imperative
    or direct address is a common but not required signal.
  - ENACTMENT is dominant when the passage's primary work is giving
    material or practical form to a preferred future through actual,
    planned, imagined, delayed, refused, or reconfigured practices.

STEP 4 -- If the passage ALSO contains substantial, separable evidence of
a second activity (and optionally a third), record it as a SECONDARY
CLASSIFICATION (0-2 entries). Only record a secondary classification when
there is a genuinely separable body of content large enough to be coded
on its own -- do not manufacture secondary classifications from marginal
or fragmentary content, and do not pad the array to reach a target count.

STEP 5 -- Determine the ORIENTATION for the PRIMARY classification, and
for each secondary classification, using the full configuration of
narrative, goal, emotion, temporality, relationship to the prescribed
future, and practice implications described in Section C. Do not infer
orientation from sentiment or tone alone.

STEP 6 -- Apply the disambiguation guidance in Sections B and C (AVOID
vs. COMPLEXIFY; DELAY vs. PREVENT; REJECT vs. CONTEST; AMBIVALENT vs.
EXPANDER) to resolve orientation for both primary and secondary
classifications.

STEP 7 -- If the input text appears to contain quotations from more than
one distinguishable speaker, or unrelated content that would be better
analyzed as separate segments, do not force it into a single artificial
reading. Instead, populate "input_scope_warning" with a brief note (e.g.,
"This input appears to contain quotations from more than one
distinguishable speaker; consider segmenting before analysis for a more
precise reading."). If the passage is coherent, leave
"input_scope_warning" as an empty string.

====================================================================
I. THEORETICALLY CONTRASTING ORIENTATION AND POTENTIAL CHALLENGE PATHWAYS
====================================================================

For EVERY text, in addition to classifying its primary (and any
secondary) activity/subtype/orientation, identify:
  1. "theoretically_contrasting_orientation": which of the OTHER THREE
     orientations holds the most contrasting narrative/goal/emotion/
     temporality relative to THIS SPECIFIC text. This is a theoretical
     contrast inferred from the framework, not an observed interaction,
     unless the source text itself preserves a visible exchange between
     different speakers.
  2. "potential_challenge_rationale": a content-specific explanation,
     citing specific phrases from THIS text, of how this text's
     performance COULD contribute to friction with a differently
     oriented performance IF one were also present in the same
     discussion or market. Do not state that the challenge has already
     occurred from this segment alone.

Do NOT compute the challenge pathway label(s) yourself -- they are
derived deterministically from your main_activity and
secondary_classifications by the calling application.

====================================================================
J. DIAGNOSTIC-SUPPORT OUTPUTS (NOT definitive recommendations)
====================================================================

This application supports the diagnostic steps of the roadmaps in
Sections E and F. For a single text segment, do not issue definitive
policy instruments or managerial interventions. Instead, for
policy_diagnostic_considerations and manager_diagnostic_considerations,
identify:
  - Which roadmap diagnostic step is most relevant to this text.
  - What additional evidence should be collected before acting.
  - Which assumptions or conditions this text suggests should be
    investigated.
  - What behavioral or interactional evidence would be needed before
    committing to a response.
  - Which general roadmap response directions may merit consideration
    (from Sections E/F), phrased as something to investigate, not as a
    definitive instruction.
Use hedged language: "could consider," "should investigate," "requires
additional evidence" -- rather than categorical prescriptions.

====================================================================
OUTPUT RULES
====================================================================

Select exactly ONE value for main_activity, activity_subtype, and
main_orientation. There is no "MIXED" option for these three fields.
Provide zero to two secondary_classifications ONLY when substantive,
separable evidence supports them (Section H, Step 4).

MANDATORY ORIENTATION-SUBTYPE PAIRING (applies to the primary
classification AND to every secondary classification -- never violate
this table):
  CATALYZER  -> SIMPLIFY (Evaluation) | ADVOCATE (Negotiation) | ACCELERATE (Enactment)
  AMBIVALENT -> STALL (Evaluation)    | QUESTION (Negotiation) | DELAY (Enactment)
  RESISTANT  -> AVOID (Evaluation)    | REJECT (Negotiation)   | PREVENT (Enactment)
  EXPANDER   -> COMPLEXIFY (Evaluation) | CONTEST (Negotiation) | REROUTE (Enactment)
Before finalizing your answer, verify that every activity_subtype (main
and secondary) belongs to the row matching its own orientation. If it
does not, re-evaluate and resolve the inconsistency before responding.

====================================================================
OUTPUT FORMAT -- Return ONLY valid JSON
====================================================================

{
  "prescribed_future_acknowledged": "Brief restatement of the prescribed future",

  "main_activity": "one single value: EVALUATION, NEGOTIATION, or ENACTMENT",
  "activity_subtype": "one single value: SIMPLIFY, STALL, AVOID, COMPLEXIFY, ADVOCATE, QUESTION, REJECT, CONTEST, ACCELERATE, DELAY, PREVENT, REROUTE",
  "activity_rationale": "Which step of the Decision Procedure applied, citing specific phrases",

  "secondary_classifications": [
    {
      "activity": "EVALUATION, NEGOTIATION, or ENACTMENT",
      "activity_subtype": "valid subtype for the orientation below",
      "orientation": "CATALYZER, AMBIVALENT, RESISTANT, or EXPANDER",
      "rationale": "brief text-specific explanation"
    }
  ],
  "input_scope_warning": "",

  "main_orientation": "one single value: CATALYZER, AMBIVALENT, RESISTANT, or EXPANDER",
  "orientation_confidence": "HIGH, MEDIUM, or LOW",
  "orientation_rationale": "Configuration of narrative, goal, emotion, temporality; cited phrases",
  "narrative_identified": "Name and description of the dominant narrative",
  "dominant_emotions": "Comma-separated list of emotions detected",
  "temporality_expressed": "...",
  "notable_conditions_of_adoption": "Which condition applies, if evident",

  "theoretically_contrasting_orientation": "One value among CATALYZER, AMBIVALENT, RESISTANT, EXPANDER -- not the main_orientation",
  "potential_challenge_rationale": "Content-specific, hedged explanation citing THIS text's phrases",

  "policy_diagnostic_considerations": {
    "step": "...", "objective": "...", "questions_and_evidence": [], "additional_considerations": []
  },
  "manager_diagnostic_considerations": {
    "step": "...", "objective": "...", "issues_to_investigate": [], "avoid": [], "communication_consideration": "..."
  }
}
"""

# ─────────────────────────────────────────
# ORIENTATION CONFIG
# ─────────────────────────────────────────
ORIENTATIONS = {
    "CATALYZER": {
        "color": "#27AE60", "bg": "#EAFAF1", "border": "#2ECC71",
        "goal": "Accelerate change toward the prescribed future",
        "narrative": "Urgency Narrative",
        "tagline": "Urgent, desirable, and already underway.",
        "temporality": "Present-focused -- The future is now",
        "activities": "Simplify - Advocate - Accelerate",
        "notable_conditions": (
            "High degree of alignment between current practices and "
            "prescribed future"
        )
    },
    "AMBIVALENT": {
        "color": "#D68910", "bg": "#FEFDE7", "border": "#F4D03F",
        "goal": "Slow or stage movement; delay decisions; balance risks and benefits",
        "narrative": "Pragmatic Narrative",
        "tagline": "Valuable, but conditions are not yet ready.",
        "temporality": "Gradual -- The future is contingent",
        "activities": "Stall - Question - Delay",
        "notable_conditions": "Limited resources to support change"
    },
    "RESISTANT": {
        "color": "#C0392B", "bg": "#FDEDEC", "border": "#E74C3C",
        "goal": "Contest the prescribed future; protect the status quo",
        "narrative": "Control Narrative",
        "tagline": "Threatens autonomy, identity, or rights.",
        "temporality": "Maintenance -- The future is distant / should not happen",
        "activities": "Avoid - Reject - Prevent",
        "notable_conditions": "Low degree of alignment between current practices and prescribed future"
    },
    "EXPANDER": {
        "color": "#7D3C98", "bg": "#F4ECF7", "border": "#9B59B6",
        "goal": "Expand and reroute the prescribed future; propose alternatives",
        "narrative": "Bigger Picture Narrative",
        "tagline": "The problem is framed too narrowly.",
        "temporality": "Envisioned -- Change will be broader than prescribed",
        "activities": "Complexify - Contest - Reroute",
        "notable_conditions": "Mismatch among current practices, normative practices, and the prescribed future"
    }
}

CHALLENGE_PATHWAYS = {
    "CONVOLUTED_EVALUATIONS": {
        "label": "Convoluted Evaluations",
        "color": "#2980B9", "bg": "#EBF5FB",
        "description": (
            "Signals that could contribute to Convoluted Evaluations if "
            "this evaluative performance clashes with differently oriented "
            "evaluations elsewhere in the discussion or market."
        )
    },
    "CONFRONTATIONAL_NEGOTIATIONS": {
        "label": "Confrontational Negotiations",
        "color": "#E67E22", "bg": "#FEF9E7",
        "description": (
            "Signals that could contribute to Confrontational Negotiations "
            "if this negotiating performance clashes with differently "
            "oriented negotiations elsewhere in the discussion or market."
        )
    },
    "COMPETING_ENACTMENTS": {
        "label": "Competing Enactments",
        "color": "#8E44AD", "bg": "#F5EEF8",
        "description": (
            "Signals that could contribute to Competing Enactments if this "
            "practice performance clashes with differently oriented "
            "enactments elsewhere in the discussion or market."
        )
    },
    "N/A": {
        "label": "Not Applicable",
        "color": "#999", "bg": "#FAFAFA",
        "description": "No potential challenge pathway could be derived."
    }
}

ACTIVITY_META = {
    "EVALUATION":  {
        "color": "#2980B9", "bg": "#EBF5FB",
        "definition": "Primarily assesses meaning, desirability, feasibility, or trade-offs of the prescribed future.",
        "subtypes": {"SIMPLIFY": "CATALYZER", "STALL": "AMBIVALENT",
                     "AVOID": "RESISTANT", "COMPLEXIFY": "EXPANDER"}
    },
    "NEGOTIATION": {
        "color": "#E67E22", "bg": "#FEF9E7",
        "definition": "Primarily attempts to shape a collective trajectory (may be purely declarative; imperative not required).",
        "subtypes": {"ADVOCATE": "CATALYZER", "QUESTION": "AMBIVALENT",
                     "REJECT": "RESISTANT", "CONTEST": "EXPANDER"}
    },
    "ENACTMENT":   {
        "color": "#8E44AD", "bg": "#F5EEF8",
        "definition": "Primarily gives material or practical form to a preferred future through the speaker's own practices.",
        "subtypes": {"ACCELERATE": "CATALYZER", "DELAY": "AMBIVALENT",
                     "PREVENT": "RESISTANT", "REROUTE": "EXPANDER"}
    },
}

PF_EV = (
    "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's "
    "net-zero emissions targets, as prescribed by Australia's National Electric "
    "Vehicle Strategy (2023)"
)

PF_NVES = (
    "Implement a national New Vehicle Efficiency Standard (NVES) in Australia to "
    "reduce transport emissions, as consulted on by the Australian Government's "
    "Department of Climate Change, Energy, the Environment and Water"
)

PF_AI_HEALTH = (
    "Transition all patients who enter primary care to AI-supported triage by 2030 "
    "(a specific, dated mandate -- illustrative of a Bounded intervention in the "
    "AI-integrated healthcare context)"
)

# ─────────────────────────────────────────
# POLICY & MANAGERIAL DIAGNOSTIC GUIDANCE (aggregate, document-level)
# Hedged, diagnostic-support language only.
# ─────────────────────────────────────────
POLICY_GUIDANCE = {
    "CATALYZER": {
        "implications": (
            "Catalyzer performances could indicate early evidence and "
            "implementation momentum, but may also obscure the specific "
            "conditions that made early adoption possible. Investigate "
            "which enabling conditions supported this pattern before "
            "assuming broader public value."
        ),
        "monitor": "Urgency and inevitability language; voluntary early adoption; advocacy for faster rollout.",
        "objective": "Investigate whether responsible acceleration is supported by evidence.",
        "questions_and_evidence": ["Time-limited pilots with independent evaluation",
                         "Reporting of failures and overrides",
                         "Subgroup/local validation before scaling",
                         "Predefined thresholds for expansion, modification, or withdrawal (to investigate, not to assume)"]
    },
    "AMBIVALENT": {
        "implications": (
            "Ambivalent performances may indicate specific, addressable "
            "conditions rather than generalized opposition. Investigate "
            "which technical, material, ethical, or institutional "
            "conditions are described as unresolved."
        ),
        "monitor": "Conditional language ('I would, but...', 'not yet'); requests for evidence; questions about liability, safety, or affordability.",
        "objective": "Investigate whether uncertainty can be converted into explicit, addressable conditions.",
        "questions_and_evidence": ["Impact assessments", "Staged authorization possibilities",
                         "Public registers", "Alternative pathway availability (to investigate)"]
    },
    "RESISTANT": {
        "implications": (
            "Resistant performances may reflect ideological opposition, "
            "identity threat, material disadvantage, or practical "
            "exclusion. Investigate which of these applies before "
            "designing a response, as each requires a different kind of "
            "evidence and response."
        ),
        "monitor": "Language on coercion, surveillance, loss of choice, discrimination, distrust; complaints, refusals, organized opposition.",
        "objective": "Investigate legitimacy and accountability concerns raised.",
        "questions_and_evidence": ["Whether appeal/human-review mechanisms exist", "Independent audit availability",
                         "Whether non-participation pathways are preserved (to investigate)"]
    },
    "EXPANDER": {
        "implications": (
            "Expander performances may reveal whether the prescribed "
            "future addresses narrow efficiency gains while leaving the "
            "underlying public problem unchanged. Investigate whether the "
            "proposed alternative complements or requires revising the "
            "current problem framing."
        ),
        "monitor": "Claims that the intervention does not solve the underlying problem; proposals for collective alternatives.",
        "objective": "Investigate whether the policy focus should be broadened.",
        "questions_and_evidence": ["Whether deliberative input has been sought", "Funding availability for complementary pathways (to investigate)"]
    },
}

MANAGER_GUIDANCE = {
    "CATALYZER": {
        "implications": (
            "Catalyzer enthusiasm may not generalize; investigate what "
            "resources and competencies supported early adoption before "
            "assuming replicability."
        ),
        "monitor": "Urgency/inevitability language, pilot participation, advocacy, referrals.",
        "objective": "Investigate whether enthusiasm reflects credible, generalizable experimentation.",
        "issues_to_investigate": ["Whether pilots are governed and documented", "Whether limitations are being reported",
                           "Whether early adopters are representative (to investigate, not assume)"],
        "avoid": ["Treating enthusiasm as evidence of inevitability without investigation"]
    },
    "AMBIVALENT": {
        "implications": (
            "Ambivalent hesitation may identify specific, addressable "
            "barriers. Investigate the specific conditions raised rather "
            "than treating this as generalized resistance to be overcome "
            "by persuasion alone."
        ),
        "monitor": "Conditional language, repeated comparison, requests for evidence/assistance, liability questions.",
        "objective": "Investigate whether generalized uncertainty reflects specific, addressable conditions.",
        "issues_to_investigate": ["Whether comparison tools or trials are available", "Whether training/human assistance is accessible"],
        "avoid": ["Assuming hesitation reflects ignorance without investigation", "Applying artificial urgency"]
    },
    "RESISTANT": {
        "implications": (
            "Investigate whether this reflects ideological opposition, "
            "identity threat, material disadvantage, or practical "
            "exclusion -- each requires different evidence before a "
            "response is designed."
        ),
        "monitor": "Language on surveillance, loss of choice, dehumanization, discrimination, distrust.",
        "objective": "Investigate legitimacy, autonomy, and accountability concerns.",
        "issues_to_investigate": ["Whether consultation or appeal mechanisms exist", "Whether opt-outs are preserved"],
        "avoid": ["\"There is no alternative\" messaging without investigation", "Ridicule"]
    },
    "EXPANDER": {
        "implications": (
            "Expander critique may reveal unmet systemic needs or "
            "alternative value propositions. Investigate rather than "
            "treat as out-of-scope."
        ),
        "monitor": "Claims the intervention does not solve the underlying problem; advocacy for collective alternatives.",
        "objective": "Investigate whether systemic critique warrants incorporation.",
        "issues_to_investigate": ["Whether participatory design input has been sought", "Whether alternative governance/service models are feasible"],
        "avoid": ["Presenting the offering as a complete solution without investigation"]
    },
}

CROSS_ORIENTATION_WARNING = (
    "Cross-orientation interference check: before finalizing a response, "
    "investigate whether a response tailored to one orientation could "
    "intensify concerns for another (e.g., performance-evidence campaigns "
    "aimed at Ambivalent audiences may deepen Resistant distrust, or "
    "reinforce Expander critique that the intervention is being oversold "
    "as a complete solution). This requires further evidence, not a single "
    "segment."
)

# ─────────────────────────────────────────
# BENCHMARK EXAMPLES -- built-in coded illustrations
# (used for the Coding Consistency Check, not empirical validation)
# ─────────────────────────────────────────
EXAMPLES = {
    "Select an example": {
        "prescribed": "", "comment": "", "activity": "", "subtype": "", "orientation": "",
        "secondary_expected": None
    },
    "CATALYZER | Evaluation -> Simplify": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "SIMPLIFY", "orientation": "CATALYZER",
        "secondary_expected": None,
        "comment": (
            "EVs are already cheaper to run than petrol cars once you factor in "
            "fuel and servicing costs, and battery prices have dropped so fast "
            "that price parity with ICE vehicles is basically here already. "
            "The range anxiety argument is outdated too, most new EVs now do "
            "400-500km on a single charge, which covers almost every day-to-day "
            "trip. Charging infrastructure has expanded so quickly in the last "
            "two years that finding a charger is rarely an issue in metro areas "
            "anymore. The transition is happening now, faster than most people "
            "expected, and every year the previous concerns keep getting "
            "resolved one by one."
        )
    },
    "CATALYZER | Negotiation -> Advocate": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "ADVOCATE", "orientation": "CATALYZER",
        "secondary_expected": None,
        "comment": (
            "Climate crisis is real. It's time to look at solar energy and "
            "electric vehicles, not the energy sources of the past like fossil "
            "fuels. "
            "When prices drop below $50k and charging times below 15 minutes, you "
            "can expect a real EV boom. "
            "More or less of a problem than handing my kids a planet that's an "
            "uninhabitable place? "
            "We need to act on transport emissions as quickly as possible. People "
            "are still buying new internal combustion vehicles due to the lack of "
            "choice of electric vehicles. Australia has demonstrated that it has "
            "an appetite for EVs, so let's get moving."
        )
    },
    "CATALYZER | Enactment -> Accelerate": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "ACCELERATE", "orientation": "CATALYZER",
        "secondary_expected": None,
        "comment": (
            "Our family has been living with an EV and a PHEV for 3 years and "
            "they are fantastic. There are many advantages and few disadvantages, "
            "apart from fictitious scenarios non-EV owners make up. "
            "Road trips up and down East Coast are simple in a Tesla, with "
            "superchargers it is easy, just a stop every 2.5 hours or so. "
            "We now both use our EV as our preferred first vehicle, the EV just "
            "ends up being nicer for road trips too. "
            "Proud owner of Model 3. I'll never own a gas combustion engine again, "
            "not even a hybrid. "
            "Bought our first EV largely for the environment, partly for fuel "
            "cost savings. Bought our second EV because they're just far better "
            "cars to own and drive."
        )
    },
    "AMBIVALENT | Evaluation -> Stall": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "STALL", "orientation": "AMBIVALENT",
        "secondary_expected": None,
        "comment": (
            "Range anxiety is overstated, however if you stay somewhere with no "
            "charging and need to drive 200-300km you are stuffed. "
            "I am far from being anti EV (I want one!) but I am also trying to "
            "weigh up all the facts. "
            "I'm not convinced yet that full EVs are the way to go. They seem to "
            "have quite a few problems, you know, battery disposal and other "
            "things. "
            "Perhaps these problems are over-exaggerated for views and I realise "
            "they will eventually be resolved with infrastructure and "
            "improvements in technology. I just don't see this happening "
            "adequately in the next few years. I'm willing to change my mind if "
            "my concerns are unfounded."
        )
    },
    "AMBIVALENT | Negotiation -> Question": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "QUESTION", "orientation": "AMBIVALENT",
        "secondary_expected": None,
        "comment": (
            "One of the arguments that is used for full EV's is the lower "
            "servicing costs but I'm guessing that a plug in hybrid still needs "
            "to be serviced like an ICE vehicle? I suppose that you could also "
            "include the benefits of investing the 17k difference over the 7 odd "
            "years you're trying to save money. Opportunity cost perhaps? I also "
            "can't help thinking that in a few years they will come out with a "
            "cheaper, more efficient or better technology that will render all of "
            "the current EV's completely worthless. "
            "We need to invest in infrastructure but at the same time limit the "
            "cost of doing so by not putting all eggs in the one basket. We "
            "should not place all our attention on EVs now as most of the "
            "electricity used to charge them is from burning coal. We should "
            "transition to hybrid vehicles instead of EVs until 2030."
        )
    },
    "AMBIVALENT | Enactment -> Delay": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "DELAY", "orientation": "AMBIVALENT",
        "secondary_expected": ("AMBIVALENT", "EVALUATION", "STALL"),
        "comment": (
            "Really good and interesting report! I am wanting to upgrade the car "
            "at a not too distant time and I am umming and aahing over PHEV or "
            "EV. EV would be magic but such a jump in price! PHEV seems great as "
            "a midway point as most of my driving is around town. "
            "Yep, the cost is indeed a huge hurdle. I think I'll be running my 12 "
            "year old Subaru Outback a bit longer! "
            "Just bought a new petrol car as the infrastructure still isn't in "
            "place. "
            "Hopefully, by the time my car does need to be replaced, EVs are a "
            "lot cheaper and the inconveniences are worked out. "
            "My car is doing all right, 13 years and 130,000 km, so good for "
            "another 13 years because it's diesel."
        )
    },
    "RESISTANT | Evaluation -> Avoid": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "AVOID", "orientation": "RESISTANT",
        "secondary_expected": None,
        "comment": (
            "Electric vehicles are not the solution, for Australia to take this "
            "up we are going to have to increase mining of precious minerals at "
            "a considerable amount, which in itself will contribute to "
            "greenhouse gases, the current electricity infrastructure can't keep "
            "up with the demand now let alone if everyone in inner city want "
            "electric cars being recharged in high rise complexes. I feel this "
            "is a lazy policy just appealing to city people and is just going to "
            "result in expensive car prices. "
            "EV and hybrid technology has long way to go especially here in "
            "Australia. Petrol and diesel vehicles will be around for many "
            "decades to come doing the jobs that EVs and hybrids just can't do. "
            "Electric vehicles are not the future, just a muddle point."
        )
    },
    "RESISTANT | Negotiation -> Reject": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "REJECT", "orientation": "RESISTANT",
        "secondary_expected": None,
        "comment": (
            "Is this communism, take away our freedom of choice! "
            "Australians are not as ignorant as the politicians think, and they "
            "research government push and now question the purpose behind these "
            "pushes. There's always big corporations behind any government move "
            "and if this country is taxed just for an ideology then the "
            "potential for even greater social unrest is likely. "
            "I think it's like being a vegan of the car world. People think it's "
            "a virtue signal, that you must be a snooty holier-than-thou type "
            "judging their non-participation and lifestyle which they take "
            "pride in and identify with. It's social policing because you're "
            "deviating from the norm. "
            "Yes they are just slapped together on the EV gravy train. Like any "
            "new technologies what are you going to do if your EV shits itself "
            "out in the middle of nowhere? You'd better be sitting down when you "
            "get the towing and repair bill for your 80 grand shit box. And you "
            "thought you would save money buying an EV?"
        )
    },
    "RESISTANT | Enactment -> Prevent": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "PREVENT", "orientation": "RESISTANT",
        "secondary_expected": None,
        "comment": (
            "I have had ICE cars for some 37 years and have found them to be "
            "very reliable. "
            "Why buy a new EV when my old car is doing all right, 13 years and "
            "130,000 km, so good for another 13 years because it's diesel. No "
            "matter what the price of an EV it's still cheaper to keep the car I "
            "own and repair. "
            "From the start of manufacturing to the end of the vehicle's life "
            "I'd easily put my money on ICE being a far better investment. "
            "Me, I'm sticking to my petrol vehicle til it dies."
        )
    },
    "EXPANDER | Evaluation -> Complexify": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "COMPLEXIFY", "orientation": "EXPANDER",
        "secondary_expected": None,
        "comment": (
            "Facilitating greater use of active, shared and public transport can "
            "cut climate pollution further and faster than electrifying "
            "vehicles, and do so this decade, because the effects are seen "
            "immediately through reduced use of private motor vehicle travel. "
            "The best way to help the environment is to buy less stuff and keep "
            "older stuff running for longer. "
            "This doesn't cover the destruction of the fabric of cities to "
            "accommodate cars. Gasoline or electric, the most significant "
            "environmental destruction that's caused by cars are the blight it "
            "causes to cities. 60% of the land in car-dependent cities are "
            "dedicated to cars, mainly parking and roads. Electric vehicle is a "
            "false solution if you care about the environment at all."
        )
    },
    "EXPANDER | Negotiation -> Contest": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "CONTEST", "orientation": "EXPANDER",
        "secondary_expected": None,
        "comment": (
            "Consumerism trumps facts. John you are so right but the first "
            "sentence prevails in modern society, why save the environment by "
            "keeping the car you already own and using it less, when you can "
            "join the Joneses, Smiths or whoever your neighbour is and spend "
            "money on that flash new hybrid/EV/hydrogen powered four wheeled "
            "status symbol that shows you earn more money than you need. But "
            "hey who am I to judge. "
            "Does it have to be a car? "
            "If your main priority was the environment, ride a bicycle. You're "
            "buying a 2-tonne metal box powered by a giant battery, let's not "
            "pretend we're saving the planet, we're just picking a lesser evil "
            "but it's still not good for the planet."
        )
    },
    "EXPANDER | Enactment -> Reroute": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "REROUTE", "orientation": "EXPANDER",
        "secondary_expected": ("EXPANDER", "NEGOTIATION", "CONTEST"),
        "comment": (
            "We tend to do most of our shopping by bike rather than with the ute "
            "because the ute's inconvenient to park and navigate in small car "
            "parks. "
            "So that's the plan, to extract maximum value out of that current "
            "vehicle until it is no longer functional. I am at the moment on a "
            "waiting list for a new electric cargo bike. "
            "The future is less cars, in higher density pedestrian, bike and "
            "train-orientated urban environments, where cars are secondary "
            "transport really only for those who really need it. "
            "I uprooted my life and moved from the Sunshine Coast to Melbourne "
            "with some of my strongest reasoning being the ability to use "
            "public transport, ride a bike around and use a car as little as "
            "possible."
        )
    },
}

# ─────────────────────────────────────────
# CONSISTENCY SAFEGUARD (applies to primary AND secondary classifications)
# ─────────────────────────────────────────

def _fix_pairing(orientation: str, activity: str, subtype: str):
    """Returns a (possibly corrected) subtype so that it belongs to the
    valid pairing row for the given orientation/activity, trusting
    orientation as the more reliable signal. Returns (subtype, note)."""
    subtype_map = ACTIVITY_META.get(activity, {}).get("subtypes", {})
    if not subtype_map:
        return subtype, None
    expected_orientation = subtype_map.get(subtype)
    if expected_orientation and expected_orientation != orientation:
        corrected = next((st for st, ori in subtype_map.items() if ori == orientation), None)
        if corrected:
            return corrected, f"subtype adjusted from {subtype} to {corrected} to match orientation {orientation}"
    return subtype, None


def enforce_consistency(result: dict) -> dict:
    """Defensive post-processing applied to BOTH the primary classification
    and every secondary classification."""
    notes = []

    main_orientation = _clean_enum(result.get("main_orientation", "")).upper()
    main_activity = _clean_enum(result.get("main_activity", "")).upper()
    main_subtype = _clean_enum(result.get("activity_subtype", "")).upper()
    fixed_subtype, note = _fix_pairing(main_orientation, main_activity, main_subtype)
    if note:
        result["activity_subtype"] = fixed_subtype
        notes.append(f"Primary: {note}.")
    else:
        result["activity_subtype"] = main_subtype

    secondary = get_secondary_classifications(result)
    fixed_secondary = []
    for i, sec in enumerate(secondary):
        ori = sec.get("orientation", "")
        act = sec.get("activity", "")
        sub = sec.get("activity_subtype", "")
        if act and sub and ori:
            fixed_sub, note2 = _fix_pairing(ori, act, sub)
            if note2:
                notes.append(f"Secondary #{i+1}: {note2}.")
            sec["activity_subtype"] = fixed_sub
        fixed_secondary.append(sec)
    result["secondary_classifications"] = fixed_secondary

    if notes:
        result["_consistency_note"] = " ".join(notes)
    return result


# ─────────────────────────────────────────
# CORE FUNCTIONS -- single-comment analysis
# ─────────────────────────────────────────

def analyze_comment(prescribed_future: str, comment: str, api_key: str) -> dict:
    client = openai.OpenAI(api_key=api_key)
    user_message = f"""
PRESCRIBED FUTURE:
{prescribed_future}

TEXT TO ANALYZE:
{comment}

Read the entire segment first, then apply the Decision Procedure (Section
H). Identify ALL substantive evidence of evaluation, negotiation, and
enactment before selecting a primary classification; if a second
activity is substantively and separably present, populate
secondary_classifications (0-2 entries, never padded). Negotiation may
be purely declarative and does not require an imperative or direct
address. If the input appears to mix content from multiple distinct
speakers or unrelated quotations, populate input_scope_warning instead of
forcing a single artificial reading. Verify every activity_subtype
(primary and secondary) belongs to the valid pairing table for its own
orientation before responding. Complete Section I
(theoretically_contrasting_orientation + potential_challenge_rationale)
using hedged language -- describe what COULD contribute to friction, not
what has already occurred. Populate policy_diagnostic_considerations and
manager_diagnostic_considerations as diagnostic support only (Section
J): identify relevant roadmap steps, evidence to collect, and assumptions
to investigate -- do not issue definitive recommendations from this
single text segment.
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message}
        ],
        response_format={"type": "json_object"},
        temperature=0
    )
    parsed = json.loads(response.choices[0].message.content)
    parsed = enforce_consistency(parsed)
    return parsed


def run_consistency_suite(api_key: str) -> dict:
    """Internal quality-control tool: tests whether the current prompt
    reproduces predetermined coding decisions for a set of benchmark
    examples. This does NOT constitute empirical validation, intercoder
    reliability, or evidence of generalizability -- it only checks
    agreement with predetermined benchmark examples."""
    results = []
    for name, ex in EXAMPLES.items():
        if not ex.get("comment"):
            continue
        try:
            pred = analyze_comment(ex["prescribed"], ex["comment"], api_key)
        except Exception as e:
            results.append({
                "example": name, "error": str(e),
                "expected": (ex["orientation"], ex["activity"], ex["subtype"]),
                "predicted": (None, None, None), "match": False,
                "secondary_expected": ex.get("secondary_expected"),
                "secondary_match": None
            })
            continue
        pred_orientation = _clean_enum(pred.get("main_orientation", "")).upper()
        pred_activity    = _clean_enum(pred.get("main_activity", "")).upper()
        pred_subtype     = _clean_enum(pred.get("activity_subtype", "")).upper()
        match = (
            pred_orientation == ex["orientation"]
            and pred_activity == ex["activity"]
            and pred_subtype == ex["subtype"]
        )

        secondary_match = None
        sec_expected = ex.get("secondary_expected")
        if sec_expected:
            secondary_list = get_secondary_classifications(pred)
            secondary_match = any(
                sec.get("orientation") == sec_expected[0]
                and sec.get("activity") == sec_expected[1]
                and sec.get("activity_subtype") == sec_expected[2]
                for sec in secondary_list
            )

        results.append({
            "example": name,
            "expected": (ex["orientation"], ex["activity"], ex["subtype"]),
            "predicted": (pred_orientation, pred_activity, pred_subtype),
            "match": match,
            "secondary_expected": sec_expected,
            "secondary_match": secondary_match
        })
    if not results:
        return {"results": [], "overall_agreement": 0.0}
    agreement = sum(r["match"] for r in results) / len(results)
    return {"results": results, "overall_agreement": agreement}


# ─────────────────────────────────────────
# DOCUMENT / CORPUS ANALYSIS FUNCTIONS
# ─────────────────────────────────────────

def extract_text_from_pdf(uploaded_file) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        st.error(
            "PDF support requires the 'pypdf' package. Add pypdf to "
            "requirements.txt and redeploy. In the meantime, you can paste "
            "the text directly using the 'Paste text' option below."
        )
        return ""
    reader = PdfReader(uploaded_file)
    text_parts = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(text_parts)


def split_into_chunks(
    text: str,
    granularity: str = "paragraph",
    sentences_per_chunk: int = 3,
    min_words: int = 8,
    max_chars: int = 900
) -> list:
    text = (text or "").strip()
    if not text:
        return []

    if granularity == "sentence_group":
        flat = re.sub(r'\s+', ' ', text)
        sentences = re.split(r'(?<=[.!?])\s+', flat)
        sentences = [s.strip() for s in sentences if s.strip()]
        chunks = []
        for i in range(0, len(sentences), sentences_per_chunk):
            group = " ".join(sentences[i:i + sentences_per_chunk])
            chunks.append(group)
    else:
        raw_paragraphs = re.split(r'\n\s*\n+', text)
        chunks = []
        for para in raw_paragraphs:
            para = re.sub(r'\s+', ' ', para).strip()
            if not para:
                continue
            if len(para) > max_chars:
                sub_sentences = re.split(r'(?<=[.!?])\s+', para)
                current = ""
                for sent in sub_sentences:
                    if len(current) + len(sent) + 1 <= max_chars:
                        current = (current + " " + sent).strip()
                    else:
                        if current:
                            chunks.append(current)
                        current = sent
                if current:
                    chunks.append(current)
            else:
                chunks.append(para)

    return [c for c in chunks if len(c.split()) >= min_words]


def extract_public_consultation_responses(text: str, min_words: int = 4) -> list:
    """Detects tabular public-consultation exports: each response starts
    with a 6-7 digit ID, followed by 'Name withheld' (or a real name), a
    ranking of options, a free-text comment, and a Yes/No/NULL support
    indicator. Returns free-text comments only, one per respondent."""
    text = re.sub(r'\s+', ' ', text.strip())
    id_pattern = re.compile(r'(?=\b\d{6,7}\s+(?:Name\s+withheld|[A-Z][a-z]+))')
    raw_blocks = id_pattern.split(text)
    raw_blocks = [b.strip() for b in raw_blocks if b.strip()]

    responses = []
    for block in raw_blocks:
        block = re.sub(
            r'^\d{6,7}\s+(?:Name\s+withheld|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*',
            '', block
        )
        block = re.sub(
            r'Option\s+[ABC]\s*-\s*\w+,?\s*',
            '', block, flags=re.IGNORECASE
        )
        block = re.sub(r'\b(Yes|No|NULL)\s*$', '', block, flags=re.IGNORECASE).strip()

        if not block or block.upper() == "NULL":
            continue

        block = re.sub(r'\s{2,}', ' ', block).strip(' ,.-')

        if len(block.split()) >= min_words and block.upper() != "NULL":
            responses.append(block)

    return responses


def compute_evenly_spaced_sample_indices(total: int, k: int) -> list:
    """Returns up to k distinct 0-based indices evenly distributed across
    range(total), preserving original document order, so a limited sample
    is drawn from the beginning, middle, and end rather than always the
    first k segments."""
    if total <= 0 or k <= 0:
        return []
    if k >= total:
        return list(range(total))
    if k == 1:
        return [total // 2]
    step = (total - 1) / (k - 1)
    seen = set()
    for i in range(k):
        idx = int(round(i * step))
        idx = max(0, min(total - 1, idx))
        probe = idx
        forward = True
        while probe in seen:
            probe = probe + 1 if forward else probe - 1
            if probe >= total:
                probe = idx
                forward = False
                continue
            if probe < 0:
                break
        seen.add(max(0, min(total - 1, probe)))
    return sorted(seen)


def analyze_document(indexed_chunks: list, prescribed_future: str, api_key: str, progress_bar=None) -> list:
    """indexed_chunks: list of (original_index, text) tuples. Returns
    results sorted by original_index to preserve document order."""
    total = len(indexed_chunks)
    results = [None] * total
    with concurrent.futures.ThreadPoolExecutor(max_workers=DOC_MAX_WORKERS) as executor:
        future_to_pos = {
            executor.submit(analyze_comment, prescribed_future, text, api_key): pos
            for pos, (orig_idx, text) in enumerate(indexed_chunks)
        }
        completed = 0
        for future in concurrent.futures.as_completed(future_to_pos):
            pos = future_to_pos[future]
            orig_idx, text = indexed_chunks[pos]
            try:
                r = future.result()
            except Exception as e:
                r = {"_error": str(e)}
            r["_chunk_text"] = text
            r["_chunk_index"] = orig_idx
            results[pos] = r
            completed += 1
            if progress_bar is not None:
                progress_bar.progress(completed / total, text=f"Analyzed {completed}/{total} segments...")
    results_sorted = sorted(
        [r for r in results if r is not None],
        key=lambda r: r.get("_chunk_index", 0)
    )
    return results_sorted


def summarize_document_results(results: list) -> dict:
    valid = [r for r in results if r and "_error" not in r]
    errors = [r for r in results if r and "_error" in r]
    n = len(valid)
    if n == 0:
        return {"n_analyzed": 0, "n_errors": len(errors)}

    orientation_counts, activity_counts, challenge_counts = {}, {}, {}
    contrast_pairs = {}

    for r in valid:
        ori = _clean_enum(r.get("main_orientation", "")).upper()
        act = _clean_enum(r.get("main_activity", "")).upper()
        secondary = get_secondary_classifications(r)
        pathways = derive_challenge_pathways(act, secondary)
        contrast = get_contrasting_orientation(r)

        if ori:
            orientation_counts[ori] = orientation_counts.get(ori, 0) + 1
        if act:
            activity_counts[act] = activity_counts.get(act, 0) + 1
        for p in pathways:
            challenge_counts[p] = challenge_counts.get(p, 0) + 1
        if ori in ORIENTATIONS and contrast in ORIENTATIONS:
            pair = tuple(sorted([ori, contrast]))
            contrast_pairs[pair] = contrast_pairs.get(pair, 0) + 1

    most_frequent_orientation = max(orientation_counts, key=orientation_counts.get) if orientation_counts else None
    most_frequent_activity = max(activity_counts, key=activity_counts.get) if activity_counts else None
    most_frequent_challenge = max(challenge_counts, key=challenge_counts.get) if challenge_counts else None

    return {
        "n_analyzed": n,
        "n_errors": len(errors),
        "orientation_counts": orientation_counts,
        "activity_counts": activity_counts,
        "challenge_counts": challenge_counts,
        "contrast_pairs": contrast_pairs,
        "most_frequent_orientation": most_frequent_orientation,
        "most_frequent_activity": most_frequent_activity,
        "most_frequent_challenge": most_frequent_challenge,
    }


def build_narrative_summary(summary: dict, intervention_type_key: str = None) -> str:
    n = summary.get("n_analyzed", 0)
    if n == 0:
        return "No segments could be analyzed."

    ori_counts = summary["orientation_counts"]
    chal_counts = summary["challenge_counts"]
    most_freq_ori = summary.get("most_frequent_orientation")
    most_freq_chal = summary.get("most_frequent_challenge")

    def pct(cnt):
        return round(cnt / n * 100, 1)

    lines = []

    if most_freq_ori:
        ori_meta = ORIENTATIONS.get(most_freq_ori, {})
        lines.append(
            f"Across **{n}** analyzed segments, the most frequently identified "
            f"dominant orientation is **{most_freq_ori}** "
            f"({pct(ori_counts[most_freq_ori])}% of segments), associated with a "
            f"*{ori_meta.get('narrative','')}* -- \"{ori_meta.get('tagline','')}\""
        )

    sorted_ori = sorted(ori_counts.items(), key=lambda x: -x[1])
    ori_dist = ", ".join(f"{k} {pct(v)}%" for k, v in sorted_ori)
    lines.append(
        f"**Orientation distribution among analyzed segments:** {ori_dist}. "
        f"These percentages describe text segments, not unique consumers, "
        f"organizations, or population prevalence."
    )

    if most_freq_chal and most_freq_chal != "N/A":
        chal_meta = CHALLENGE_PATHWAYS.get(most_freq_chal, {})
        lines.append(
            f"The most frequently identified potential challenge pathway is "
            f"**{chal_meta.get('label', most_freq_chal)}** "
            f"({pct(chal_counts[most_freq_chal])}% of segments carry this "
            f"signal): {chal_meta.get('description','')}"
        )

    n_orientations_present = len([k for k, v in ori_counts.items() if v > 0])
    if n_orientations_present >= 2:
        lines.append(
            "Multiple future-making orientations were detected within the "
            "analyzed segments. This heterogeneity identifies a need for "
            "contextual examination of whether differently oriented "
            "performances coexist, clash, or interfere with one another. "
            "Orientation diversity alone does not establish Fragile Futures."
        )
    else:
        lines.append(
            "A single orientation was identified across all analyzed "
            "segments. This does not, by itself, indicate an absence of "
            "diversity in the broader population -- it describes only the "
            "analyzed sample."
        )

    if intervention_type_key and intervention_type_key in INTERVENTION_TYPES:
        it = INTERVENTION_TYPES[intervention_type_key]
        if it.get("note"):
            lines.append(
                f"**Intervention type context** ({intervention_type_key.split(' (')[0]}, "
                f"{it['scope']} scope / {it['prescriptiveness']} prescriptive): "
                f"{it['note']} This is contextual information; it does not "
                f"predetermine the orientations or challenge pathways found "
                f"above."
            )

    return "\n\n".join(lines)


def render_pct_bars(counts: dict, meta_dict: dict, total: int, label_key_name=None):
    if total == 0:
        st.caption("No data to display.")
        return
    for key, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        pct_val = round(cnt / total * 100, 1)
        meta = meta_dict.get(key, {})
        color = meta.get("color", "#888")
        display_name = meta.get(label_key_name, key) if label_key_name else key
        st.markdown(f"""
        <div style="margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px;">
                <span><strong>{display_name}</strong></span>
                <span style="color:#666;">{cnt} segments ({pct_val}%)</span>
            </div>
            <div style="background:#eee;border-radius:6px;height:14px;width:100%;overflow:hidden;">
                <div style="background:{color};width:{pct_val}%;height:14px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def _serialize_secondary(secondary_list: list) -> str:
    if not secondary_list:
        return ""
    parts = []
    for sec in secondary_list:
        parts.append(
            f"{sec.get('orientation','')}/{sec.get('activity','')}/"
            f"{sec.get('activity_subtype','')}: {sec.get('rationale','')}"
        )
    return " || ".join(parts)


def _serialize_considerations(d: dict) -> str:
    if not d:
        return ""
    parts = [f"Step: {d.get('step','')}", f"Objective: {d.get('objective','')}"]
    for key in ("questions_and_evidence", "additional_considerations",
                "issues_to_investigate", "avoid"):
        vals = d.get(key)
        if vals:
            parts.append(f"{key}: " + "; ".join(vals))
    if d.get("communication_consideration"):
        parts.append(f"communication_consideration: {d.get('communication_consideration')}")
    return " | ".join(parts)


def build_results_dataframe(results: list) -> pd.DataFrame:
    rows = []
    for r in results:
        if not r:
            continue
        if "_error" in r:
            rows.append({
                "segment_index": r.get("_chunk_index", ""),
                "segment_text": r.get("_chunk_text", ""),
                "main_orientation": "ERROR", "main_activity": "", "main_subtype": "",
                "secondary_classifications": "", "potential_challenge_pathways": "",
                "theoretically_contrasting_orientation": "",
                "orientation_rationale": "", "activity_rationale": "",
                "challenge_pathway_rationale": "", "input_scope_warning": "",
                "policy_diagnostic_considerations": "", "manager_diagnostic_considerations": "",
                "error": r.get("_error", "")
            })
            continue
        act = _clean_enum(r.get("main_activity", "")).upper()
        secondary = get_secondary_classifications(r)
        pathways = derive_challenge_pathways(act, secondary)
        pathway_labels = [CHALLENGE_PATHWAYS.get(p, {}).get("label", p) for p in pathways]
        rows.append({
            "segment_index": r.get("_chunk_index", ""),
            "segment_text": r.get("_chunk_text", ""),
            "main_orientation": _clean_enum(r.get("main_orientation", "")).upper(),
            "main_activity": act,
            "main_subtype": _clean_enum(r.get("activity_subtype", "")).upper(),
            "secondary_classifications": _serialize_secondary(secondary),
            "potential_challenge_pathways": "; ".join(pathway_labels),
            "theoretically_contrasting_orientation": get_contrasting_orientation(r),
            "orientation_rationale": r.get("orientation_rationale", ""),
            "activity_rationale": r.get("activity_rationale", ""),
            "challenge_pathway_rationale": r.get("potential_challenge_rationale", ""),
            "input_scope_warning": get_input_scope_warning(r),
            "policy_diagnostic_considerations": _serialize_considerations(get_policy_considerations(r)),
            "manager_diagnostic_considerations": _serialize_considerations(get_manager_considerations(r)),
            "error": ""
        })
    return pd.DataFrame(rows)


def show_document_summary(results: list, prescribed_future: str, intervention_type_key: str = None,
                           total_analyzable: int = None, sampling_description: str = ""):
    summary = summarize_document_results(results)
    n = summary.get("n_analyzed", 0)
    n_errors = summary.get("n_errors", 0)

    if n == 0:
        st.error("No segments could be successfully analyzed.")
        return

    st.markdown(f"""
    <div style="background:#EBF5FB;border-left:5px solid #2980B9;border-radius:8px;
                padding:12px 18px;margin-bottom:16px;">
        <strong style="color:#2980B9;">Prescribed Future Analyzed:</strong><br>
        <em style="color:#333;">{prescribed_future}</em>
    </div>
    """, unsafe_allow_html=True)

    if sampling_description:
        st.caption(f"**Sampling:** {sampling_description}")

    st.info(INTERPRETIVE_USE_NOTE)

    if n_errors:
        st.warning(f"{n_errors} segment(s) failed to analyze and were excluded from the summary.")

    st.markdown("### Executive Summary")
    st.markdown(build_narrative_summary(summary, intervention_type_key))

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### Dominant Orientations Within Analyzed Segments")
        render_pct_bars(summary["orientation_counts"], ORIENTATIONS, n)
        st.caption("Percentages describe analyzed text segments, not unique consumers or population prevalence.")
    with col2:
        st.markdown("#### Activity Distribution")
        render_pct_bars(summary["activity_counts"], ACTIVITY_META, n)
    with col3:
        st.markdown("#### Potential Challenge Signals")
        render_pct_bars(summary["challenge_counts"], CHALLENGE_PATHWAYS, n, label_key_name="label")
        st.caption("A signal indicates a segment's activity could contribute to this pathway if it clashes with a differently oriented performance -- it does not confirm the challenge occurred.")

    st.markdown("---")
    st.markdown("### Most Frequent Theoretical Contrast Pairs")
    st.caption(
        "These pairs represent theoretically contrasting orientations inferred "
        "from individual segments. They are NOT observed interactions unless "
        "the source data preserve an actual exchange between speakers."
    )
    contrast_pairs = summary.get("contrast_pairs", {})
    if contrast_pairs:
        sorted_pairs = sorted(contrast_pairs.items(), key=lambda x: -x[1])
        for pair, cnt in sorted_pairs[:6]:
            o1, o2 = pair
            pct_val = round(cnt / n * 100, 1)
            st.markdown(f"- **{o1}** vs. **{o2}**: {cnt} segments ({pct_val}%)")
    else:
        st.caption("No contrast pairs identified.")

    st.markdown("---")
    st.markdown("### Diagnostic Considerations by Orientation")
    st.caption(
        "These considerations support the diagnostic steps of the policy and "
        "managerial roadmaps. They are not definitive recommendations."
    )
    top_orientations = sorted(summary["orientation_counts"].items(), key=lambda x: -x[1])[:2]
    policy_tab, manager_tab = st.tabs(["Policy Diagnostic Considerations", "Managerial Diagnostic Considerations"])

    with policy_tab:
        for ori, cnt in top_orientations:
            guidance = POLICY_GUIDANCE.get(ori, {})
            cfg = ORIENTATIONS.get(ori, {})
            pct_val = round(cnt / n * 100, 1)
            st.markdown(f"**{ori}** ({pct_val}% of segments) -- \"{cfg.get('tagline','')}\"")
            st.markdown(f"*Could indicate:* {guidance.get('implications','--')}")
            st.markdown(f"*Monitor for:* {guidance.get('monitor','--')}")
            st.markdown(f"*Objective:* {guidance.get('objective','--')}")
            for q in guidance.get("questions_and_evidence", []):
                st.markdown(f"- {q}")
            st.markdown("")

    with manager_tab:
        for ori, cnt in top_orientations:
            guidance = MANAGER_GUIDANCE.get(ori, {})
            cfg = ORIENTATIONS.get(ori, {})
            pct_val = round(cnt / n * 100, 1)
            st.markdown(f"**{ori}** ({pct_val}% of segments) -- \"{cfg.get('tagline','')}\"")
            st.markdown(f"*Could indicate:* {guidance.get('implications','--')}")
            st.markdown(f"*Monitor for:* {guidance.get('monitor','--')}")
            st.markdown(f"*Objective:* {guidance.get('objective','--')}")
            for issue in guidance.get("issues_to_investigate", []):
                st.markdown(f"- {issue}")
            avoid_list = guidance.get("avoid", [])
            if avoid_list:
                st.markdown(f"*Avoid:* {', '.join(avoid_list)}")
            st.markdown("")
        if len(top_orientations) >= 2:
            st.info(CROSS_ORIENTATION_WARNING)

    st.markdown("---")
    st.markdown("### Segment-Level Detail")
    df = build_results_dataframe(results)
    display_cols = ["segment_index", "main_orientation", "main_activity",
                     "main_subtype", "potential_challenge_pathways",
                     "theoretically_contrasting_orientation", "input_scope_warning"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols] if display_cols else df, use_container_width=True, height=350)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download full results as CSV (includes complete text and all rationale fields)",
        data=csv_bytes,
        file_name="future_making_document_analysis.csv",
        mime="text/csv"
    )

    st.markdown("---")
    st.markdown("### Segment Rationale Explorer")
    st.caption(
        "Select an individual segment below to see its full classification, "
        "secondary classifications, and rationale, presented the same way as "
        "in the single-comment analysis view."
    )

    valid_indexed = [(i, r) for i, r in enumerate(results) if r and "_error" not in r]
    if valid_indexed:
        option_labels = [
            f"Segment (original index {r.get('_chunk_index', i)}): {r.get('_chunk_text', '')[:90]}..."
            for i, r in valid_indexed
        ]
        chosen_pos = st.selectbox(
            "Choose a segment to inspect:",
            options=range(len(option_labels)),
            format_func=lambda x: option_labels[x]
        )
        chosen_idx, chosen_result = valid_indexed[chosen_pos]
        st.markdown("**Full segment text:**")
        st.info(chosen_result.get("_chunk_text", ""))
        show_results(chosen_result, prescribed_future, show_interpretive_note=False)
    else:
        st.caption("No valid segments available to explore.")


# ─────────────────────────────────────────
# UI HELPER FUNCTIONS -- single comment
# ─────────────────────────────────────────

def show_example_badge(ex_data: dict):
    if not ex_data.get("activity"):
        return
    ori, act, sub = ex_data.get("orientation", ""), ex_data.get("activity", ""), ex_data.get("subtype", "")
    cfg, ameta = ORIENTATIONS.get(ori, {}), ACTIVITY_META.get(act, {})
    if not cfg or not ameta:
        return
    st.markdown(f"""
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap;">
        <span style="background:{cfg['bg']};border:2px solid {cfg['border']};color:{cfg['color']};
                     border-radius:20px;padding:4px 14px;font-weight:bold;font-size:13px;">
            {ori}
        </span>
        <span style="font-size:16px;color:#aaa;">-></span>
        <span style="background:{ameta['bg']};border:2px solid {ameta['color']};color:{ameta['color']};
                     border-radius:20px;padding:4px 14px;font-weight:bold;font-size:13px;">
            {act}
        </span>
        <span style="font-size:16px;color:#aaa;">-></span>
        <span style="background:#f0f0f0;border:2px solid #bbb;color:#444;
                     border-radius:20px;padding:4px 14px;font-weight:bold;font-size:13px;">
            {sub}
        </span>
    </div>
    """, unsafe_allow_html=True)


def show_results(result: dict, prescribed_future: str, show_interpretive_note: bool = True):
    orientation = _clean_enum(result.get("main_orientation", "")).upper().strip()
    main_act    = _clean_enum(result.get("main_activity", "")).upper().strip()
    act_sub     = _clean_enum(result.get("activity_subtype", "N/A")).upper().strip()

    secondary = get_secondary_classifications(result)
    pathways = derive_challenge_pathways(main_act, secondary)
    primary_pathway_key = pathways[0] if pathways else "N/A"
    chg = CHALLENGE_PATHWAYS.get(primary_pathway_key, CHALLENGE_PATHWAYS["N/A"])

    if show_interpretive_note:
        st.info(INTERPRETIVE_USE_NOTE)

    st.markdown(f"""
    <div style="background:#EBF5FB;border-left:5px solid #2980B9;border-radius:8px;
                padding:12px 18px;margin-bottom:16px;">
        <strong style="color:#2980B9;">Prescribed Future Analyzed:</strong><br>
        <em style="color:#333;">{prescribed_future}</em>
    </div>
    """, unsafe_allow_html=True)

    warning_text = get_input_scope_warning(result)
    if warning_text:
        st.warning(f"Input-scope note: {warning_text}")

    if result.get("_consistency_note"):
        st.caption(f"Note: {result['_consistency_note']}")

    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        cfg = ORIENTATIONS.get(orientation, {})
        st.markdown(f"""
        <div style="background:{cfg.get('bg','#f5f5f5')};border-left:6px solid {cfg.get('border','#999')};
                    border-radius:10px;padding:16px 18px;min-height:230px;">
            <h3 style="color:{cfg.get('color','#555')};margin:0;font-size:22px;">
                {orientation}
            </h3>
            <p style="color:#666;margin:4px 0 3px;font-size:12px;">
                <strong>Confidence:</strong> {result.get('orientation_confidence','N/A')}
            </p>
            <p style="color:#777;margin:2px 0;font-size:11px;font-style:italic;">"{cfg.get('tagline','')}"</p>
            <p style="color:#777;margin:2px 0;font-size:11px;">{cfg.get('narrative','')}</p>
            <p style="color:#777;margin:2px 0;font-size:11px;">{cfg.get('temporality','')}</p>
            <p style="color:#777;margin:2px 0;font-size:11px;">{cfg.get('goal','')}</p>
            <p style="color:#999;margin:4px 0 0;font-size:10px;">{cfg.get('activities','')}</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        ameta = ACTIVITY_META.get(main_act, {})
        sub_cfg = ORIENTATIONS.get(orientation, {})
        st.markdown(f"""
        <div style="background:{ameta.get('bg','#f5f5f5')};border-left:6px solid {ameta.get('color','#555')};
                    border-radius:10px;padding:16px 18px;min-height:230px;">
            <h3 style="color:{ameta.get('color','#555')};margin:0;font-size:20px;">
                {main_act}
            </h3>
            <p style="color:#555;margin:4px 0 3px;font-size:12px;"><strong>Primary Future-Making Activity</strong></p>
            <span style="background:{sub_cfg.get('bg','#f5f5f5')};border:1.5px solid {sub_cfg.get('color','#555')};
                         color:{sub_cfg.get('color','#555')};border-radius:12px;
                         padding:3px 10px;font-weight:bold;font-size:12px;">
                -> {act_sub}
            </span>
            <p style="color:#777;margin:8px 0 0;font-size:11px;font-style:italic;">
                {ameta.get('definition','')[:180]}
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        pathway_labels = [CHALLENGE_PATHWAYS.get(p, {}).get("label", p) for p in pathways]
        st.markdown(f"""
        <div style="background:{chg['bg']};border-left:6px solid {chg['color']};
                    border-radius:10px;padding:16px 18px;min-height:230px;">
            <h3 style="color:{chg['color']};margin:0;font-size:20px;">{chg['label']}</h3>
            <p style="color:#555;margin:4px 0 3px;font-size:12px;"><strong>Potential Challenge Pathway</strong></p>
            <p style="color:#999;margin:0 0 4px;font-size:10px;">(potential only -- requires a clash with a differently oriented performance)</p>
            <p style="color:#777;margin:3px 0;font-size:11px;">{chg['description']}</p>
            {"<p style='color:#999;margin:4px 0 0;font-size:10px;'>Additional signals: " + ", ".join(pathway_labels[1:]) + "</p>" if len(pathway_labels) > 1 else ""}
        </div>
        """, unsafe_allow_html=True)

    contrast_ori = get_contrasting_orientation(result)
    contrast_cfg = ORIENTATIONS.get(contrast_ori)
    if contrast_cfg:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:#FFF8F0;border:2px dashed #E67E22;border-radius:10px;
                    padding:16px 18px;">
            <h4 style="color:#E67E22;margin:0 0 8px;font-size:16px;">
                Theoretically Contrasting Orientation
            </h4>
            <p style="font-size:13px;color:#555;margin:0 0 6px;">
                This segment's configuration of narrative, goal, emotion, and
                temporality most theoretically contrasts with a
                <strong style="color:{contrast_cfg['color']};">{contrast_ori}</strong>
                orientation. This is a theoretical contrast inferred from the
                framework, not an observed interaction, unless the source data
                preserve an actual exchange between speakers.
            </p>
            <p style="font-size:12px;color:#777;font-style:italic;margin:0;">
                "{result.get('potential_challenge_rationale','--')}"
            </p>
        </div>
        """, unsafe_allow_html=True)

    if secondary:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Secondary Classification(s)")
        st.caption(
            "Substantive, separable content also detected in this segment, "
            "captured alongside the primary classification rather than "
            "discarded."
        )
        for sec in secondary:
            sec_ori = sec.get("orientation", "")
            sec_act = sec.get("activity", "")
            sec_sub = sec.get("activity_subtype", "")
            sec_cfg = ORIENTATIONS.get(sec_ori, {})
            sec_ameta = ACTIVITY_META.get(sec_act, {})
            st.markdown(f"""
            <div style="border:1px solid #ddd;border-radius:8px;padding:10px 14px;margin-bottom:8px;background:#fafafa;">
                <span style="background:{sec_cfg.get('bg','#eee')};border:1.5px solid {sec_cfg.get('border','#999')};
                             color:{sec_cfg.get('color','#555')};border-radius:14px;padding:3px 10px;
                             font-weight:bold;font-size:12px;">{sec_ori or 'N/A'}</span>
                &nbsp;-> &nbsp;
                <span style="background:{sec_ameta.get('bg','#eee')};border:1.5px solid {sec_ameta.get('color','#999')};
                             color:{sec_ameta.get('color','#555')};border-radius:14px;padding:3px 10px;
                             font-weight:bold;font-size:12px;">{sec_act or 'N/A'} / {sec_sub or 'N/A'}</span>
                <p style="font-size:12px;color:#666;margin:6px 0 0;">{sec.get('rationale','')}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab_ori, tab_act, tab_chg = st.tabs(["Orientation Rationale", "Activity Rationale", "Challenge Pathway Rationale"])

    with tab_ori:
        st.markdown("**Why this orientation? (configuration of narrative, goal, emotion, temporality)**")
        st.write(result.get("orientation_rationale", "--"))
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown("**Narrative**"); st.caption(result.get("narrative_identified", "--"))
        with c2:
            st.markdown("**Emotions**"); st.caption(result.get("dominant_emotions", "--"))
        with c3:
            st.markdown("**Temporality**"); st.caption(result.get("temporality_expressed", "--"))
        with c4:
            st.markdown("**Notable Conditions**"); st.caption(result.get("notable_conditions_of_adoption", "--"))

    with tab_act:
        st.markdown("**Why this activity is primary? (Decision Procedure applied)**")
        st.write(result.get("activity_rationale", "--"))
        st.markdown("---")
        st.markdown("**Activity Definitions**")
        for act_name, meta in ACTIVITY_META.items():
            is_main = (act_name == main_act)
            border  = f"3px solid {meta['color']}" if is_main else "1px solid #ddd"
            st.markdown(f"""
            <div style="border:{border};border-radius:8px;padding:10px 14px;
                        margin-bottom:8px;background:{'#fff' if is_main else '#fafafa'};">
                <strong style="color:{meta['color']};">{act_name}</strong>
                {'<span style="background:#27AE60;color:white;border-radius:8px;'
                 'padding:1px 8px;font-size:11px;margin-left:8px;">PRIMARY</span>'
                 if is_main else ''}<br>
                <span style="font-size:11px;color:#555;">{meta['definition']}</span>
            </div>
            """, unsafe_allow_html=True)

    with tab_chg:
        st.markdown("**How could this comment contribute to a future-making challenge?**")
        st.write(result.get("potential_challenge_rationale", "--"))
        pathway_labels_full = [CHALLENGE_PATHWAYS.get(p, {}).get("label", p) for p in pathways]
        st.caption(
            f"Deterministic mapping applied (primary + secondary activities): "
            f"{', '.join(pathway_labels_full) if pathway_labels_full else 'N/A'}. "
            f"These are potential pathways, not confirmed challenges."
        )

    st.markdown("---")
    st.markdown("## Diagnostic Support (Policy and Managerial)")
    st.caption(
        "These outputs support the diagnostic steps of the roadmaps below. "
        "They are not definitive recommendations from a single text segment."
    )
    policy_tab, manager_tab = st.tabs(["Policy Diagnostic Considerations", "Managerial Diagnostic Considerations"])

    with policy_tab:
        policy = get_policy_considerations(result)
        st.markdown(f"**Most Relevant Roadmap Step:** {policy.get('step','--')}")
        st.markdown(f"**Diagnostic Objective:** {policy.get('objective','--')}")
        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown("**Questions and Evidence for Policy Diagnosis**")
            for q in policy.get("questions_and_evidence", []) or []:
                st.markdown(f"- {q}")
        with pc2:
            st.markdown("**Additional Considerations**")
            for action in policy.get("additional_considerations", []) or []:
                st.markdown(f"- {action}")
        with st.expander("Full Policy Roadmap (7 Steps, diagnostic support only)"):
            st.markdown("""
| Step | Action |
|:----:|--------|
| **1** | **Determine the prescribed future** |
| **2** | **Map future-making orientations** |
| **3** | **Diagnose key future-making challenges** |
| **4** | **Implement support initiatives** |
| **5** | **Facilitate enactment** |
| **6** | **Measure multiple outcomes** |
| **7** | **Revise the intervention** |
            """)

    with manager_tab:
        manager = get_manager_considerations(result)
        st.markdown(f"**Most Relevant Roadmap Step:** {manager.get('step','--')}")
        st.markdown(f"**Diagnostic Objective:** {manager.get('objective','--')}")
        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown("**Managerial Issues to Investigate**")
            for issue in manager.get("issues_to_investigate", []) or []:
                st.markdown(f"- {issue}")
        with mc2:
            st.markdown("**Avoid**")
            for av in manager.get("avoid", []) or []:
                st.markdown(f"- {av}")
        st.markdown("**Potential Communication Consideration**")
        st.info(manager.get("communication_consideration", "--"))
        with st.expander("Full Managerial Roadmap (6 Steps, diagnostic support only)"):
            st.markdown("""
| Step | Action |
|:----:|--------|
| **1** | **Determine the prescribed future** |
| **2** | **Consider future-making orientations** |
| **3** | **Monitor key future-making challenges** |
| **4** | **Select an orientation-sensitive response** |
| **5** | **Match messaging to key future-making challenges** |
| **6** | **Support consumers through enactment** |
            """)
        st.caption(CROSS_ORIENTATION_WARNING)

    st.markdown("---")
    st.caption(f"\"{PAPER_TITLE}\" | Read the paper: {PAPER_URL}")


# ─────────────────────────────────────────
# BREADCRUMB HELPER
# ─────────────────────────────────────────

def render_breadcrumb(*items, current=None):
    if current is None:
        current = len(items) - 1
    parts = []
    for i, label in enumerate(items):
        if i == current:
            parts.append(f"<strong style='color:#2980B9;'>{label}</strong>")
        else:
            parts.append(f"<span style='color:#999;'>{label}</span>")
    st.markdown(
        "<div style='font-size:13px;margin:2px 0 14px 0;'>"
        + " &nbsp;&rsaquo;&nbsp; ".join(parts) + "</div>",
        unsafe_allow_html=True
    )


# ─────────────────────────────────────────
# INTERVENTION TYPE SELECTOR (shared helper)
# ─────────────────────────────────────────

def render_intervention_type_selector(key_suffix: str):
    st.markdown("**Intervention type**")
    st.caption(
        "Intervention type describes the scope of intended change to "
        "consumer practices and how prescriptive the intervention is. This "
        "context helps interpret what the prescribed future requires, but "
        "it does not predetermine which orientations, activities, or "
        "challenge pathways will appear in the data."
    )
    st.caption(
        "Note: classification depends on the specific intervention you "
        "describe below, not on the general domain. For example, generic, "
        "decentralized adoption of AI in healthcare is typically an Open "
        "intervention, while a specific mandate requiring all primary-care "
        "patients to use AI-supported triage by a stated date may be a "
        "Bounded intervention."
    )
    it_key = st.selectbox(
        "Choose the intervention type:",
        options=list(INTERVENTION_TYPES.keys()),
        index=None,
        placeholder="No intervention type selected -- click to choose (optional)",
        key=f"it_{key_suffix}"
    )
    if it_key is None:
        st.warning(
            "No intervention type selected. The analysis will proceed "
            "without this contextual information."
        )
    else:
        it_data = INTERVENTION_TYPES[it_key]
        st.caption(f"**Example:** {it_data['example']}")
        st.caption(it_data["note"])
    return it_key


# ─────────────────────────────────────────
# MODE SELECTOR (with confirm-before-switch)
# ─────────────────────────────────────────

def render_mode_selector():
    st.markdown("""
    <style>
    div.st-key-mode_single_btn_active button {
        background-color: #2980B9 !important;
        border: 2px solid #2980B9 !important;
        color: white !important;
        font-weight: bold !important;
    }
    div.st-key-mode_single_btn_inactive button {
        background-color: #EBF5FB !important;
        border: 2px solid #AED6F1 !important;
        color: #888 !important;
        font-weight: normal !important;
    }
    div.st-key-mode_doc_btn_active button {
        background-color: #8E44AD !important;
        border: 2px solid #8E44AD !important;
        color: white !important;
        font-weight: bold !important;
    }
    div.st-key-mode_doc_btn_inactive button {
        background-color: #F5EEF8 !important;
        border: 2px solid #D7BDE2 !important;
        color: #888 !important;
        font-weight: normal !important;
    }
    </style>
    """, unsafe_allow_html=True)

    if "app_mode" not in st.session_state:
        st.session_state["app_mode"] = MODE_SINGLE
    if "pending_mode" not in st.session_state:
        st.session_state["pending_mode"] = None

    active_mode = st.session_state["app_mode"]

    col1, col2 = st.columns(2)
    with col1:
        is_active = (active_mode == MODE_SINGLE)
        key_name = "mode_single_btn_active" if is_active else "mode_single_btn_inactive"
        label = f"[Selected] {MODE_SINGLE_LABEL}" if is_active else MODE_SINGLE_LABEL
        if st.button(label, key=key_name, use_container_width=True) and not is_active:
            st.session_state["pending_mode"] = MODE_SINGLE
            st.rerun()
    with col2:
        is_active2 = (active_mode == MODE_DOC)
        key_name2 = "mode_doc_btn_active" if is_active2 else "mode_doc_btn_inactive"
        label2 = f"[Selected] {MODE_DOC_LABEL}" if is_active2 else MODE_DOC_LABEL
        if st.button(label2, key=key_name2, use_container_width=True) and not is_active2:
            st.session_state["pending_mode"] = MODE_DOC
            st.rerun()

    pending_mode = st.session_state["pending_mode"]
    if pending_mode and pending_mode != active_mode:
        pending_label = MODE_SINGLE_LABEL if pending_mode == MODE_SINGLE else MODE_DOC_LABEL
        st.warning(
            f"Switch to **'{pending_label}'**? Any unsaved input in the "
            f"current mode may be lost."
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Proceed", type="primary", key="confirm_switch_btn", use_container_width=True):
                st.session_state["app_mode"] = pending_mode
                st.session_state["pending_mode"] = None
                st.rerun()
        with c2:
            if st.button("Cancel", key="cancel_switch_btn", use_container_width=True):
                st.session_state["pending_mode"] = None
                st.rerun()
    else:
        active_label = MODE_SINGLE_LABEL if active_mode == MODE_SINGLE else MODE_DOC_LABEL
        active_color = "#2980B9" if active_mode == MODE_SINGLE else "#8E44AD"
        active_bg = "#EBF5FB" if active_mode == MODE_SINGLE else "#F5EEF8"
        st.markdown(f"""
        <div style="background:{active_bg};border-left:4px solid {active_color};
                    padding:8px 14px;border-radius:6px;margin:10px 0 16px 0;">
            <strong style="color:{active_color};">Current mode:</strong> {active_label}
        </div>
        """, unsafe_allow_html=True)

    return st.session_state["app_mode"]


# ─────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────

def main():
    st.title("Future-Making Analyzer")
    render_breadcrumb("Home")
    st.markdown(HOMEPAGE_DESCRIPTION)
    st.divider()

    api_key = None
    try:
        api_key = st.secrets["openai_api_key"]
    except Exception:
        with st.expander("API Settings -- click to configure", expanded=True):
            api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")

    st.markdown("---")
    st.markdown("### What would you like to do?")
    mode = render_mode_selector()

    # ═══════════════════════════════════════
    # MODE 1: SINGLE COMMENT
    # ═══════════════════════════════════════
    if mode == MODE_SINGLE:
        render_breadcrumb("Home", MODE_SINGLE_LABEL, "Step 1: Prescribed Future")
        st.markdown("### Step 1 -- Define the Prescribed Future")

        it_key_single = render_intervention_type_selector("single")

        pf_default = st.session_state.pop("pf_prefill", "")
        prescribed_future = st.text_area(
            "prescribed_future", value=pf_default, height=85,
            placeholder="e.g., 'Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's net-zero emissions targets by 2035'",
            label_visibility="collapsed"
        )

        render_breadcrumb("Home", MODE_SINGLE_LABEL, "Step 2: Comment")
        st.markdown("### Step 2 -- Enter a Consumer Comment")
        st.caption(
            "Suitable inputs include consumer, citizen, patient, "
            "consultation, forum, interview, and market-actor discourse. "
            "Institutional and policy documents can be used to define the "
            "prescribed future above; they should not be classified as "
            "consumer orientations unless the analyzed text clearly "
            "contains consumer, citizen, patient, or other relevant actor "
            "discourse."
        )
        st.info(INTERPRETIVE_USE_NOTE)

        input_method = st.radio(
            "Input method:",
            ["Type or paste text", "Upload a .txt file"],
            horizontal=True
        )

        comment = ""
        if input_method == "Type or paste text":
            selected_ex = st.selectbox(
                "Or try a built-in benchmark example:", list(EXAMPLES.keys())
            )
            ex_data = EXAMPLES.get(selected_ex, {"prescribed": "", "comment": "", "activity": "", "subtype": "", "orientation": ""})
            if selected_ex != "Select an example":
                show_example_badge(ex_data)
                suggested_pf = ex_data.get("prescribed", "")
                if suggested_pf:
                    st.info(f"Suggested prescribed future: {suggested_pf[:130]}...")
                    if st.button("Use this as my prescribed future", type="secondary"):
                        st.session_state["pf_prefill"] = suggested_pf
                        st.rerun()
            comment = st.text_area(
                "Comment:", value=ex_data.get("comment", ""), height=220,
                placeholder="Paste or type a consumer comment here...", label_visibility="collapsed"
            )
        else:
            uploaded_file = st.file_uploader("Upload .txt file:", type=["txt"])
            if uploaded_file:
                comment = uploaded_file.read().decode("utf-8")
                st.success(f"Uploaded: {len(comment):,} characters")

        if not prescribed_future.strip():
            prescribed_future = PF_EV

        final_pf_single = augment_prescribed_future(prescribed_future, it_key_single)

        st.markdown("---")
        ready = bool(api_key and comment.strip())
        if not comment.strip():
            st.warning("Please enter a comment in Step 2.")
        if not api_key:
            st.warning("Please configure your OpenAI API key above.")

        if st.button("Analyze Comment", type="primary", use_container_width=True, disabled=not ready):
            with st.spinner("Analyzing with the framework's coding criteria..."):
                try:
                    result = analyze_comment(final_pf_single, comment.strip(), api_key)
                    st.divider()
                    render_breadcrumb("Home", MODE_SINGLE_LABEL, "Step 3: Results")
                    st.markdown("## Analysis Results")
                    show_results(result, final_pf_single)
                except openai.AuthenticationError:
                    st.error("Invalid API key.")
                except openai.RateLimitError:
                    st.error("Rate limit reached. Please wait a moment.")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

    # ═══════════════════════════════════════
    # MODE 2: DOCUMENT / CORPUS ANALYSIS
    # ═══════════════════════════════════════
    else:
        render_breadcrumb("Home", MODE_DOC_LABEL)
        st.caption(
            "Upload or paste a larger text (e.g., forum export, survey "
            "open-ends, public consultation submissions, or a social media "
            "export) to get an aggregate view of future-making orientations, "
            "activities, and potential challenge signals across selected "
            "segments, plus a full rationale explorer for individual "
            "segments."
        )
        st.info(
            "Institutional and policy documents can be used to define the "
            "prescribed future (Step 1 below) and to examine institutional "
            "framing, but should not be classified as consumer orientations "
            "unless the analyzed text clearly contains consumer, citizen, "
            "patient, or other relevant actor discourse. This version does "
            "not build a separate institutional-framing model."
        )

        render_breadcrumb("Home", MODE_DOC_LABEL, "Step 1: Prescribed Future")
        st.markdown("### Step 1 -- Define the Prescribed Future")

        it_key_doc = render_intervention_type_selector("doc")

        pf_doc_default = st.session_state.get("pf_doc_prefill", PF_EV)
        prescribed_future_doc = st.text_area(
            "prescribed_future_doc", value=pf_doc_default, height=85,
            label_visibility="collapsed"
        )
        preset_cols = st.columns(3)
        with preset_cols[0]:
            if st.button("Use ZEV/EV preset", type="secondary"):
                st.session_state["pf_doc_prefill"] = PF_EV
                st.rerun()
        with preset_cols[1]:
            if st.button("Use NVES preset", type="secondary"):
                st.session_state["pf_doc_prefill"] = PF_NVES
                st.rerun()
        with preset_cols[2]:
            if st.button("Use AI-Healthcare preset", type="secondary"):
                st.session_state["pf_doc_prefill"] = PF_AI_HEALTH
                st.rerun()

        render_breadcrumb("Home", MODE_DOC_LABEL, "Step 2: Upload Document")
        st.markdown("### Step 2 -- Provide the Document")
        doc_input_method = st.radio(
            "Input method:",
            ["Upload file (.txt, .md, .pdf)", "Paste text"],
            horizontal=True
        )

        raw_text = ""
        if doc_input_method == "Upload file (.txt, .md, .pdf)":
            uploaded_doc = st.file_uploader("Upload document:", type=["txt", "md", "pdf"])
            if uploaded_doc:
                if uploaded_doc.name.lower().endswith(".pdf"):
                    with st.spinner("Extracting text from PDF..."):
                        raw_text = extract_text_from_pdf(uploaded_doc)
                else:
                    raw_text = uploaded_doc.read().decode("utf-8", errors="ignore")
                if raw_text:
                    st.success(f"Extracted {len(raw_text):,} characters from '{uploaded_doc.name}'")
        else:
            raw_text = st.text_area(
                "Paste large text here (works even if PDF extraction is unavailable):",
                height=250
            )

        if raw_text.strip():
            render_breadcrumb("Home", MODE_DOC_LABEL, "Step 3: Segmentation")
            st.markdown("### Step 3 -- Configure Segmentation")

            id_hits = len(re.findall(r'\b\d{6,7}\s+(?:Name\s+withheld|[A-Z][a-z]+)', raw_text))
            looks_like_consultation = id_hits >= 5

            granularity_options = ["Paragraphs (recommended for prose/reports)",
                                    "Sentence groups (finer-grained)"]
            if looks_like_consultation:
                granularity_options.insert(
                    0,
                    f"Public consultation responses (auto-detected {id_hits} respondent IDs)"
                )

            gcol1, gcol2 = st.columns(2)
            with gcol1:
                granularity = st.selectbox("Segment by:", granularity_options)
            sentences_per_chunk = 3
            with gcol2:
                if granularity.startswith("Sentence"):
                    sentences_per_chunk = st.slider("Sentences per segment", 2, 6, 3)

            if granularity.startswith("Public consultation"):
                chunks = extract_public_consultation_responses(raw_text)
            elif granularity.startswith("Sentence"):
                chunks = split_into_chunks(raw_text, granularity="sentence_group", sentences_per_chunk=sentences_per_chunk)
            else:
                chunks = split_into_chunks(raw_text, granularity="paragraph")

            if chunks:
                st.info(f"Document split into {len(chunks)} analyzable segments.")
                with st.expander(f"Preview first segments (of {len(chunks)} total)"):
                    for i, c in enumerate(chunks[:10]):
                        st.caption(f"[{i}] {c[:200]}{'...' if len(c) > 200 else ''}")
            else:
                st.warning(
                    "No analyzable segments found with the current segmentation "
                    "option. Try a different segmentation method, or paste more "
                    "text below."
                )

            render_breadcrumb("Home", MODE_DOC_LABEL, "Step 4: Run Analysis")
            st.markdown("### Step 4 -- Run Analysis")

            total_analyzable = len(chunks)
            max_possible = max(1, min(total_analyzable, 300)) if chunks else 1
            default_val = min(30, max_possible) if chunks else 1
            max_chunks = st.slider(
                "Number of segments to analyze (evenly sampled across the full "
                "set if fewer than all are selected)",
                min_value=1, max_value=max_possible, value=default_val,
                disabled=(total_analyzable == 0)
            )
            est_seconds = round(max_chunks / DOC_MAX_WORKERS * 2.5)
            est_cost = round(max_chunks * 0.00075, 3)
            st.caption(
                f"Estimated time: ~{est_seconds}s | API calls: {max_chunks} "
                f"(parallelized, {DOC_MAX_WORKERS} at a time) | "
                f"Estimated cost: ~${est_cost}"
            )

            if total_analyzable > 0:
                if max_chunks >= total_analyzable:
                    sampling_preview = "Full set of analyzable segments."
                else:
                    sampling_preview = (
                        f"Evenly distributed sample of {max_chunks} from "
                        f"{total_analyzable} analyzable segments."
                    )
                st.caption(f"**Sampling method:** {sampling_preview}")

            run_doc_analysis = st.button(
                "Analyze Document", type="primary", use_container_width=True,
                disabled=(not api_key or total_analyzable == 0)
            )
            if not api_key:
                st.warning("Please configure your OpenAI API key above.")
            if total_analyzable == 0:
                st.caption("The Analyze Document button is disabled until at least one valid segment is found.")

            if run_doc_analysis and chunks:
                final_pf_doc = augment_prescribed_future(prescribed_future_doc, it_key_doc)

                if max_chunks >= total_analyzable:
                    sample_indices = list(range(total_analyzable))
                    sampling_description = "Full set of analyzable segments."
                else:
                    sample_indices = compute_evenly_spaced_sample_indices(total_analyzable, max_chunks)
                    sampling_description = (
                        f"Evenly distributed sample of {len(sample_indices)} from "
                        f"{total_analyzable} analyzable segments."
                    )

                indexed_chunks = [(idx, chunks[idx]) for idx in sample_indices]

                progress_bar = st.progress(0, text="Starting analysis...")
                doc_results = analyze_document(
                    indexed_chunks, final_pf_doc, api_key, progress_bar
                )
                progress_bar.empty()
                st.session_state["doc_results"] = doc_results
                st.session_state["doc_prescribed_future"] = final_pf_doc
                st.session_state["doc_intervention_type"] = it_key_doc
                st.session_state["doc_total_analyzable"] = total_analyzable
                st.session_state["doc_sampling_description"] = sampling_description

        if "doc_results" in st.session_state:
            st.divider()
            render_breadcrumb("Home", MODE_DOC_LABEL, "Step 5: Results")
            st.markdown("## Document-Level Analysis")
            show_document_summary(
                st.session_state["doc_results"],
                st.session_state.get("doc_prescribed_future", PF_EV),
                st.session_state.get("doc_intervention_type"),
                total_analyzable=st.session_state.get("doc_total_analyzable"),
                sampling_description=st.session_state.get("doc_sampling_description", "")
            )
            if st.button("Clear document results"):
                del st.session_state["doc_results"]
                st.rerun()

    # ─────────────────────────────────────────
    # ADVANCED / DEVELOPER TOOLS
    # ─────────────────────────────────────────
    st.markdown("---")
    with st.expander("Advanced / Developer Tools"):
        st.caption(
            "Internal quality-control tool. Not needed for regular use."
        )
        st.markdown("#### Coding Consistency Check")
        st.caption(
            "Agreement with built-in benchmark examples tests whether the "
            "current prompt reproduces predetermined coding decisions. It "
            "does NOT constitute empirical validation, intercoder "
            "reliability, or evidence of generalizability."
        )
        if st.button("Run Coding Consistency Check"):
            if not api_key:
                st.warning("Configure your API key above first.")
            else:
                with st.spinner("Running consistency check across benchmark examples..."):
                    report = run_consistency_suite(api_key)
                if report["results"]:
                    st.metric("Agreement with Benchmark Examples", f"{report['overall_agreement']*100:.1f}%")
                    for r in report["results"]:
                        status = "PASS" if r["match"] else "FAIL"
                        with st.expander(f"[{status}] {r['example']}"):
                            st.write("**Expected (primary):**", r["expected"])
                            st.write("**Predicted (primary):**", r["predicted"])
                            if r.get("secondary_expected"):
                                sec_status = "PASS" if r.get("secondary_match") else "FAIL"
                                st.write(f"**Secondary check [{sec_status}]:** expected "
                                         f"{r['secondary_expected']} among predicted secondary "
                                         f"classifications.")
                            if r.get("error"):
                                st.error(r["error"])
                else:
                    st.info("No labeled benchmark examples found.")


if __name__ == "__main__":
    main()
