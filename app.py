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

DOC_MAX_WORKERS = 5
DEFAULT_THREAD = "_default_thread_"

# ─────────────────────────────────────────
# INTERPRETIVE-USE NOTES
# ─────────────────────────────────────────
INTERPRETIVE_USE_NOTE = (
    "**Interpretive-use note.** For comparability, the application assigns a "
    "dominant orientation and activity to each analyzed comment. This is an "
    "analytical simplification: future-making activities are interdependent "
    "and recursive, and consumers may adopt, combine, or move between "
    "orientations across contexts and over time. Review outputs alongside "
    "the complete text, the surrounding interaction, the specified "
    "intervention, and relevant behavioral evidence. Corpus percentages "
    "refer only to analyzed comments and should not be interpreted as "
    "population estimates. Future-making challenges and Fragile Futures "
    "require evidence that differently oriented performances coexist, "
    "clash, or interfere with one another."
)

NEGOTIATION_CONTEXT_NOTE = (
    "**Negotiation is an interactional activity.** Its identification is "
    "more reliable when parent comments, surrounding replies, the original "
    "post, or the consultation prompt are available. When conversational "
    "context is unavailable, the application can identify implicit "
    "relational positioning but cannot reconstruct the complete "
    "interaction."
)

HOMEPAGE_DESCRIPTION = """
Use this application to support the diagnosis of consumer future-making in
response to a policy or market intervention. Upload or paste a collection of
consumer comments, consultation responses, forum posts, or social-media
conversations. The application analyzes each **focal comment** while using
available thread context to identify how consumers evaluate, negotiate, and
enact preferred futures.

The framework was developed through qualitative research on Australian Zero
Emission Vehicle interventions. Its application to AI-integrated healthcare
illustrates its expected transferability to another future-oriented context;
it does not constitute independent empirical validation. Orientations are
situated ways of performing future-making, not fixed consumer types or
stable market segments. Results support interpretive diagnosis and should
be reviewed in context: corpus summaries describe only the analyzed
comments and do not, by themselves, demonstrate population prevalence,
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
MODE_DOC_LABEL = "Map Orientations Across Selected Comments"

# ─────────────────────────────────────────
# ENUM VALIDATION SETS
# ─────────────────────────────────────────
VALID_INTERACTION_TYPES = {
    "AGREEMENT", "REINFORCEMENT", "QUESTION", "COMPARISON", "CORRECTION",
    "REBUTTAL", "REJECTION", "CONTESTATION", "PERSUASION", "NONE"
}
VALID_CONTEXT_TYPES = {
    "PARENT_REPLY", "THREAD_WINDOW", "ORIGINAL_POST", "CONSULTATION_PROMPT", "NONE"
}
VALID_NEGOTIATION_EVIDENCE = {
    "OBSERVED_INTERACTION", "IMPLICIT_RELATIONAL_POSITIONING", "NO_NEGOTIATION_EVIDENCE"
}

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
    act = _clean_enum(main_activity).upper() if main_activity else ""
    return ACTIVITY_TO_CHALLENGE_PATHWAY.get(act, "N/A")


def derive_challenge_pathways(main_activity: str, secondary_classifications: list) -> list:
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
# SCOPE AND DEGREE OF PRESCRIPTION OF INTERVENTIONS
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
    base_pf = (base_pf or "").strip()
    if not it_key or it_key not in INTERVENTION_TYPES:
        return base_pf
    it_data = INTERVENTION_TYPES[it_key]
    type_name = it_key.split(" (")[0]
    addition = (
        f"[Intervention type (context only, not predictive): {type_name} -- "
        f"{it_data['scope']} scope, {it_data['prescriptiveness']} prescriptive.]"
    )
    if addition in base_pf:
        return base_pf
    return f"{base_pf} {addition}".strip()


# ─────────────────────────────────────────
# SYSTEM PROMPT v14 -- strengthened relational Negotiation signals
# (fixes: decisive-action dominance for Enactment; named-address
# sufficiency; future-vision test for declarative Negotiation/Contest)
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an analytical assistant supporting the diagnosis of consumer
future-making in response to policy or market interventions, grounded in a
practice-theoretical framework developed through qualitative research on
Australian Zero Emission Vehicle (ZEV) interventions.

This framework was developed through qualitative research in the ZEV
context. Its application below to AI-integrated healthcare illustrates the
framework's expected transferability to another future-oriented context; it
does not constitute independent empirical validation in that domain.

You will always be given TWO separate fields:
  1. A FOCAL COMMENT (or FOCAL RESPONSE) -- this is the ONLY text you
     classify.
  2. CONVERSATIONAL CONTEXT (or CONSULTATION/POLICY CONTEXT) -- parent
     comment, nearby thread comments, the original post, and/or the
     consultation prompt. Use this ONLY to interpret the focal comment's
     relational positioning. NEVER classify the context itself, and NEVER
     aggregate the context and the focal comment into one combined
     classification.

====================================================================
A. SCOPE AND DEGREE OF PRESCRIPTION OF INTERVENTIONS (context)
====================================================================

  FIXED (Narrow, Highly prescriptive)   -- e.g., ban on single-use plastic bags
  BOUNDED (Broad, Highly prescriptive)  -- e.g., ZEV policies and strategies
  FLEXIBLE (Narrow, Lowly prescriptive) -- e.g., Meat-free Mondays
  OPEN (Broad, Lowly prescriptive)      -- e.g., decentralized adoption of AI in healthcare

This typology CONTEXTUALIZES the prescribed future; it does NOT
predetermine which orientations, activities, or challenge pathways will be
found. Classification depends on how the specific intervention is
specified, not on its general domain.

====================================================================
B. FUTURE-MAKING ACTIVITIES
====================================================================

--- EVALUATION ---
Choose EVALUATION when the focal comment primarily makes a STANDALONE
assessment of the prescribed future -- its meaning, desirability,
feasibility, credibility, consequences, risks, assumptions, or trade-offs
-- and its meaning DOES NOT DEPEND on positioning against another claim,
actor, or pathway raised in the context, AND it does not itself assert a
competing collective trajectory (see FUTURE-VISION TEST below).
Example: "EV batteries remain too expensive and the charging network is
inadequate." -- a standalone assessment, EVALUATION.
Sub-types by orientation:
  SIMPLIFY   (Catalyzer)  -- narrows focus, treats difficulties as
    temporary or already solved
  STALL      (Ambivalent) -- careful consideration, information gathering,
    unresolved technical/ethical/institutional conditions
  AVOID      (Resistant)  -- a narrow, categorical, dismissive standalone
    judgment WITHOUT elaborated systemic reasoning
  COMPLEXIFY (Expander)   -- zooms out to systemic trade-offs, WITH
    elaborated reasoning connecting the topic to wider systems

  DISAMBIGUATION -- AVOID vs. COMPLEXIFY: a brief categorical dismissal
  with no elaborated systemic reasoning is typically AVOID; a dismissal
  that elaborates a systemic argument (city design, land use, production
  patterns, structural inequality) is typically COMPLEXIFY, even with
  similarly strong language.

--- NEGOTIATION (RELATIONAL -- READ CAREFULLY) ---
Definition: Negotiation refers to how consumers POSITION preferred futures
IN RELATION TO other actors, claims, pathways, or versions of the future,
in an attempt to shape collective trajectories. It includes comparing,
questioning, defending, rejecting, contesting, correcting, endorsing, or
expanding preferred futures.

CRITICAL RULES:
  - Negotiation does NOT require an imperative, a direct address, or an
    explicit call to action. A comment can be Negotiation while being
    entirely grammatically declarative.
  - Do NOT automatically classify a comment as Evaluation merely because
    it lacks "we need to," "should," "let's," a named addressee, or a
    direct command.
  - Use the CONVERSATIONAL CONTEXT to determine whether the focal comment:
    responds to another position; agrees with, reinforces, corrects, or
    rejects another claim; asks another actor to provide evidence;
    compares preferred futures; attributes responsibility or authority;
    defends a proposed pathway; contests the legitimacy or scope of the
    prescribed future; or attempts to influence which future should be
    pursued. ANY of these relational moves is sufficient for Negotiation,
    even without context, if the focal comment's own content clearly
    stakes out a position relative to an implied alternative.
  - When context is unavailable, look for IMPLICIT relational positioning
    within the focal comment itself (e.g., a confident declarative
    alternative future, a correction of an unstated assumption, a proposed
    compromise pathway). This is still Negotiation, but record
    negotiation_evidence as IMPLICIT_RELATIONAL_POSITIONING rather than
    OBSERVED_INTERACTION.
  - CRITICAL -- NAMED-ADDRESS SUFFICIENCY: A direct address to a specific
    named individual (e.g., "John you are so right," or an explicit
    rebuttal of a claim just attributed to a named person) is, BY ITSELF,
    a STRONG and USUALLY SUFFICIENT signal of Negotiation -- because it
    explicitly relates the comment's content to another identified
    person's claim. Do NOT let this signal be outweighed merely because
    much of the SURROUNDING text in the same passage also reads like
    systemic or standalone assessment. A long passage that is mostly
    critique-sounding content STILL counts as Negotiation overall if a
    named address anchors it relationally, unless the named address is
    clearly incidental (e.g., a passing greeting unconnected to the
    future-making content).
  - CRITICAL -- FUTURE-VISION TEST: A declarative statement that asserts
    what "the future" will or should look like, whose vision diverges from
    the prescribed future (e.g., "The future is less cars, in higher
    density pedestrian, bike and train-orientated urban environments"), is
    a relational move: it stakes out and advances an ALTERNATIVE
    collective trajectory rather than merely assessing the prescribed
    future's own merits, costs, or credibility. Code such statements as
    NEGOTIATION (the orientation-appropriate subtype -- typically CONTEST
    for Expander, ADVOCATE for Catalyzer, QUESTION for Ambivalent), NOT
    EVALUATION, even without any imperative, addressee, or explicit
    contrast marker. Reserve EVALUATION for statements that assess the
    prescribed future's own merits/trade-offs/credibility WITHOUT
    asserting a competing trajectory. Apply this test to every
    "the future is/will be..." or "we need X, not Y" style statement
    BEFORE defaulting to Evaluation. If such a statement co-occurs with
    other, more clearly evaluative or enactment content in the same
    passage, capture it explicitly as a NEGOTIATION classification
    (primary or secondary, per Section H) rather than folding it into an
    Evaluation reading of the whole passage.

Examples of Negotiation signals (NONE require an imperative):
  "That assumes everyone can charge at home."
  "The previous comment ignores the cost of battery replacement."
  "Hybrids would be a more realistic pathway until the infrastructure improves."
  "The future is fewer cars, not simply electric cars."
  "Governments should first electrify their own fleets."
  "No, consumers should retain the right to choose."
  "I agree that EVs are necessary, but the transition needs to be slower."
These statements position one future against another even with no
imperative.

Sub-types by orientation:
  ADVOCATE  (Catalyzer)  -- recruits others, calls for stronger
    policy/rollout, positions itself as accelerating relative to a slower
    or resistant alternative
  QUESTION  (Ambivalent) -- polite skepticism, asks for proof from others,
    or proposes a STAGED/INTERIM compromise pathway WITHIN THE SAME
    PARADIGM relative to a more urgent or more resistant position
  REJECT    (Resistant)  -- refuses a demand or frames the intervention
    (or the authority behind it) as illegitimate; no alternative future
    proposed. Applies even in third person -- direct address not required.
  CONTEST   (Expander)   -- contests the current paradigm itself and
    proposes a SYSTEMIC alternative outside it, whether phrased as an
    imperative or as a confident declarative claim

  DISAMBIGUATION -- REJECT vs. CONTEST: REJECT refuses without proposing
  an alternative; CONTEST proposes a different, broader future.

Sub-types by orientation (Enactment):
  ACCELERATE (Catalyzer)  -- adopts the prescribed future early
  DELAY      (Ambivalent) -- ties non-adoption to resolvable conditions
  PREVENT    (Resistant)  -- durable, identity-based non-adoption
  REROUTE    (Expander)   -- adopts an entirely different practice/pathway

--- ENACTMENT ---
Primarily gives material or practical form to a preferred future through
actual, planned, imagined, delayed, refused, or reconfigured practices,
typically attributed to the speaker's own practice. A DECISIVE, first-
person practical commitment stated as the passage's MAIN POINT (e.g.,
"just bought," "I'm planning to run this one for as long as it lasts,"
"I'll stick with...") is a STRONG signal for ENACTMENT as the PRIMARY
classification, even when accompanied by additional evaluative commentary
elsewhere in the passage -- UNLESS the action is clearly a minor,
incidental aside buried within predominantly evaluative content (in which
case Evaluation may remain primary with Enactment captured as secondary).
When in doubt, ask: does the passage exist mainly to justify/explain a
decisive action already taken or firmly planned (-> ENACTMENT primary),
or does it exist mainly to weigh an open question, with an action
mentioned only in passing (-> EVALUATION primary, ENACTMENT secondary)?

====================================================================
C. FUTURE-MAKING ORIENTATIONS
====================================================================

--- CATALYZER --- Urgency narrative. "Urgent, desirable, and already
underway." Goal: accelerate change. Emotions: utopian optimism,
enthusiasm, confidence, pride. Temporality: present-focused.
VALID SUBTYPES: SIMPLIFY (Evaluation), ADVOCATE (Negotiation), ACCELERATE
(Enactment).

--- AMBIVALENT --- Pragmatic narrative. "Valuable, but conditions are not
yet ready." Goal: slow/stage change. Emotions: curiosity, caution,
anxiety, frustration, conditional optimism. Temporality: gradual/contingent.
VALID SUBTYPES: STALL (Evaluation), QUESTION (Negotiation), DELAY (Enactment).

DISAMBIGUATION -- AMBIVALENT vs. EXPANDER: an alternative that stays
WITHIN the current paradigm as a temporary bridge ("hybrid until 2030") is
typically AMBIVALENT; one that REJECTS the paradigm durably (no car at
all, degrowth) is typically EXPANDER.

--- RESISTANT --- Control narrative. "Threatens autonomy, identity, or
rights." Goal: contest and protect status quo. Emotions: pessimism, anger,
anxiety, fear, defiance, distrust. Temporality: maintenance-oriented.
VALID SUBTYPES: AVOID (Evaluation), REJECT (Negotiation), PREVENT
(Enactment). AVOID should not be assigned to any other orientation.

--- EXPANDER --- Bigger-picture narrative. "The problem is framed too
narrowly." Goal: expand/reroute; propose alternative pathways. Emotions:
dystopian optimism, concern, hope, critical urgency. Temporality:
envisioned/system-oriented.
VALID SUBTYPES: COMPLEXIFY (Evaluation), CONTEST (Negotiation), REROUTE
(Enactment).

Do NOT infer orientation from sentiment or tone alone. Ground it in the
full configuration of narrative, goal, emotion, temporality, relationship
to the prescribed future, and practice implications.

====================================================================
D. FUTURE-MAKING CHALLENGES AS POTENTIAL PATHWAYS
====================================================================

  EVALUATION  -> may contribute to CONVOLUTED_EVALUATIONS
  NEGOTIATION -> may contribute to CONFRONTATIONAL_NEGOTIATIONS
  ENACTMENT   -> may contribute to COMPETING_ENACTMENTS

A single focal comment provides evidence of ONE performance -- not proof
that a challenge, or Fragile Futures, has occurred. This mapping is
applied deterministically by the calling application.

====================================================================
E-F. ROADMAPS (diagnostic support only -- see Section J)
====================================================================

Policy roadmap (7 steps): 1) Determine the prescribed future. 2) Map
orientations. 3) Diagnose challenges. 4) Implement matched support. 5)
Facilitate enactment. 6) Measure outcomes. 7) Revise the intervention.

Managerial roadmap (6 steps): 1) Determine the prescribed future. 2)
Consider orientations as a diagnostic lens. 3) Monitor challenges. 4)
Select an orientation-sensitive response. 5) Match messaging. 6) Support
enactment.

====================================================================
G. GROUNDING EXAMPLES
====================================================================

Example 1 (EVALUATION, standalone, no relational positioning):
FOCAL: "EV batteries remain too expensive and the charging network is
inadequate."
CONTEXT: none.
-> EVALUATION / STALL / AMBIVALENT. negotiation_evidence: NO_NEGOTIATION_EVIDENCE.

Example 2 (the SAME evaluative content becomes NEGOTIATION when used
relationally against a parent comment):
CONTEXT (parent): "EV adoption should be accelerated immediately."
FOCAL: "That ignores households without home charging. Hybrids would be a
more realistic transition until the infrastructure improves."
The focal comment uses evaluative content (infrastructure readiness) IN
SERVICE OF a relational move: correcting/rebutting the parent's urgency
claim and proposing a staged compromise.
-> Primary: NEGOTIATION / QUESTION / AMBIVALENT.
-> Secondary: EVALUATION / STALL / AMBIVALENT (the infrastructure claim is
   also a separable evaluative statement).
interaction_detected: true. interaction_type: CORRECTION (or REBUTTAL).
interaction_target: "the parent comment's claim that acceleration should
be immediate." negotiation_evidence: OBSERVED_INTERACTION (context was
available and the relation is explicit).

Example 3 (declarative Negotiation/Contest with NO imperative and NO
context -- implicit relational positioning; see FUTURE-VISION TEST):
FOCAL: "The future is fewer cars, not simply electric cars."
CONTEXT: none.
This is declarative, but it stakes out an alternative trajectory relative
to the (implied) EV-centric prescribed future -- it is NEGOTIATION, not
EVALUATION, because its primary work is to advance a different collective
trajectory, not merely to assess one.
-> NEGOTIATION / CONTEST / EXPANDER. negotiation_evidence:
IMPLICIT_RELATIONAL_POSITIONING (no context was available, but the
content itself stakes a relational position).

Example 4 (polite request for evidence, ambivalent Negotiation, third
person addressee, no formal context provided):
FOCAL: "Have you thought about what they are gonna do with all the
batteries once they expire because they aren't recyclable?"
-> NEGOTIATION / QUESTION / AMBIVALENT. negotiation_evidence:
IMPLICIT_RELATIONAL_POSITIONING (no structured context, but a real
addressee is implied within the comment itself).

Example 5 (direct rejection of authority, no context needed -- adversarial
third-person framing is sufficient):
FOCAL: "We don't need politicians and their cronies telling us what sort
of car we can have."
-> NEGOTIATION / REJECT / RESISTANT. negotiation_evidence:
IMPLICIT_RELATIONAL_POSITIONING.

Example 6 (ENACTMENT with separable EVALUATION secondary -- decisive
action is the passage's main point):
FOCAL: "Just bought a new petrol car last month because the EV charging
infrastructure still isn't in place near me, and I'm planning to run this
one for as long as it lasts before I even reconsider switching. I'm not
anti-EV -- I like the idea in principle -- but the upfront cost is still a
huge hurdle for me, and I don't expect that to change in the next few
years."
The passage's MAIN POINT is the decisive action already taken and firmly
planned ("just bought," "planning to run this one for as long as it
lasts"); the cost commentary is real but clearly secondary, explaining WHY
the action was taken rather than being the passage's central concern.
-> Primary: ENACTMENT / DELAY / AMBIVALENT (non-adoption tied to a
   resolvable condition -- cost -- with an implied "for now").
-> Secondary: EVALUATION / STALL / AMBIVALENT.

Example 7 (EVALUATION/AVOID vs. EVALUATION/COMPLEXIFY contrast):
"Electric vehicles are not the solution... just a muddle point." ->
EVALUATION / AVOID / RESISTANT (narrow, unelaborated dismissal).
"...60% of the land in car-dependent cities are dedicated to cars...
Electric vehicle is a false solution if you care about the environment at
all." -> EVALUATION / COMPLEXIFY / EXPANDER (elaborated systemic reasoning).

Example 8 (public consultation response, relational to the policy prompt
even without replying to another consumer):
CONSULTATION/POLICY CONTEXT: "This consultation asks respondents whether
the proposed New Vehicle Efficiency Standard should include additional
support for regional infrastructure."
FOCAL RESPONSE: "The proposed standard should include incentives for
regional charging infrastructure, otherwise regional communities will be
unfairly disadvantaged compared to metro areas."
This response positions itself relative to the policy proposal (defends a
modification/compromise pathway) -- NEGOTIATION, not merely EVALUATION.
-> NEGOTIATION / QUESTION / AMBIVALENT. negotiation_evidence:
OBSERVED_INTERACTION (the consultation prompt was available and the
response explicitly engages it). context_type: CONSULTATION_PROMPT.

Example 9 -- CRITICAL, HIGH-CONFUSION PATTERN -- named address BURIED
inside a long passage that otherwise reads like systemic critique/
Evaluation. Apply NAMED-ADDRESS SUFFICIENCY even when most of the
surrounding text sounds evaluative:
FOCAL: "Consumerism trumps facts. John you are so right but the first
sentence prevails in modern society, why save the environment by keeping
the car you already own and using it less, when you can join the Joneses,
Smiths or whoever your neighbour is and spend money on that flash new
hybrid/EV/hydrogen powered four wheeled status symbol that shows you earn
more money than you need. Does it have to be a car? If your main priority
was the environment, ride a bicycle. You're buying a 2-tonne metal box
powered by a giant battery, let's not pretend we're saving the planet,
we're just picking a lesser evil but it's still not good for the planet."
CONTEXT: none provided.
Reasoning: most of this passage (the final sentences about the "2-tonne
metal box" and "picking a lesser evil") reads like a standalone systemic
assessment, which could tempt a reading of EVALUATION/COMPLEXIFY. However,
"John you are so right" is a NAMED DIRECT ADDRESS responding to a specific
claim John apparently just made -- per NAMED-ADDRESS SUFFICIENCY, this
alone establishes relational positioning for the passage as a whole. The
imperatives that follow ("ride a bicycle," "does it have to be a car?")
further confirm NEGOTIATION, proposing a systemic alternative (non-car
mobility) -- hence CONTEST, not a standalone evaluative judgment. Do NOT
let the volume of critique-sounding content at the end of the passage
override the named-address signal near the beginning.
-> Primary: NEGOTIATION / CONTEST / EXPANDER. negotiation_evidence:
IMPLICIT_RELATIONAL_POSITIONING (no structured context was provided, but
the named address and imperatives establish relational positioning within
the focal comment itself).

Example 10 -- FUTURE-VISION TEST applied within an action-heavy passage
(secondary Negotiation/Contest alongside primary Enactment/Reroute):
FOCAL: "We tend to do most of our shopping by bike rather than with the
ute because the ute's inconvenient to park and navigate in small car
parks. I am at the moment on a waiting list for a new electric cargo
bike. The future is less cars, in higher density pedestrian, bike and
train-orientated urban environments, where cars are secondary transport
really only for those who really need it."
The first two sentences describe decisive, ongoing practice changes
(ENACTMENT/REROUTE, primary). The third sentence ("The future is less
cars...") is a distinct, separable FUTURE-VISION statement that stakes out
a competing collective trajectory -- per the Future-Vision Test, this
should be captured explicitly as a SECONDARY Negotiation/Contest
classification, not folded silently into the Enactment reading or
mistaken for Evaluation.
-> Primary: ENACTMENT / REROUTE / EXPANDER.
-> Secondary: NEGOTIATION / CONTEST / EXPANDER.

====================================================================
H. DECISION PROCEDURE -- Apply for EVERY focal comment
====================================================================

STEP 1 -- Read the FOCAL COMMENT and the CONVERSATIONAL CONTEXT (if any)
in full. Never classify the context itself.

STEP 2 -- Determine whether the focal comment's primary work is (a) a
standalone assessment (EVALUATION), (b) positioning relative to another
claim/actor/pathway -- explicit (via context) or implicit (via its own
content) -- (NEGOTIATION), or (c) giving material/practical form to a
preferred future through the speaker's own practice (ENACTMENT).

STEP 3 -- BEFORE weighing overall passage tone or length, FIRST check for
two strong, often-decisive relational signals, regardless of how much
surrounding text reads as systemic assessment:
  (i) a NAMED direct address to a specific individual (Section B,
      Named-Address Sufficiency) -- if present anywhere in the passage
      and not clearly incidental, this alone typically establishes
      Negotiation;
  (ii) a declarative "the future is/will be/should be..." (or "we need X,
      not Y") statement that advances a trajectory different from the
      prescribed future (Section B, Future-Vision Test) -- this alone
      typically establishes Negotiation for that statement, whether as
      primary or secondary.
If context is available, ALSO check explicitly whether the focal comment:
responds to another position; agrees/reinforces/corrects/rejects a claim;
asks for evidence; compares futures; attributes responsibility/authority;
defends a pathway; contests legitimacy/scope; or attempts to influence
which future should be pursued. Any of these -> NEGOTIATION, regardless
of grammatical mood.

STEP 4 -- If NO context is available and neither signal in Step 3 is
present, still check the focal comment's OWN content for other implicit
relational positioning (a proposed compromise, an implied correction). If
present -> NEGOTIATION with negotiation_evidence =
IMPLICIT_RELATIONAL_POSITIONING. If genuinely absent, and the comment is a
self-contained assessment with no relational content -> EVALUATION.

STEP 5 -- If BOTH substantial evaluative/negotiating content AND
substantial enactment content are present, ask: does the passage exist
mainly to justify/explain a decisive action already taken or firmly
planned (-> ENACTMENT primary, per Section B's Enactment guidance), or
does it exist mainly to weigh an open question with an action mentioned
only in passing (-> EVALUATION primary, ENACTMENT secondary)? Capture
whichever is not primary as a secondary classification -- do not discard
it.

STEP 6 -- Determine ORIENTATION for the primary and any secondary
classification using Section C's full configuration, not sentiment alone.
Apply disambiguations (AVOID vs. COMPLEXIFY; DELAY vs. PREVENT; REJECT vs.
CONTEST; AMBIVALENT vs. EXPANDER).

STEP 7 -- Populate interaction fields:
  - interaction_detected: true only if the CONTEXT was used to identify a
    real relational move.
  - interaction_type: one of AGREEMENT, REINFORCEMENT, QUESTION,
    COMPARISON, CORRECTION, REBUTTAL, REJECTION, CONTESTATION, PERSUASION,
    NONE.
  - interaction_target: brief description of the claim/actor/future being
    addressed.
  - interaction_rationale: how the focal comment relates to the context.
  - negotiation_evidence: OBSERVED_INTERACTION only if context was
    actually available AND used; IMPLICIT_RELATIONAL_POSITIONING if the
    focal comment positions itself relationally without confirmed context
    (including via Named-Address Sufficiency or the Future-Vision Test);
    NO_NEGOTIATION_EVIDENCE if the comment is Evaluation/Enactment with no
    relational positioning at all.

STEP 8 -- If the input text appears to mix content from multiple
distinguishable speakers in a way that cannot be cleanly separated,
populate "input_scope_warning" instead of forcing an artificial single
reading.

====================================================================
I. THEORETICALLY CONTRASTING ORIENTATION
====================================================================

Identify "theoretically_contrasting_orientation": which of the other
three orientations holds the most contrasting narrative/goal/emotion/
temporality relative to this specific comment. This is a THEORETICAL
contrast inferred from the framework -- distinct from any OBSERVED
interaction pair, which the calling application computes separately from
real parent-reply relationships. Also provide "potential_challenge_rationale"
in hedged language (what COULD contribute to friction, not what has
occurred).

====================================================================
J. DIAGNOSTIC-SUPPORT OUTPUTS (NOT definitive recommendations)
====================================================================

For policy_diagnostic_considerations / manager_diagnostic_considerations:
identify the relevant roadmap step, evidence to collect, assumptions to
investigate, and general roadmap directions that MERIT CONSIDERATION
(hedged: "could consider," "should investigate," "requires additional
evidence"). Do not issue definitive recommendations from one comment.

====================================================================
OUTPUT RULES
====================================================================

Select exactly ONE value for main_activity, activity_subtype, and
main_orientation. Provide zero to two secondary_classifications ONLY when
substantively supported -- including, per Steps 3 and 5 above, any
separable Named-Address or Future-Vision Negotiation content, or any
separable decisive Enactment/Evaluation content.

MANDATORY ORIENTATION-SUBTYPE PAIRING (applies to primary AND every
secondary classification):
  CATALYZER  -> SIMPLIFY (Evaluation) | ADVOCATE (Negotiation) | ACCELERATE (Enactment)
  AMBIVALENT -> STALL (Evaluation)    | QUESTION (Negotiation) | DELAY (Enactment)
  RESISTANT  -> AVOID (Evaluation)    | REJECT (Negotiation)   | PREVENT (Enactment)
  EXPANDER   -> COMPLEXIFY (Evaluation) | CONTEST (Negotiation) | REROUTE (Enactment)

====================================================================
OUTPUT FORMAT -- Return ONLY valid JSON
====================================================================

{
  "prescribed_future_acknowledged": "Brief restatement of the prescribed future",

  "main_activity": "EVALUATION, NEGOTIATION, or ENACTMENT",
  "activity_subtype": "SIMPLIFY, STALL, AVOID, COMPLEXIFY, ADVOCATE, QUESTION, REJECT, CONTEST, ACCELERATE, DELAY, PREVENT, REROUTE",
  "activity_rationale": "Which Decision Procedure step applied, citing specific phrases from the FOCAL comment, including whether Named-Address Sufficiency or the Future-Vision Test applied",

  "secondary_classifications": [
    {"activity": "...", "activity_subtype": "...", "orientation": "...", "rationale": "..."}
  ],
  "input_scope_warning": "",

  "main_orientation": "CATALYZER, AMBIVALENT, RESISTANT, or EXPANDER",
  "orientation_confidence": "HIGH, MEDIUM, or LOW",
  "orientation_rationale": "...",
  "narrative_identified": "...",
  "dominant_emotions": "...",
  "temporality_expressed": "...",
  "notable_conditions_of_adoption": "...",

  "interaction_detected": false,
  "interaction_type": "AGREEMENT | REINFORCEMENT | QUESTION | COMPARISON | CORRECTION | REBUTTAL | REJECTION | CONTESTATION | PERSUASION | NONE",
  "interaction_target": "",
  "interaction_rationale": "",
  "context_available": false,
  "context_type": "PARENT_REPLY | THREAD_WINDOW | ORIGINAL_POST | CONSULTATION_PROMPT | NONE",
  "negotiation_evidence": "OBSERVED_INTERACTION | IMPLICIT_RELATIONAL_POSITIONING | NO_NEGOTIATION_EVIDENCE",

  "theoretically_contrasting_orientation": "...",
  "potential_challenge_rationale": "...",

  "policy_diagnostic_considerations": {"step": "...", "objective": "...", "questions_and_evidence": [], "additional_considerations": []},
  "manager_diagnostic_considerations": {"step": "...", "objective": "...", "issues_to_investigate": [], "avoid": [], "communication_consideration": "..."}
}
"""

# ─────────────────────────────────────────
# ORIENTATION / ACTIVITY / CHALLENGE CONFIG
# ─────────────────────────────────────────
ORIENTATIONS = {
    "CATALYZER": {
        "color": "#27AE60", "bg": "#EAFAF1", "border": "#2ECC71",
        "goal": "Accelerate change toward the prescribed future",
        "narrative": "Urgency Narrative",
        "tagline": "Urgent, desirable, and already underway.",
        "temporality": "Present-focused -- The future is now",
        "activities": "Simplify - Advocate - Accelerate",
        "notable_conditions": "High degree of alignment between current practices and prescribed future"
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
        "label": "Convoluted Evaluations", "color": "#2980B9", "bg": "#EBF5FB",
        "description": "Signals that could contribute to Convoluted Evaluations if this evaluative performance clashes with differently oriented evaluations elsewhere."
    },
    "CONFRONTATIONAL_NEGOTIATIONS": {
        "label": "Confrontational Negotiations", "color": "#E67E22", "bg": "#FEF9E7",
        "description": "Signals that could contribute to Confrontational Negotiations if this negotiating performance clashes with differently oriented negotiations elsewhere."
    },
    "COMPETING_ENACTMENTS": {
        "label": "Competing Enactments", "color": "#8E44AD", "bg": "#F5EEF8",
        "description": "Signals that could contribute to Competing Enactments if this practice performance clashes with differently oriented enactments elsewhere."
    },
    "N/A": {"label": "Not Applicable", "color": "#999", "bg": "#FAFAFA", "description": "No potential challenge pathway could be derived."}
}

ACTIVITY_META = {
    "EVALUATION":  {"color": "#2980B9", "bg": "#EBF5FB",
        "definition": "A standalone assessment whose meaning does not depend on positioning against another claim.",
        "subtypes": {"SIMPLIFY": "CATALYZER", "STALL": "AMBIVALENT", "AVOID": "RESISTANT", "COMPLEXIFY": "EXPANDER"}},
    "NEGOTIATION": {"color": "#E67E22", "bg": "#FEF9E7",
        "definition": "Positions a preferred future relative to another actor, claim, or pathway (may be purely declarative).",
        "subtypes": {"ADVOCATE": "CATALYZER", "QUESTION": "AMBIVALENT", "REJECT": "RESISTANT", "CONTEST": "EXPANDER"}},
    "ENACTMENT":   {"color": "#8E44AD", "bg": "#F5EEF8",
        "definition": "Gives material or practical form to a preferred future through the speaker's own practice.",
        "subtypes": {"ACCELERATE": "CATALYZER", "DELAY": "AMBIVALENT", "PREVENT": "RESISTANT", "REROUTE": "EXPANDER"}},
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
# POLICY & MANAGERIAL DIAGNOSTIC GUIDANCE
# ─────────────────────────────────────────
POLICY_GUIDANCE = {
    "CATALYZER": {"implications": "Catalyzer performances could indicate early momentum; investigate enabling conditions before assuming broader public value.",
        "monitor": "Urgency and inevitability language; voluntary early adoption; advocacy for faster rollout.",
        "objective": "Investigate whether responsible acceleration is supported by evidence.",
        "questions_and_evidence": ["Time-limited pilots with independent evaluation", "Reporting of failures and overrides",
                                    "Subgroup/local validation before scaling", "Predefined thresholds for expansion (to investigate)"]},
    "AMBIVALENT": {"implications": "Ambivalent performances may indicate specific, addressable conditions rather than generalized opposition.",
        "monitor": "Conditional language; requests for evidence; questions about liability, safety, or affordability.",
        "objective": "Investigate whether uncertainty can be converted into explicit, addressable conditions.",
        "questions_and_evidence": ["Impact assessments", "Staged authorization possibilities", "Public registers", "Alternative pathway availability (to investigate)"]},
    "RESISTANT": {"implications": "Resistant performances may reflect ideological opposition, identity threat, material disadvantage, or exclusion.",
        "monitor": "Language on coercion, surveillance, loss of choice, discrimination, distrust.",
        "objective": "Investigate legitimacy and accountability concerns raised.",
        "questions_and_evidence": ["Whether appeal/human-review mechanisms exist", "Independent audit availability", "Whether non-participation pathways are preserved (to investigate)"]},
    "EXPANDER": {"implications": "Expander performances may reveal whether the prescribed future leaves the underlying problem unchanged.",
        "monitor": "Claims the intervention does not solve the underlying problem; proposals for collective alternatives.",
        "objective": "Investigate whether the policy focus should be broadened.",
        "questions_and_evidence": ["Whether deliberative input has been sought", "Funding availability for complementary pathways (to investigate)"]},
}

MANAGER_GUIDANCE = {
    "CATALYZER": {"implications": "Catalyzer enthusiasm may not generalize; investigate supporting resources before assuming replicability.",
        "monitor": "Urgency/inevitability language, pilot participation, advocacy.",
        "objective": "Investigate whether enthusiasm reflects credible, generalizable experimentation.",
        "issues_to_investigate": ["Whether pilots are governed and documented", "Whether limitations are being reported"], "avoid": ["Treating enthusiasm as evidence of inevitability without investigation"]},
    "AMBIVALENT": {"implications": "Ambivalent hesitation may identify specific, addressable barriers.",
        "monitor": "Conditional language, requests for evidence/assistance, liability questions.",
        "objective": "Investigate whether generalized uncertainty reflects specific conditions.",
        "issues_to_investigate": ["Whether comparison tools or trials are available", "Whether training/human assistance is accessible"], "avoid": ["Assuming hesitation reflects ignorance", "Applying artificial urgency"]},
    "RESISTANT": {"implications": "Investigate whether this reflects ideological opposition, identity threat, material disadvantage, or exclusion.",
        "monitor": "Language on surveillance, loss of choice, dehumanization, discrimination, distrust.",
        "objective": "Investigate legitimacy, autonomy, and accountability concerns.",
        "issues_to_investigate": ["Whether consultation or appeal mechanisms exist", "Whether opt-outs are preserved"], "avoid": ["\"There is no alternative\" messaging without investigation", "Ridicule"]},
    "EXPANDER": {"implications": "Expander critique may reveal unmet systemic needs; investigate rather than treat as out-of-scope.",
        "monitor": "Claims the intervention does not solve the underlying problem; advocacy for collective alternatives.",
        "objective": "Investigate whether systemic critique warrants incorporation.",
        "issues_to_investigate": ["Whether participatory design input has been sought", "Whether alternative governance/service models are feasible"], "avoid": ["Presenting the offering as a complete solution without investigation"]},
}

CROSS_ORIENTATION_WARNING = (
    "Cross-orientation interference check: investigate whether a response tailored "
    "to one orientation could intensify concerns for another. This requires further "
    "evidence, not a single comment."
)

# ─────────────────────────────────────────
# BENCHMARK EXAMPLES (Coding Consistency Check)
# ─────────────────────────────────────────
EXAMPLES = {
    "Select an example": {
        "prescribed": "", "comment": "", "context": "", "context_type": "NONE",
        "is_consultation": False, "activity": "", "subtype": "", "orientation": "",
        "secondary_expected": None, "negotiation_evidence_expected": None
    },
    "1. Standalone assessment -> EVALUATION": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "STALL", "orientation": "AMBIVALENT",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": None, "negotiation_evidence_expected": "NO_NEGOTIATION_EVIDENCE",
        "comment": "EV batteries remain too expensive and the charging network is inadequate."
    },
    "2. Same content used to rebut a parent -> NEGOTIATION (+ secondary Evaluation)": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "QUESTION", "orientation": "AMBIVALENT",
        "context": "EV adoption should be accelerated immediately.", "context_type": "PARENT_REPLY",
        "is_consultation": False,
        "secondary_expected": ("AMBIVALENT", "EVALUATION", "STALL"),
        "negotiation_evidence_expected": "OBSERVED_INTERACTION",
        "comment": "That ignores households without home charging. Hybrids would be a more realistic transition until the infrastructure improves."
    },
    "3. Declarative alternative future, no imperative, no context -> NEGOTIATION/CONTEST": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "CONTEST", "orientation": "EXPANDER",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": None, "negotiation_evidence_expected": "IMPLICIT_RELATIONAL_POSITIONING",
        "comment": "The future is fewer cars, not simply electric cars, in higher density pedestrian and transit-oriented urban environments."
    },
    "4. Polite request for evidence -> NEGOTIATION/QUESTION/AMBIVALENT": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "QUESTION", "orientation": "AMBIVALENT",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": None, "negotiation_evidence_expected": "IMPLICIT_RELATIONAL_POSITIONING",
        "comment": "Have you thought about what they are gonna do with all the batteries once they expire because they aren't recyclable?"
    },
    "5. Direct rejection of government authority -> NEGOTIATION/REJECT/RESISTANT": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "REJECT", "orientation": "RESISTANT",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": None, "negotiation_evidence_expected": "IMPLICIT_RELATIONAL_POSITIONING",
        "comment": "We don't need politicians and their cronies telling us what sort of car we can have."
    },
    "6. Enactment primary + Evaluation secondary (decisive action is the main point)": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "DELAY", "orientation": "AMBIVALENT",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": ("AMBIVALENT", "EVALUATION", "STALL"),
        "negotiation_evidence_expected": "NO_NEGOTIATION_EVIDENCE",
        "comment": (
            "Just bought a new petrol car last month because the EV charging "
            "infrastructure still isn't in place near me, and I'm planning to "
            "run this one for as long as it lasts before I even reconsider "
            "switching. I'm not anti-EV -- I like the idea in principle -- but "
            "the upfront cost is still a huge hurdle for me, and I don't expect "
            "that to change in the next few years."
        )
    },
    "7. EVALUATION/AVOID (narrow dismissal)": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "AVOID", "orientation": "RESISTANT",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": None, "negotiation_evidence_expected": "NO_NEGOTIATION_EVIDENCE",
        "comment": "Electric vehicles are not the solution. Electric vehicles are not the future, just a muddle point."
    },
    "8. EVALUATION/COMPLEXIFY (elaborated systemic reasoning)": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "COMPLEXIFY", "orientation": "EXPANDER",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": None, "negotiation_evidence_expected": "NO_NEGOTIATION_EVIDENCE",
        "comment": (
            "60% of the land in car-dependent cities are dedicated to cars, mainly "
            "parking and roads. Electric vehicle is a false solution if you care "
            "about the environment at all."
        )
    },
    "9. Public consultation response, relational to policy prompt": {
        "prescribed": PF_NVES, "activity": "NEGOTIATION", "subtype": "QUESTION", "orientation": "AMBIVALENT",
        "context": "This consultation asks respondents whether the proposed New Vehicle "
                   "Efficiency Standard should include additional support for regional "
                   "infrastructure.",
        "context_type": "CONSULTATION_PROMPT", "is_consultation": True,
        "secondary_expected": None, "negotiation_evidence_expected": "OBSERVED_INTERACTION",
        "comment": (
            "The proposed standard should include incentives for regional charging "
            "infrastructure, otherwise regional communities will be unfairly "
            "disadvantaged compared to metro areas."
        )
    },
    "10. No context available -> context_type NONE": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "PREVENT", "orientation": "RESISTANT",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": None, "negotiation_evidence_expected": "NO_NEGOTIATION_EVIDENCE",
        "comment": "I won't be getting one, I'll stick to my V8 and my other diesel 4x4."
    },
    "11. Named address buried in heavy critique -> NEGOTIATION/CONTEST/EXPANDER": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "CONTEST", "orientation": "EXPANDER",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": None, "negotiation_evidence_expected": "IMPLICIT_RELATIONAL_POSITIONING",
        "comment": (
            "Consumerism trumps facts. John you are so right but the first "
            "sentence prevails in modern society, why save the environment by "
            "keeping the car you already own and using it less, when you can "
            "join the Joneses, Smiths or whoever your neighbour is and spend "
            "money on that flash new hybrid/EV/hydrogen powered four wheeled "
            "status symbol that shows you earn more money than you need. Does "
            "it have to be a car? If your main priority was the environment, "
            "ride a bicycle. You're buying a 2-tonne metal box powered by a "
            "giant battery, let's not pretend we're saving the planet, we're "
            "just picking a lesser evil but it's still not good for the planet."
        )
    },
    "12. Future-vision statement inside action-heavy passage -> secondary Negotiation/Contest": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "REROUTE", "orientation": "EXPANDER",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": ("EXPANDER", "NEGOTIATION", "CONTEST"),
        "negotiation_evidence_expected": None,
        "comment": (
            "We tend to do most of our shopping by bike rather than with the ute "
            "because the ute's inconvenient to park and navigate in small car "
            "parks. I am at the moment on a waiting list for a new electric "
            "cargo bike. The future is less cars, in higher density pedestrian, "
            "bike and train-orientated urban environments, where cars are "
            "secondary transport really only for those who really need it."
        )
    },
}

# ─────────────────────────────────────────
# CONSISTENCY SAFEGUARDS
# ─────────────────────────────────────────

def _fix_pairing(orientation: str, activity: str, subtype: str):
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
    notes = []
    main_orientation = _clean_enum(result.get("main_orientation", "")).upper()
    main_activity = _clean_enum(result.get("main_activity", "")).upper()
    main_subtype = _clean_enum(result.get("activity_subtype", "")).upper()
    fixed_subtype, note = _fix_pairing(main_orientation, main_activity, main_subtype)
    result["activity_subtype"] = fixed_subtype
    if note:
        notes.append(f"Primary: {note}.")

    secondary = get_secondary_classifications(result)
    fixed_secondary = []
    for i, sec in enumerate(secondary):
        ori, act, sub = sec.get("orientation", ""), sec.get("activity", ""), sec.get("activity_subtype", "")
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


def enforce_interaction_consistency(result: dict, context_available: bool, context_type: str) -> dict:
    result["context_available"] = bool(context_available)
    result["context_type"] = context_type if context_type in VALID_CONTEXT_TYPES else "NONE"

    if not context_available:
        result["interaction_detected"] = False
        result["interaction_type"] = "NONE"
        ne = _clean_enum(result.get("negotiation_evidence", "")).upper()
        if ne == "OBSERVED_INTERACTION":
            act = _clean_enum(result.get("main_activity", "")).upper()
            secondary_acts = [s.get("activity") for s in get_secondary_classifications(result)]
            if act == "NEGOTIATION" or "NEGOTIATION" in secondary_acts:
                result["negotiation_evidence"] = "IMPLICIT_RELATIONAL_POSITIONING"
            else:
                result["negotiation_evidence"] = "NO_NEGOTIATION_EVIDENCE"
    else:
        it = _clean_enum(result.get("interaction_type", "")).upper()
        if it not in VALID_INTERACTION_TYPES:
            it = "NONE"
        result["interaction_type"] = it
        result["interaction_detected"] = bool(result.get("interaction_detected")) and it != "NONE"

    ne = _clean_enum(result.get("negotiation_evidence", "")).upper()
    if ne not in VALID_NEGOTIATION_EVIDENCE:
        ne = "NO_NEGOTIATION_EVIDENCE"
    result["negotiation_evidence"] = ne
    return result


# ─────────────────────────────────────────
# CORE FUNCTION -- focal comment + conversational context
# ─────────────────────────────────────────

def analyze_comment(prescribed_future: str, focal_text: str, context_text: str = "",
                     context_type: str = "NONE", is_consultation: bool = False,
                     api_key: str = None) -> dict:
    client = openai.OpenAI(api_key=api_key)

    if is_consultation:
        focal_label = "FOCAL RESPONSE TO CLASSIFY"
        context_label = "CONSULTATION/POLICY CONTEXT -- USE FOR INTERPRETATION BUT DO NOT CLASSIFY"
    else:
        focal_label = "FOCAL COMMENT TO CLASSIFY"
        context_label = "CONVERSATIONAL CONTEXT -- USE FOR INTERPRETATION BUT DO NOT CLASSIFY"

    context_available = bool(context_text and context_text.strip())
    context_block = context_text.strip() if context_available else "No conversational context is available for this comment."

    user_message = f"""
PRESCRIBED FUTURE:
{prescribed_future}

{focal_label}:
{focal_text}

{context_label}:
{context_block}

CONTEXT TYPE (determined by the calling application, not by you): {context_type}
CONTEXT AVAILABLE: {context_available}

Classify ONLY the focal comment/response above, using the context solely
to interpret its relational positioning (Section H). Negotiation does NOT
require an imperative or direct address -- apply the relational definition
in Section B, INCLUDING the Named-Address Sufficiency rule and the
Future-Vision Test, BEFORE weighing overall passage tone or length. If
context is unavailable, still check the focal comment's own content for
implicit relational positioning before defaulting to Evaluation. If both
substantial evaluative/negotiating content and substantial enactment
content are present, decide which is the passage's main point per Section
B/H and capture the other as a secondary classification. Verify every
activity_subtype (primary and secondary) belongs to the valid pairing
table for its own orientation. Populate policy_diagnostic_considerations
and manager_diagnostic_considerations as hedged diagnostic support only.
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
    parsed = enforce_interaction_consistency(parsed, context_available, context_type)
    return parsed


def run_consistency_suite(api_key: str) -> dict:
    results = []
    for name, ex in EXAMPLES.items():
        if not ex.get("comment"):
            continue
        try:
            pred = analyze_comment(
                ex["prescribed"], ex["comment"], ex.get("context", ""),
                ex.get("context_type", "NONE"), ex.get("is_consultation", False), api_key
            )
        except Exception as e:
            results.append({
                "example": name, "error": str(e),
                "expected": (ex["orientation"], ex["activity"], ex["subtype"]),
                "predicted": (None, None, None), "match": False,
                "secondary_expected": ex.get("secondary_expected"), "secondary_match": None,
                "negotiation_evidence_expected": ex.get("negotiation_evidence_expected"),
                "negotiation_evidence_match": None
            })
            continue
        pred_orientation = _clean_enum(pred.get("main_orientation", "")).upper()
        pred_activity    = _clean_enum(pred.get("main_activity", "")).upper()
        pred_subtype     = _clean_enum(pred.get("activity_subtype", "")).upper()
        match = (pred_orientation == ex["orientation"] and pred_activity == ex["activity"] and pred_subtype == ex["subtype"])

        secondary_match = None
        sec_expected = ex.get("secondary_expected")
        if sec_expected:
            secondary_list = get_secondary_classifications(pred)
            secondary_match = any(
                sec.get("orientation") == sec_expected[0] and sec.get("activity") == sec_expected[1]
                and sec.get("activity_subtype") == sec_expected[2] for sec in secondary_list
            )

        ne_match = None
        ne_expected = ex.get("negotiation_evidence_expected")
        if ne_expected:
            ne_match = (pred.get("negotiation_evidence") == ne_expected)

        results.append({
            "example": name,
            "expected": (ex["orientation"], ex["activity"], ex["subtype"]),
            "predicted": (pred_orientation, pred_activity, pred_subtype),
            "match": match,
            "secondary_expected": sec_expected, "secondary_match": secondary_match,
            "negotiation_evidence_expected": ne_expected, "negotiation_evidence_match": ne_match,
            "context_type_reported": pred.get("context_type")
        })
    if not results:
        return {"results": [], "overall_agreement": 0.0}
    agreement = sum(r["match"] for r in results) / len(results)
    return {"results": results, "overall_agreement": agreement}


# ─────────────────────────────────────────
# COMMENT / THREAD DATA STRUCTURES
# ─────────────────────────────────────────

def build_comment_records_from_paragraphs(text: str, separator: str = None) -> list:
    text = (text or "").strip()
    if not text:
        return []
    if separator:
        raw_items = [x.strip() for x in text.split(separator) if x.strip()]
    else:
        raw_items = [re.sub(r'\s+', ' ', p).strip() for p in re.split(r'\n\s*\n+', text) if p.strip()]
    records = []
    for i, item in enumerate(raw_items):
        if len(item.split()) < 2:
            continue
        records.append({
            "comment_id": f"c{i}", "thread_id": DEFAULT_THREAD, "parent_comment_id": None,
            "author": "", "timestamp": "", "comment_text": item, "original_index": i,
        })
    return records


def build_comment_records_from_csv(df: pd.DataFrame) -> list:
    cols = {c.lower().strip(): c for c in df.columns}
    text_col = cols.get("comment_text") or cols.get("text") or cols.get("comment")
    if not text_col:
        return []

    def safe_get(row, name, default=""):
        c = cols.get(name)
        if c and pd.notna(row.get(c)):
            return str(row.get(c)).strip()
        return default

    records = []
    for i, row in df.iterrows():
        text = str(row.get(text_col, "")).strip() if pd.notna(row.get(text_col)) else ""
        if not text:
            continue
        comment_id = safe_get(row, "comment_id", f"c{i}")
        thread_id = safe_get(row, "thread_id", DEFAULT_THREAD) or DEFAULT_THREAD
        parent_id = safe_get(row, "parent_comment_id", "") or None
        author = safe_get(row, "author", "")
        timestamp = safe_get(row, "timestamp", "")
        records.append({
            "comment_id": comment_id, "thread_id": thread_id, "parent_comment_id": parent_id,
            "author": author, "timestamp": timestamp, "comment_text": text, "original_index": i,
        })
    return records


def extract_public_consultation_responses(text: str, min_words: int = 4) -> list:
    text = re.sub(r'\s+', ' ', text.strip())
    matches = list(re.finditer(r'\b(\d{6,7})\s+(?:Name\s+withheld|[A-Z][a-z]+)', text))
    responses = []
    for idx, m in enumerate(matches):
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        resp_id = m.group(1)
        block = re.sub(r'^\d{6,7}\s+(?:Name\s+withheld|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*', '', block)
        block = re.sub(r'Option\s+[ABC]\s*-\s*\w+,?\s*', '', block, flags=re.IGNORECASE)
        block = re.sub(r'\b(Yes|No|NULL)\s*$', '', block, flags=re.IGNORECASE).strip()
        block = re.sub(r'\s{2,}', ' ', block).strip(' ,.-')
        if not block or block.upper() == "NULL":
            continue
        if len(block.split()) >= min_words:
            responses.append({"id": resp_id, "text": block})
    return responses


def build_comment_records_from_consultation(text: str) -> list:
    raw = extract_public_consultation_responses(text)
    records = []
    for i, item in enumerate(raw):
        records.append({
            "comment_id": f"resp_{item['id']}", "thread_id": DEFAULT_THREAD, "parent_comment_id": None,
            "author": "", "timestamp": "", "comment_text": item["text"], "original_index": i,
        })
    return records


def index_threads(records: list):
    by_id = {r["comment_id"]: r for r in records}
    thread_order = {}
    for r in records:
        thread_order.setdefault(r["thread_id"], []).append(r["comment_id"])
    return by_id, thread_order


def build_context(record: dict, by_id: dict, thread_order: dict,
                   consultation_prompt: str = None, is_consultation: bool = False):
    parts = []
    context_type = "NONE"
    focal_id = record["comment_id"]
    thread_id = record["thread_id"]
    order = thread_order.get(thread_id, [focal_id])
    idx_in_thread = order.index(focal_id) if focal_id in order else 0

    parent_id = record.get("parent_comment_id")
    parent_record = by_id.get(parent_id) if parent_id else None
    if parent_record and parent_record.get("thread_id") != thread_id:
        parent_record = None

    if parent_record:
        parts.append(f"PARENT COMMENT:\n{parent_record['comment_text']}")
        context_type = "PARENT_REPLY"

    preceding_ids = order[max(0, idx_in_thread - 2):idx_in_thread]
    preceding_ids = [pid for pid in preceding_ids if pid != parent_id]
    for pid in preceding_ids:
        parts.append(f"PRECEDING COMMENT:\n{by_id[pid]['comment_text']}")
        if context_type == "NONE":
            context_type = "THREAD_WINDOW"

    following_record = None
    for cid in order:
        cand = by_id.get(cid)
        if cand and cand.get("parent_comment_id") == focal_id:
            following_record = cand
            break
    if following_record:
        parts.append(f"FOLLOWING REPLY:\n{following_record['comment_text']}")
        if context_type == "NONE":
            context_type = "THREAD_WINDOW"

    if order:
        root_record = by_id.get(order[0])
        if (root_record and root_record["comment_id"] not in (focal_id, parent_id)
                and not root_record.get("parent_comment_id")):
            parts.append(f"ORIGINAL POST:\n{root_record['comment_text']}")
            if context_type == "NONE":
                context_type = "ORIGINAL_POST"

    if is_consultation and consultation_prompt and consultation_prompt.strip():
        parts.append(f"CONSULTATION QUESTION / POLICY CONTEXT:\n{consultation_prompt.strip()}")
        if context_type == "NONE":
            context_type = "CONSULTATION_PROMPT"

    context_text = "\n\n".join(parts)
    return context_text, context_type, bool(parts)


def compute_evenly_spaced_sample_indices(total: int, k: int) -> list:
    if total <= 0 or k <= 0:
        return []
    if k >= total:
        return list(range(total))
    if k == 1:
        return [total // 2]
    step = (total - 1) / (k - 1)
    seen = set()
    for i in range(k):
        idx = max(0, min(total - 1, int(round(i * step))))
        probe, forward = idx, True
        while probe in seen:
            probe = probe + 1 if forward else probe - 1
            if probe >= total:
                probe, forward = idx, False
                continue
            if probe < 0:
                break
        seen.add(max(0, min(total - 1, probe)))
    return sorted(seen)


def analyze_document(prepared_records: list, prescribed_future: str, api_key: str, progress_bar=None) -> list:
    total = len(prepared_records)
    results = [None] * total
    with concurrent.futures.ThreadPoolExecutor(max_workers=DOC_MAX_WORKERS) as executor:
        future_to_pos = {
            executor.submit(
                analyze_comment, prescribed_future, rec["comment_text"], rec["context_text"],
                rec["context_type"], rec["is_consultation"], api_key
            ): pos
            for pos, rec in enumerate(prepared_records)
        }
        completed = 0
        for future in concurrent.futures.as_completed(future_to_pos):
            pos = future_to_pos[future]
            rec = prepared_records[pos]
            try:
                r = future.result()
            except Exception as e:
                r = {"_error": str(e)}
            r["_comment_id"] = rec["comment_id"]
            r["_thread_id"] = rec["thread_id"]
            r["_parent_comment_id"] = rec["parent_comment_id"]
            r["_comment_text"] = rec["comment_text"]
            r["_original_index"] = rec["original_index"]
            results[pos] = r
            completed += 1
            if progress_bar is not None:
                progress_bar.progress(completed / total, text=f"Analyzed {completed}/{total} comments...")
    return sorted([r for r in results if r is not None], key=lambda r: r.get("_original_index", 0))


# ─────────────────────────────────────────
# CORPUS-LEVEL AGGREGATION
# ─────────────────────────────────────────

def compute_observed_interaction_pairs(results: list) -> dict:
    by_comment_id = {r.get("_comment_id"): r for r in results if r and "_error" not in r and r.get("_comment_id")}
    pairs = {}
    for r in results:
        if not r or "_error" in r:
            continue
        parent_id = r.get("_parent_comment_id")
        if parent_id and parent_id in by_comment_id:
            parent_r = by_comment_id[parent_id]
            parent_ori = _clean_enum(parent_r.get("main_orientation", "")).upper()
            child_ori = _clean_enum(r.get("main_orientation", "")).upper()
            if parent_ori in ORIENTATIONS and child_ori in ORIENTATIONS:
                key = (parent_ori, child_ori)
                pairs[key] = pairs.get(key, 0) + 1
    return pairs


def compute_observed_challenge_signals(results: list) -> dict:
    by_comment_id = {r.get("_comment_id"): r for r in results if r and "_error" not in r and r.get("_comment_id")}
    signals = {"CONVOLUTED_EVALUATIONS": 0, "CONFRONTATIONAL_NEGOTIATIONS": 0, "COMPETING_ENACTMENTS": 0}
    detail = []
    for r in results:
        if not r or "_error" in r:
            continue
        parent_id = r.get("_parent_comment_id")
        if not parent_id or parent_id not in by_comment_id:
            continue
        parent_r = by_comment_id[parent_id]
        parent_ori = _clean_enum(parent_r.get("main_orientation", "")).upper()
        child_ori = _clean_enum(r.get("main_orientation", "")).upper()
        if parent_ori == child_ori or parent_ori not in ORIENTATIONS or child_ori not in ORIENTATIONS:
            continue
        interaction_type = _clean_enum(r.get("interaction_type", "")).upper()
        if interaction_type in ("AGREEMENT", "REINFORCEMENT"):
            continue
        child_act = _clean_enum(r.get("main_activity", "")).upper()
        parent_act = _clean_enum(parent_r.get("main_activity", "")).upper()
        pathway = None
        if child_act == "EVALUATION" and parent_act == "EVALUATION":
            pathway = "CONVOLUTED_EVALUATIONS"
        elif child_act == "NEGOTIATION" or parent_act == "NEGOTIATION":
            pathway = "CONFRONTATIONAL_NEGOTIATIONS"
        elif child_act == "ENACTMENT" and parent_act == "ENACTMENT":
            pathway = "COMPETING_ENACTMENTS"
        if pathway:
            signals[pathway] += 1
            detail.append({"parent": parent_r, "reply": r, "pathway": pathway})
    return signals, detail


def summarize_document_results(results: list, total_detected: int) -> dict:
    valid = [r for r in results if r and "_error" not in r]
    errors = [r for r in results if r and "_error" in r]
    n = len(valid)
    if n == 0:
        return {"n_analyzed": 0, "n_errors": len(errors), "total_detected": total_detected}

    orientation_counts, activity_counts, challenge_counts = {}, {}, {}
    theoretical_contrast_pairs = {}
    n_with_context, n_without_context = 0, 0
    n_negotiation, n_negotiation_observed, n_negotiation_implicit = 0, 0, 0

    for r in valid:
        ori = _clean_enum(r.get("main_orientation", "")).upper()
        act = _clean_enum(r.get("main_activity", "")).upper()
        secondary = get_secondary_classifications(r)
        pathways = derive_challenge_pathways(act, secondary)
        contrast = get_contrasting_orientation(r)
        ctx_available = bool(r.get("context_available"))
        ne = _clean_enum(r.get("negotiation_evidence", "")).upper()

        if ori:
            orientation_counts[ori] = orientation_counts.get(ori, 0) + 1
        if act:
            activity_counts[act] = activity_counts.get(act, 0) + 1
        for p in pathways:
            challenge_counts[p] = challenge_counts.get(p, 0) + 1

        if ctx_available:
            n_with_context += 1
        else:
            n_without_context += 1
            if ori in ORIENTATIONS and contrast in ORIENTATIONS:
                pair = tuple(sorted([ori, contrast]))
                theoretical_contrast_pairs[pair] = theoretical_contrast_pairs.get(pair, 0) + 1

        if act == "NEGOTIATION":
            n_negotiation += 1
            if ne == "OBSERVED_INTERACTION":
                n_negotiation_observed += 1
            elif ne == "IMPLICIT_RELATIONAL_POSITIONING":
                n_negotiation_implicit += 1

    observed_pairs = compute_observed_interaction_pairs(valid)
    observed_challenge_signals, observed_challenge_detail = compute_observed_challenge_signals(valid)

    most_freq_ori = max(orientation_counts, key=orientation_counts.get) if orientation_counts else None
    most_freq_act = max(activity_counts, key=activity_counts.get) if activity_counts else None
    most_freq_chal = max(challenge_counts, key=challenge_counts.get) if challenge_counts else None

    return {
        "total_detected": total_detected,
        "n_analyzed": n, "n_errors": len(errors),
        "n_with_context": n_with_context, "n_without_context": n_without_context,
        "n_negotiation": n_negotiation, "n_negotiation_observed": n_negotiation_observed,
        "n_negotiation_implicit": n_negotiation_implicit,
        "orientation_counts": orientation_counts, "activity_counts": activity_counts,
        "challenge_counts": challenge_counts,
        "theoretical_contrast_pairs": theoretical_contrast_pairs,
        "observed_interaction_pairs": observed_pairs,
        "observed_challenge_signals": observed_challenge_signals,
        "observed_challenge_detail": observed_challenge_detail,
        "most_frequent_orientation": most_freq_ori, "most_frequent_activity": most_freq_act,
        "most_frequent_challenge": most_freq_chal,
    }


def build_narrative_summary(summary: dict, intervention_type_key: str = None) -> str:
    n = summary.get("n_analyzed", 0)
    if n == 0:
        return "No comments could be analyzed."

    def pct(cnt):
        return round(cnt / n * 100, 1)

    lines = []
    most_freq_ori = summary.get("most_frequent_orientation")
    ori_counts = summary["orientation_counts"]
    if most_freq_ori:
        ori_meta = ORIENTATIONS.get(most_freq_ori, {})
        lines.append(
            f"Across **{n}** analyzed comments (out of **{summary.get('total_detected', n)}** "
            f"comments detected), the most frequent dominant orientation among analyzed "
            f"comments is **{most_freq_ori}** ({pct(ori_counts[most_freq_ori])}%), associated "
            f"with a *{ori_meta.get('narrative','')}* -- \"{ori_meta.get('tagline','')}\""
        )

    sorted_ori = sorted(ori_counts.items(), key=lambda x: -x[1])
    lines.append(
        "**Orientation distribution among analyzed comments:** "
        + ", ".join(f"{k} {pct(v)}%" for k, v in sorted_ori)
        + ". These percentages describe analyzed comments, not unique consumers or population prevalence."
    )

    lines.append(
        f"**Context coverage:** {summary.get('n_with_context',0)} of {n} analyzed comments had "
        f"available conversational context; {summary.get('n_without_context',0)} did not."
    )

    n_neg = summary.get("n_negotiation", 0)
    if n_neg:
        lines.append(
            f"**Negotiation identified in {n_neg} comments** ({pct(n_neg)}%): "
            f"{summary.get('n_negotiation_observed',0)} based on observed interaction, "
            f"{summary.get('n_negotiation_implicit',0)} based on implicit relational "
            f"positioning (no confirmed context)."
        )

    most_freq_chal = summary.get("most_frequent_challenge")
    chal_counts = summary["challenge_counts"]
    if most_freq_chal and most_freq_chal != "N/A":
        chal_meta = CHALLENGE_PATHWAYS.get(most_freq_chal, {})
        lines.append(
            f"The most frequent potential challenge signal within analyzed comments is "
            f"**{chal_meta.get('label', most_freq_chal)}** ({pct(chal_counts[most_freq_chal])}%): "
            f"{chal_meta.get('description','')}"
        )

    if len([k for k, v in ori_counts.items() if v > 0]) >= 2:
        lines.append(
            "Multiple future-making orientations were detected within the analyzed "
            "comments. This heterogeneity identifies a need for contextual "
            "examination of whether differently oriented performances coexist, "
            "clash, or interfere with one another. Orientation diversity alone does "
            "not establish Fragile Futures."
        )

    if intervention_type_key and intervention_type_key in INTERVENTION_TYPES:
        it = INTERVENTION_TYPES[intervention_type_key]
        if it.get("note"):
            lines.append(
                f"**Intervention type context** ({intervention_type_key.split(' (')[0]}, "
                f"{it['scope']} scope / {it['prescriptiveness']} prescriptive): {it['note']} "
                f"This is contextual information; it does not predetermine the orientations "
                f"or challenge pathways found above."
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
                <span style="color:#666;">{cnt} comments ({pct_val}%)</span>
            </div>
            <div style="background:#eee;border-radius:6px;height:14px;width:100%;overflow:hidden;">
                <div style="background:{color};width:{pct_val}%;height:14px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def _serialize_secondary(secondary_list: list) -> str:
    if not secondary_list:
        return ""
    return " || ".join(
        f"{s.get('orientation','')}/{s.get('activity','')}/{s.get('activity_subtype','')}: {s.get('rationale','')}"
        for s in secondary_list
    )


def _serialize_considerations(d: dict) -> str:
    if not d:
        return ""
    parts = [f"Step: {d.get('step','')}", f"Objective: {d.get('objective','')}"]
    for key in ("questions_and_evidence", "additional_considerations", "issues_to_investigate", "avoid"):
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
        base = {
            "comment_index": r.get("_original_index", ""),
            "comment_id": r.get("_comment_id", ""),
            "thread_id": r.get("_thread_id", ""),
            "parent_comment_id": r.get("_parent_comment_id", ""),
            "comment_text": r.get("_comment_text", ""),
        }
        if "_error" in r:
            base.update({
                "main_orientation": "ERROR", "main_activity": "", "main_subtype": "",
                "secondary_classifications": "", "potential_challenge_pathways": "",
                "theoretically_contrasting_orientation": "", "context_available": "",
                "context_type": "", "interaction_detected": "", "interaction_type": "",
                "interaction_target": "", "negotiation_evidence": "",
                "orientation_rationale": "", "activity_rationale": "",
                "challenge_pathway_rationale": "", "input_scope_warning": "",
                "policy_diagnostic_considerations": "", "manager_diagnostic_considerations": "",
                "error": r.get("_error", "")
            })
            rows.append(base)
            continue
        act = _clean_enum(r.get("main_activity", "")).upper()
        secondary = get_secondary_classifications(r)
        pathways = derive_challenge_pathways(act, secondary)
        pathway_labels = [CHALLENGE_PATHWAYS.get(p, {}).get("label", p) for p in pathways]
        base.update({
            "main_orientation": _clean_enum(r.get("main_orientation", "")).upper(),
            "main_activity": act,
            "main_subtype": _clean_enum(r.get("activity_subtype", "")).upper(),
            "secondary_classifications": _serialize_secondary(secondary),
            "potential_challenge_pathways": "; ".join(pathway_labels),
            "theoretically_contrasting_orientation": get_contrasting_orientation(r),
            "context_available": r.get("context_available", ""),
            "context_type": r.get("context_type", ""),
            "interaction_detected": r.get("interaction_detected", ""),
            "interaction_type": r.get("interaction_type", ""),
            "interaction_target": r.get("interaction_target", ""),
            "negotiation_evidence": r.get("negotiation_evidence", ""),
            "orientation_rationale": r.get("orientation_rationale", ""),
            "activity_rationale": r.get("activity_rationale", ""),
            "challenge_pathway_rationale": r.get("potential_challenge_rationale", ""),
            "input_scope_warning": get_input_scope_warning(r),
            "policy_diagnostic_considerations": _serialize_considerations(get_policy_considerations(r)),
            "manager_diagnostic_considerations": _serialize_considerations(get_manager_considerations(r)),
            "error": ""
        })
        rows.append(base)
    return pd.DataFrame(rows)


def show_document_summary(results: list, prescribed_future: str, intervention_type_key: str = None,
                           total_detected: int = None, sampling_description: str = ""):
    summary = summarize_document_results(results, total_detected or len(results))
    n = summary.get("n_analyzed", 0)
    n_errors = summary.get("n_errors", 0)

    if n == 0:
        st.error("No comments could be successfully analyzed.")
        return

    st.markdown(f"""
    <div style="background:#EBF5FB;border-left:5px solid #2980B9;border-radius:8px;padding:12px 18px;margin-bottom:16px;">
        <strong style="color:#2980B9;">Prescribed Future Analyzed:</strong><br>
        <em style="color:#333;">{prescribed_future}</em>
    </div>
    """, unsafe_allow_html=True)

    if sampling_description:
        st.caption(f"**Sampling:** {sampling_description}")

    st.info(INTERPRETIVE_USE_NOTE)
    st.info(NEGOTIATION_CONTEXT_NOTE)

    if n_errors:
        st.warning(f"{n_errors} comment(s) failed to analyze and were excluded from the summary.")

    st.markdown("### Executive Summary")
    st.markdown(build_narrative_summary(summary, intervention_type_key))

    st.markdown("---")
    st.markdown("### Comments Analyzed & Context Coverage")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total comments detected", summary.get("total_detected", n))
    c2.metric("Focal comments analyzed", n)
    c3.metric("With conversational context", summary.get("n_with_context", 0))
    c4.metric("Without context", summary.get("n_without_context", 0))
    c5, c6, c7 = st.columns(3)
    c5.metric("Classified as Negotiation", summary.get("n_negotiation", 0))
    c6.metric("Negotiation -- observed interaction", summary.get("n_negotiation_observed", 0))
    c7.metric("Negotiation -- implicit positioning", summary.get("n_negotiation_implicit", 0))

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### Dominant Orientations Within Analyzed Comments")
        render_pct_bars(summary["orientation_counts"], ORIENTATIONS, n)
        st.caption("Percentages describe analyzed comments, not unique consumers or population prevalence.")
    with col2:
        st.markdown("#### Activities Identified Across Analyzed Comments")
        render_pct_bars(summary["activity_counts"], ACTIVITY_META, n)
    with col3:
        st.markdown("#### Potential Challenge Signals Across Analyzed Comments")
        render_pct_bars(summary["challenge_counts"], CHALLENGE_PATHWAYS, n, label_key_name="label")
        st.caption("A signal indicates a comment's activity could contribute to this pathway if it clashes with a differently oriented performance.")

    st.markdown("---")
    st.markdown("### Observed Interaction Pairs")
    st.caption(
        "Only pairs supported by a REAL parent-reply relationship, where BOTH "
        "the parent and the reply were classified as focal comments."
    )
    observed_pairs = summary.get("observed_interaction_pairs", {})
    if observed_pairs:
        for (parent_ori, child_ori), cnt in sorted(observed_pairs.items(), key=lambda x: -x[1]):
            st.markdown(f"- **{parent_ori}** -> **{child_ori}** reply: {cnt} observed pair(s)")
    else:
        st.caption("No observed parent-reply pairs were found among the analyzed comments (structured thread/parent data may be unavailable).")

    st.markdown("---")
    st.markdown("### Potential Challenge Signals within Observed Exchanges")
    st.caption(
        "Requires at least two related, classified comments from the same "
        "exchange, differently oriented performances, and evidence of "
        "divergence (no agreement/reinforcement). Described as potential "
        "signals requiring interpretation across the wider corpus -- not a "
        "diagnosis of Fragile Futures from a single interaction."
    )
    observed_signals = summary.get("observed_challenge_signals", {})
    if any(observed_signals.values()):
        render_pct_bars({k: v for k, v in observed_signals.items() if v > 0}, CHALLENGE_PATHWAYS, sum(observed_signals.values()), label_key_name="label")
    else:
        st.caption("No potential challenge signals could be identified from observed exchanges in this sample.")

    st.markdown("---")
    st.markdown("### Most Frequent Theoretical Contrast Pairs")
    st.caption(
        "Theoretical contrasts inferred from the framework, shown ONLY for "
        "comments WITHOUT conversational context (comments with context are "
        "represented above under Observed Interaction Pairs instead)."
    )
    contrast_pairs = summary.get("theoretical_contrast_pairs", {})
    if contrast_pairs:
        for pair, cnt in sorted(contrast_pairs.items(), key=lambda x: -x[1])[:6]:
            o1, o2 = pair
            st.markdown(f"- **{o1}** vs. **{o2}**: {cnt} comment(s)")
    else:
        st.caption("No theoretical contrast pairs identified (or all analyzed comments had conversational context).")

    st.markdown("---")
    st.markdown("### Diagnostic Considerations by Orientation")
    st.caption("These considerations support diagnostic roadmap steps. They are not definitive recommendations.")
    top_orientations = sorted(summary["orientation_counts"].items(), key=lambda x: -x[1])[:2]
    policy_tab, manager_tab = st.tabs(["Policy Diagnostic Considerations", "Managerial Diagnostic Considerations"])
    with policy_tab:
        for ori, cnt in top_orientations:
            guidance, cfg = POLICY_GUIDANCE.get(ori, {}), ORIENTATIONS.get(ori, {})
            st.markdown(f"**{ori}** ({round(cnt/n*100,1)}% of comments) -- \"{cfg.get('tagline','')}\"")
            st.markdown(f"*Could indicate:* {guidance.get('implications','--')}")
            st.markdown(f"*Objective:* {guidance.get('objective','--')}")
            for q in guidance.get("questions_and_evidence", []):
                st.markdown(f"- {q}")
            st.markdown("")
    with manager_tab:
        for ori, cnt in top_orientations:
            guidance, cfg = MANAGER_GUIDANCE.get(ori, {}), ORIENTATIONS.get(ori, {})
            st.markdown(f"**{ori}** ({round(cnt/n*100,1)}% of comments) -- \"{cfg.get('tagline','')}\"")
            st.markdown(f"*Could indicate:* {guidance.get('implications','--')}")
            st.markdown(f"*Objective:* {guidance.get('objective','--')}")
            for issue in guidance.get("issues_to_investigate", []):
                st.markdown(f"- {issue}")
            if guidance.get("avoid"):
                st.markdown(f"*Avoid:* {', '.join(guidance['avoid'])}")
            st.markdown("")
        if len(top_orientations) >= 2:
            st.info(CROSS_ORIENTATION_WARNING)

    st.markdown("---")
    st.markdown("### Comment-Level Detail")
    df = build_results_dataframe(results)
    display_cols = ["comment_index", "comment_id", "parent_comment_id", "main_orientation",
                     "main_activity", "main_subtype", "context_type", "negotiation_evidence",
                     "potential_challenge_pathways"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols] if display_cols else df, use_container_width=True, height=350)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download full results as CSV (includes comment_id, thread_id, parent_comment_id, and all rationale fields)",
        data=csv_bytes, file_name="future_making_comment_analysis.csv", mime="text/csv"
    )

    st.markdown("---")
    st.markdown("### Comment Rationale Explorer")
    valid_indexed = [(i, r) for i, r in enumerate(results) if r and "_error" not in r]
    if valid_indexed:
        option_labels = [f"[{r.get('_comment_id', i)}] {r.get('_comment_text', '')[:90]}..." for i, r in valid_indexed]
        chosen_pos = st.selectbox("Choose a comment to inspect:", options=range(len(option_labels)), format_func=lambda x: option_labels[x])
        chosen_idx, chosen_result = valid_indexed[chosen_pos]
        st.markdown("**Full focal comment text:**")
        st.info(chosen_result.get("_comment_text", ""))
        show_results(chosen_result, prescribed_future, show_interpretive_note=False)
    else:
        st.caption("No valid comments available to explore.")


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
        <span style="background:{cfg['bg']};border:2px solid {cfg['border']};color:{cfg['color']};border-radius:20px;padding:4px 14px;font-weight:bold;font-size:13px;">{ori}</span>
        <span style="font-size:16px;color:#aaa;">-></span>
        <span style="background:{ameta['bg']};border:2px solid {ameta['color']};color:{ameta['color']};border-radius:20px;padding:4px 14px;font-weight:bold;font-size:13px;">{act}</span>
        <span style="font-size:16px;color:#aaa;">-></span>
        <span style="background:#f0f0f0;border:2px solid #bbb;color:#444;border-radius:20px;padding:4px 14px;font-weight:bold;font-size:13px;">{sub}</span>
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
    <div style="background:#EBF5FB;border-left:5px solid #2980B9;border-radius:8px;padding:12px 18px;margin-bottom:16px;">
        <strong style="color:#2980B9;">Prescribed Future Analyzed:</strong><br>
        <em style="color:#333;">{prescribed_future}</em>
    </div>
    """, unsafe_allow_html=True)

    warning_text = get_input_scope_warning(result)
    if warning_text:
        st.warning(f"Input-scope note: {warning_text}")
    if result.get("_consistency_note"):
        st.caption(f"Note: {result['_consistency_note']}")

    ctx_type = result.get("context_type", "NONE")
    ctx_available = result.get("context_available", False)
    st.caption(
        f"**Context type used for interpretation:** {ctx_type}"
        + (" (no conversational context was available for this comment)" if not ctx_available else "")
    )

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        cfg = ORIENTATIONS.get(orientation, {})
        st.markdown(f"""
        <div style="background:{cfg.get('bg','#f5f5f5')};border-left:6px solid {cfg.get('border','#999')};border-radius:10px;padding:16px 18px;min-height:230px;">
            <h3 style="color:{cfg.get('color','#555')};margin:0;font-size:22px;">{orientation}</h3>
            <p style="color:#666;margin:4px 0 3px;font-size:12px;"><strong>Confidence:</strong> {result.get('orientation_confidence','N/A')}</p>
            <p style="color:#777;margin:2px 0;font-size:11px;font-style:italic;">"{cfg.get('tagline','')}"</p>
            <p style="color:#777;margin:2px 0;font-size:11px;">{cfg.get('narrative','')}</p>
            <p style="color:#777;margin:2px 0;font-size:11px;">{cfg.get('temporality','')}</p>
            <p style="color:#777;margin:2px 0;font-size:11px;">{cfg.get('goal','')}</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        ameta = ACTIVITY_META.get(main_act, {})
        sub_cfg = ORIENTATIONS.get(orientation, {})
        st.markdown(f"""
        <div style="background:{ameta.get('bg','#f5f5f5')};border-left:6px solid {ameta.get('color','#555')};border-radius:10px;padding:16px 18px;min-height:230px;">
            <h3 style="color:{ameta.get('color','#555')};margin:0;font-size:20px;">{main_act}</h3>
            <p style="color:#555;margin:4px 0 3px;font-size:12px;"><strong>Primary Future-Making Activity</strong></p>
            <span style="background:{sub_cfg.get('bg','#f5f5f5')};border:1.5px solid {sub_cfg.get('color','#555')};color:{sub_cfg.get('color','#555')};border-radius:12px;padding:3px 10px;font-weight:bold;font-size:12px;">-> {act_sub}</span>
            <p style="color:#777;margin:8px 0 0;font-size:11px;font-style:italic;">{ameta.get('definition','')}</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        pathway_labels = [CHALLENGE_PATHWAYS.get(p, {}).get("label", p) for p in pathways]
        st.markdown(f"""
        <div style="background:{chg['bg']};border-left:6px solid {chg['color']};border-radius:10px;padding:16px 18px;min-height:230px;">
            <h3 style="color:{chg['color']};margin:0;font-size:20px;">{chg['label']}</h3>
            <p style="color:#555;margin:4px 0 3px;font-size:12px;"><strong>Potential Challenge Pathway</strong></p>
            <p style="color:#777;margin:3px 0;font-size:11px;">{chg['description']}</p>
            {"<p style='color:#999;margin:4px 0 0;font-size:10px;'>Additional signals: " + ", ".join(pathway_labels[1:]) + "</p>" if len(pathway_labels) > 1 else ""}
        </div>
        """, unsafe_allow_html=True)

    ne = result.get("negotiation_evidence", "NO_NEGOTIATION_EVIDENCE")
    it = result.get("interaction_type", "NONE")
    if main_act == "NEGOTIATION" or it != "NONE":
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:#F4F6F7;border:1px solid #D5D8DC;border-radius:10px;padding:14px 18px;">
            <h4 style="margin:0 0 8px;font-size:15px;color:#2C3E50;">Interaction Analysis</h4>
            <p style="font-size:12px;color:#555;margin:2px 0;"><strong>Interaction detected:</strong> {result.get('interaction_detected', False)}</p>
            <p style="font-size:12px;color:#555;margin:2px 0;"><strong>Interaction type:</strong> {it}</p>
            <p style="font-size:12px;color:#555;margin:2px 0;"><strong>Interaction target:</strong> {result.get('interaction_target','--')}</p>
            <p style="font-size:12px;color:#555;margin:2px 0;"><strong>Negotiation evidence:</strong> {ne}</p>
            <p style="font-size:12px;color:#666;margin:6px 0 0;font-style:italic;">{result.get('interaction_rationale','--')}</p>
        </div>
        """, unsafe_allow_html=True)

    contrast_ori = get_contrasting_orientation(result)
    contrast_cfg = ORIENTATIONS.get(contrast_ori)
    if contrast_cfg:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:#FFF8F0;border:2px dashed #E67E22;border-radius:10px;padding:16px 18px;">
            <h4 style="color:#E67E22;margin:0 0 8px;font-size:16px;">Theoretically Contrasting Orientation</h4>
            <p style="font-size:13px;color:#555;margin:0 0 6px;">
                This comment's configuration most theoretically contrasts with a
                <strong style="color:{contrast_cfg['color']};">{contrast_ori}</strong> orientation.
                This is a theoretical contrast, not an observed interaction, unless a real
                parent-reply relationship connects this comment to one with that orientation.
            </p>
            <p style="font-size:12px;color:#777;font-style:italic;margin:0;">"{result.get('potential_challenge_rationale','--')}"</p>
        </div>
        """, unsafe_allow_html=True)

    if secondary:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Secondary Classification(s)")
        for sec in secondary:
            sec_ori, sec_act, sec_sub = sec.get("orientation", ""), sec.get("activity", ""), sec.get("activity_subtype", "")
            sec_cfg, sec_ameta = ORIENTATIONS.get(sec_ori, {}), ACTIVITY_META.get(sec_act, {})
            st.markdown(f"""
            <div style="border:1px solid #ddd;border-radius:8px;padding:10px 14px;margin-bottom:8px;background:#fafafa;">
                <span style="background:{sec_cfg.get('bg','#eee')};border:1.5px solid {sec_cfg.get('border','#999')};color:{sec_cfg.get('color','#555')};border-radius:14px;padding:3px 10px;font-weight:bold;font-size:12px;">{sec_ori or 'N/A'}</span>
                &nbsp;-> &nbsp;
                <span style="background:{sec_ameta.get('bg','#eee')};border:1.5px solid {sec_ameta.get('color','#999')};color:{sec_ameta.get('color','#555')};border-radius:14px;padding:3px 10px;font-weight:bold;font-size:12px;">{sec_act or 'N/A'} / {sec_sub or 'N/A'}</span>
                <p style="font-size:12px;color:#666;margin:6px 0 0;">{sec.get('rationale','')}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    tab_ori, tab_act, tab_chg = st.tabs(["Orientation Rationale", "Activity Rationale", "Challenge Pathway Rationale"])
    with tab_ori:
        st.write(result.get("orientation_rationale", "--"))
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("**Narrative**"); c1.caption(result.get("narrative_identified", "--"))
        c2.markdown("**Emotions**"); c2.caption(result.get("dominant_emotions", "--"))
        c3.markdown("**Temporality**"); c3.caption(result.get("temporality_expressed", "--"))
        c4.markdown("**Notable Conditions**"); c4.caption(result.get("notable_conditions_of_adoption", "--"))
    with tab_act:
        st.write(result.get("activity_rationale", "--"))
        for act_name, meta in ACTIVITY_META.items():
            is_main = (act_name == main_act)
            border = f"3px solid {meta['color']}" if is_main else "1px solid #ddd"
            st.markdown(f"""
            <div style="border:{border};border-radius:8px;padding:10px 14px;margin-bottom:8px;background:{'#fff' if is_main else '#fafafa'};">
                <strong style="color:{meta['color']};">{act_name}</strong>
                {'<span style="background:#27AE60;color:white;border-radius:8px;padding:1px 8px;font-size:11px;margin-left:8px;">PRIMARY</span>' if is_main else ''}<br>
                <span style="font-size:11px;color:#555;">{meta['definition']}</span>
            </div>
            """, unsafe_allow_html=True)
    with tab_chg:
        st.write(result.get("potential_challenge_rationale", "--"))
        pathway_labels_full = [CHALLENGE_PATHWAYS.get(p, {}).get("label", p) for p in pathways]
        st.caption(f"Deterministic mapping applied: {', '.join(pathway_labels_full) if pathway_labels_full else 'N/A'} (potential pathways, not confirmed challenges).")

    st.markdown("---")
    st.markdown("## Diagnostic Support (Policy and Managerial)")
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
            for a in policy.get("additional_considerations", []) or []:
                st.markdown(f"- {a}")
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
        st.info(manager.get("communication_consideration", "--"))
        st.caption(CROSS_ORIENTATION_WARNING)

    st.markdown("---")
    st.caption(f"\"{PAPER_TITLE}\" | Read the paper: {PAPER_URL}")


# ─────────────────────────────────────────
# BREADCRUMB / INTERVENTION TYPE / MODE SELECTOR
# ─────────────────────────────────────────

def render_breadcrumb(*items, current=None):
    if current is None:
        current = len(items) - 1
    parts = [f"<strong style='color:#2980B9;'>{label}</strong>" if i == current else f"<span style='color:#999;'>{label}</span>"
              for i, label in enumerate(items)]
    st.markdown("<div style='font-size:13px;margin:2px 0 14px 0;'>" + " &nbsp;&rsaquo;&nbsp; ".join(parts) + "</div>", unsafe_allow_html=True)


def render_intervention_type_selector(key_suffix: str):
    st.markdown("**Intervention type**")
    st.caption(
        "Describes the scope of intended change and how prescriptive the "
        "intervention is. This context helps interpret the prescribed "
        "future; it does not predetermine which orientations, activities, "
        "or challenge pathways will appear in the data."
    )
    it_key = st.selectbox(
        "Choose the intervention type:", options=list(INTERVENTION_TYPES.keys()),
        index=None, placeholder="No intervention type selected -- click to choose (optional)",
        key=f"it_{key_suffix}"
    )
    if it_key is None:
        st.warning("No intervention type selected. The analysis will proceed without this contextual information.")
    else:
        it_data = INTERVENTION_TYPES[it_key]
        st.caption(f"**Example:** {it_data['example']}")
        st.caption(it_data["note"])
    return it_key


def render_mode_selector():
    st.markdown("""
    <style>
    div.st-key-mode_single_btn_active button { background-color:#2980B9 !important;border:2px solid #2980B9 !important;color:white !important;font-weight:bold !important; }
    div.st-key-mode_single_btn_inactive button { background-color:#EBF5FB !important;border:2px solid #AED6F1 !important;color:#888 !important;font-weight:normal !important; }
    div.st-key-mode_doc_btn_active button { background-color:#8E44AD !important;border:2px solid #8E44AD !important;color:white !important;font-weight:bold !important; }
    div.st-key-mode_doc_btn_inactive button { background-color:#F5EEF8 !important;border:2px solid #D7BDE2 !important;color:#888 !important;font-weight:normal !important; }
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
        label = f"[Selected] {MODE_SINGLE_LABEL}" if is_active else MODE_SINGLE_LABEL
        if st.button(label, key="mode_single_btn_active" if is_active else "mode_single_btn_inactive", use_container_width=True) and not is_active:
            st.session_state["pending_mode"] = MODE_SINGLE
            st.rerun()
    with col2:
        is_active2 = (active_mode == MODE_DOC)
        label2 = f"[Selected] {MODE_DOC_LABEL}" if is_active2 else MODE_DOC_LABEL
        if st.button(label2, key="mode_doc_btn_active" if is_active2 else "mode_doc_btn_inactive", use_container_width=True) and not is_active2:
            st.session_state["pending_mode"] = MODE_DOC
            st.rerun()

    pending_mode = st.session_state["pending_mode"]
    if pending_mode and pending_mode != active_mode:
        pending_label = MODE_SINGLE_LABEL if pending_mode == MODE_SINGLE else MODE_DOC_LABEL
        st.warning(f"Switch to **'{pending_label}'**? Any unsaved input in the current mode may be lost.")
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
        <div style="background:{active_bg};border-left:4px solid {active_color};padding:8px 14px;border-radius:6px;margin:10px 0 16px 0;">
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
        prescribed_future = st.text_area("prescribed_future", value=pf_default, height=85, label_visibility="collapsed",
            placeholder="e.g., 'Transition all vehicles to Zero Emission Vehicles (EVs)...'")

        render_breadcrumb("Home", MODE_SINGLE_LABEL, "Step 2: Focal Comment")
        st.markdown("### Step 2 -- Enter the Focal Comment")
        st.caption(
            "Suitable inputs include consumer, citizen, patient, consultation, "
            "forum, interview, and market-actor discourse. Institutional and "
            "policy documents should be used to define the prescribed future "
            "above, not classified as consumer orientations."
        )
        st.info(INTERPRETIVE_USE_NOTE)
        st.info(NEGOTIATION_CONTEXT_NOTE)

        example_names = list(EXAMPLES.keys())
        selected_ex = st.selectbox("Or try a built-in benchmark example:", example_names)
        ex_data = EXAMPLES.get(selected_ex, EXAMPLES["Select an example"])
        if selected_ex != "Select an example":
            show_example_badge(ex_data)
            suggested_pf = ex_data.get("prescribed", "")
            if suggested_pf:
                st.info(f"Suggested prescribed future: {suggested_pf[:130]}...")
                if st.button("Use this as my prescribed future", type="secondary"):
                    st.session_state["pf_prefill"] = suggested_pf
                    st.rerun()

        input_method = st.radio("Input method:", ["Type or paste text", "Upload a .txt file"], horizontal=True)
        focal_text = ""
        if input_method == "Type or paste text":
            focal_text = st.text_area("Focal comment:", value=ex_data.get("comment", ""), height=180,
                placeholder="Paste or type the focal comment/response here...", label_visibility="collapsed")
        else:
            uploaded_file = st.file_uploader("Upload .txt file:", type=["txt"])
            if uploaded_file:
                focal_text = uploaded_file.read().decode("utf-8")
                st.success(f"Uploaded: {len(focal_text):,} characters")

        st.markdown("#### Conversational Context (optional but recommended for Negotiation)")
        is_consultation = st.checkbox(
            "This is a public-consultation / policy response (use CONSULTATION_PROMPT context labels)",
            value=ex_data.get("is_consultation", False)
        )
        context_type_options = ["NONE", "PARENT_REPLY", "THREAD_WINDOW", "ORIGINAL_POST", "CONSULTATION_PROMPT"]
        default_ctx_type = ex_data.get("context_type", "NONE")
        context_type_selected = st.selectbox(
            "Type of context provided below:", context_type_options,
            index=context_type_options.index(default_ctx_type) if default_ctx_type in context_type_options else 0
        )
        context_text = st.text_area(
            "Parent comment / nearby thread comments / original post / consultation prompt (optional):",
            value=ex_data.get("context", ""), height=100,
            placeholder="Paste the parent comment, preceding replies, original post, or consultation question here..."
        )
        if context_text.strip() and context_type_selected == "NONE":
            st.warning("You provided context text but selected context type NONE. Please select the appropriate context type above.")
        if not context_text.strip() and context_type_selected != "NONE":
            st.caption("Context type selected but no context text provided -- this will be treated as NONE.")

        if not prescribed_future.strip():
            prescribed_future = PF_EV
        final_pf_single = augment_prescribed_future(prescribed_future, it_key_single)

        effective_context_type = context_type_selected if context_text.strip() else "NONE"

        st.markdown("---")
        ready = bool(api_key and focal_text.strip())
        if not focal_text.strip():
            st.warning("Please enter a focal comment in Step 2.")
        if not api_key:
            st.warning("Please configure your OpenAI API key above.")

        if st.button("Analyze Comment", type="primary", use_container_width=True, disabled=not ready):
            with st.spinner("Analyzing with the framework's coding criteria..."):
                try:
                    result = analyze_comment(
                        final_pf_single, focal_text.strip(), context_text.strip(),
                        effective_context_type, is_consultation, api_key
                    )
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
            "Upload or paste a collection of consumer comments, consultation "
            "responses, forum posts, or social-media conversations. Each "
            "focal comment is classified in the context of the conversation "
            "or response structure in which it appears, where such structure "
            "is available."
        )
        st.info(
            "Institutional and policy documents can be used to define the "
            "prescribed future (Step 1) and, for consultations, as the "
            "consultation/policy context; they should not themselves be "
            "classified as consumer orientations."
        )

        render_breadcrumb("Home", MODE_DOC_LABEL, "Step 1: Prescribed Future")
        st.markdown("### Step 1 -- Define the Prescribed Future")
        it_key_doc = render_intervention_type_selector("doc")

        pf_doc_default = st.session_state.get("pf_doc_prefill", PF_EV)
        prescribed_future_doc = st.text_area("prescribed_future_doc", value=pf_doc_default, height=85, label_visibility="collapsed")
        preset_cols = st.columns(3)
        with preset_cols[0]:
            if st.button("Use ZEV/EV preset", type="secondary"):
                st.session_state["pf_doc_prefill"] = PF_EV; st.rerun()
        with preset_cols[1]:
            if st.button("Use NVES preset", type="secondary"):
                st.session_state["pf_doc_prefill"] = PF_NVES; st.rerun()
        with preset_cols[2]:
            if st.button("Use AI-Healthcare preset", type="secondary"):
                st.session_state["pf_doc_prefill"] = PF_AI_HEALTH; st.rerun()

        render_breadcrumb("Home", MODE_DOC_LABEL, "Step 2: Provide Comments")
        st.markdown("### Step 2 -- Provide the Comments")
        data_structure = st.radio(
            "Data structure:",
            ["Unstructured text (paste or upload .txt/.md/.pdf)",
             "Structured comments file (.csv with comment_text, and optionally thread_id / comment_id / parent_comment_id / author / timestamp)"],
            horizontal=False
        )

        raw_text = ""
        csv_df = None
        if data_structure.startswith("Structured"):
            uploaded_csv = st.file_uploader("Upload structured .csv file:", type=["csv"])
            if uploaded_csv:
                try:
                    csv_df = pd.read_csv(uploaded_csv)
                    st.success(f"Loaded {len(csv_df)} rows from '{uploaded_csv.name}'.")
                except Exception as e:
                    st.error(f"Could not read CSV: {e}")
        else:
            doc_input_method = st.radio("Input method:", ["Upload file (.txt, .md, .pdf)", "Paste text"], horizontal=True)
            if doc_input_method == "Upload file (.txt, .md, .pdf)":
                uploaded_doc = st.file_uploader("Upload document:", type=["txt", "md", "pdf"])
                if uploaded_doc:
                    if uploaded_doc.name.lower().endswith(".pdf"):
                        try:
                            from pypdf import PdfReader
                            with st.spinner("Extracting text from PDF..."):
                                reader = PdfReader(uploaded_doc)
                                raw_text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
                        except ImportError:
                            st.error("PDF support requires 'pypdf'. Add it to requirements.txt, or paste text instead.")
                    else:
                        raw_text = uploaded_doc.read().decode("utf-8", errors="ignore")
                    if raw_text:
                        st.success(f"Extracted {len(raw_text):,} characters from '{uploaded_doc.name}'")
            else:
                raw_text = st.text_area("Paste comments/responses here (one comment per paragraph, separated by a blank line):", height=250)

        records = []
        is_consultation_mode = False
        consultation_prompt_text = ""

        if csv_df is not None:
            render_breadcrumb("Home", MODE_DOC_LABEL, "Step 3: Comment Boundaries")
            st.markdown("### Step 3 -- Structured Comment Data")
            records = build_comment_records_from_csv(csv_df)
            n_with_parent = sum(1 for r in records if r.get("parent_comment_id"))
            n_threads = len(set(r["thread_id"] for r in records))
            st.info(f"Parsed {len(records)} comments across {n_threads} thread(s); {n_with_parent} comments have a recorded parent_comment_id.")
            if not records:
                st.error("Could not find a 'comment_text' column (or 'text'/'comment'). Please check your CSV headers.")

        elif raw_text.strip():
            render_breadcrumb("Home", MODE_DOC_LABEL, "Step 3: Comment Boundaries")
            st.markdown("### Step 3 -- Configure Comment Boundaries")

            id_hits = len(re.findall(r'\b\d{6,7}\s+(?:Name\s+withheld|[A-Z][a-z]+)', raw_text))
            looks_like_consultation = id_hits >= 5

            boundary_options = ["One comment per paragraph (default)", "Custom separator"]
            if looks_like_consultation:
                boundary_options.insert(0, f"Public consultation responses (auto-detected {id_hits} respondent IDs)")

            boundary_choice = st.selectbox("Comment boundary detection:", boundary_options)

            if boundary_choice.startswith("Public consultation"):
                is_consultation_mode = True
                records = build_comment_records_from_consultation(raw_text)
                consultation_prompt_text = st.text_area(
                    "Consultation question / policy proposal (used as context for every response):",
                    height=90,
                    placeholder="e.g., 'This consultation asks respondents whether the proposed New Vehicle Efficiency Standard should include additional support for regional infrastructure.'"
                )
                st.info(f"Extracted {len(records)} individual consultation responses (comments/responses), each treated as one focal response.")
            elif boundary_choice == "Custom separator":
                separator = st.text_input("Comment separator (exact string used to split comments):", value="---")
                records = build_comment_records_from_paragraphs(raw_text, separator=separator)
                st.warning(
                    "This document does not contain explicit thread/parent metadata. "
                    "Nearby comments will be used as approximate context "
                    "(THREAD_WINDOW); true reply relationships could not be "
                    "reconstructed from unstructured text."
                )
            else:
                records = build_comment_records_from_paragraphs(raw_text)
                st.warning(
                    "This document does not contain explicit thread/parent metadata. "
                    "Each blank-line-separated paragraph is treated as one comment, "
                    "and nearby comments are used as approximate context "
                    "(THREAD_WINDOW); true reply relationships could not be "
                    "reconstructed from unstructured text."
                )

            if records:
                st.info(f"{len(records)} analyzable comments detected.")
                with st.expander(f"Preview first comments (of {len(records)} total)"):
                    for rec in records[:10]:
                        st.caption(f"[{rec['comment_id']}] {rec['comment_text'][:200]}{'...' if len(rec['comment_text']) > 200 else ''}")
            else:
                st.warning("No analyzable comments found. Try a different boundary method, or paste more text.")

        total_detected = len(records)

        if total_detected > 0:
            render_breadcrumb("Home", MODE_DOC_LABEL, "Step 4: Run Analysis")
            st.markdown("### Step 4 -- Run Analysis")

            max_possible = max(1, min(total_detected, 300))
            default_val = min(30, max_possible)
            max_comments = st.slider(
                "Number of comments to analyze (evenly sampled across the full set if fewer than all are selected)",
                min_value=1, max_value=max_possible, value=default_val
            )
            est_seconds = round(max_comments / DOC_MAX_WORKERS * 2.5)
            est_cost = round(max_comments * 0.00075, 3)
            st.caption(f"Estimated time: ~{est_seconds}s | API calls: {max_comments} (parallelized, {DOC_MAX_WORKERS} at a time) | Estimated cost: ~${est_cost}")

            if max_comments >= total_detected:
                sampling_preview = "Full set of analyzable comments."
            else:
                sampling_preview = f"Evenly distributed sample of {max_comments} from {total_detected} analyzable comments."
            st.caption(f"**Sampling method:** {sampling_preview}")

            run_doc_analysis = st.button("Analyze Comments", type="primary", use_container_width=True, disabled=not api_key)
            if not api_key:
                st.warning("Please configure your OpenAI API key above.")

            if run_doc_analysis:
                final_pf_doc = augment_prescribed_future(prescribed_future_doc, it_key_doc)
                by_id, thread_order = index_threads(records)

                if max_comments >= total_detected:
                    sample_indices = list(range(total_detected))
                    sampling_description = "Full set of analyzable comments."
                else:
                    sample_indices = compute_evenly_spaced_sample_indices(total_detected, max_comments)
                    sampling_description = f"Evenly distributed sample of {len(sample_indices)} from {total_detected} analyzable comments."

                prepared_records = []
                for idx in sample_indices:
                    rec = records[idx]
                    context_text, context_type, context_available = build_context(
                        rec, by_id, thread_order, consultation_prompt_text, is_consultation_mode
                    )
                    prepared_records.append({
                        **rec,
                        "context_text": context_text, "context_type": context_type,
                        "context_available": context_available, "is_consultation": is_consultation_mode,
                    })

                progress_bar = st.progress(0, text="Starting analysis...")
                doc_results = analyze_document(prepared_records, final_pf_doc, api_key, progress_bar)
                progress_bar.empty()

                st.session_state["doc_results"] = doc_results
                st.session_state["doc_prescribed_future"] = final_pf_doc
                st.session_state["doc_intervention_type"] = it_key_doc
                st.session_state["doc_total_detected"] = total_detected
                st.session_state["doc_sampling_description"] = sampling_description

        if "doc_results" in st.session_state:
            st.divider()
            render_breadcrumb("Home", MODE_DOC_LABEL, "Step 5: Results")
            st.markdown("## Comment-Level Analysis")
            show_document_summary(
                st.session_state["doc_results"],
                st.session_state.get("doc_prescribed_future", PF_EV),
                st.session_state.get("doc_intervention_type"),
                total_detected=st.session_state.get("doc_total_detected"),
                sampling_description=st.session_state.get("doc_sampling_description", "")
            )
            if st.button("Clear results"):
                del st.session_state["doc_results"]
                st.rerun()

    # ─────────────────────────────────────────
    # ADVANCED / DEVELOPER TOOLS
    # ─────────────────────────────────────────
    st.markdown("---")
    with st.expander("Advanced / Developer Tools"):
        st.markdown("#### Coding Consistency Check")
        st.caption(
            "Agreement with built-in benchmark examples tests whether the "
            "current prompt reproduces predetermined coding decisions, "
            "including context-dependent Negotiation cases and previously "
            "observed failure patterns (decisive-action dominance for "
            "Enactment; named-address sufficiency and the future-vision "
            "test for declarative Negotiation). It does NOT constitute "
            "empirical validation, intercoder reliability, or evidence of "
            "generalizability."
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
                                st.write(f"**Secondary check [{'PASS' if r.get('secondary_match') else 'FAIL'}]:** expected {r['secondary_expected']}")
                            if r.get("negotiation_evidence_expected"):
                                st.write(f"**Negotiation evidence check [{'PASS' if r.get('negotiation_evidence_match') else 'FAIL'}]:** expected {r['negotiation_evidence_expected']}")
                            st.write("**Reported context_type:**", r.get("context_type_reported"))
                            if r.get("error"):
                                st.error(r["error"])
                else:
                    st.info("No labeled benchmark examples found.")


if __name__ == "__main__":
    main()
