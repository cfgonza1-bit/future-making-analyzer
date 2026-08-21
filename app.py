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
# SCOPE / INTERPRETIVE-USE NOTES (paper-grounded caveats only)
# ─────────────────────────────────────────
INTERPRETIVE_USE_NOTE = (
    "**Interpretive-use note.** The paper defines future-making activities as "
    "interdependent, entangled, and recursive rather than sequential, and "
    "orientations as situated ways of performing future-making rather than "
    "fixed consumer types or stable market segments. For comparability, this "
    "application assigns one dominant activity/orientation per comment plus "
    "up to two secondary classifications. This is an application-level "
    "simplification, not a claim that future-making activities or "
    "orientations are mutually exclusive. Review outputs alongside the "
    "complete comment, any available context, and relevant behavioral "
    "evidence."
)

HOMEPAGE_DESCRIPTION = f"""
Use this application to support the mapping of consumer future-making in
response to a policy or market intervention, as theorized in **"{PAPER_TITLE}."**

Upload or paste consumer comments, consultation responses, forum posts, or
social-media conversations. The application classifies each **focal
comment**, using available parent comments, nearby comments, original
posts, or consultation prompts as interpretive context, to identify how
consumers evaluate, negotiate, and enact preferred futures.

**Scope statement:**
- The framework was developed through qualitative research on Australian
  Zero Emission Vehicle (ZEV) interventions.
- The authors expect the insights may apply to other future-oriented
  intervention contexts, including AI-integrated healthcare.
- Applying the framework to AI-integrated healthcare is illustrative of
  expected transferability; it is **not** independent empirical validation.
- Intervention type (Fixed, Bounded, Flexible, or Open) depends on the
  specific scope and prescriptiveness of the intervention being analyzed,
  not on its general domain.
- Orientations (Catalyzer, Ambivalent, Resistant, Expander) are situated
  ways of performing future-making, **not** fixed consumer types or market
  segments.
- Results require interpretation alongside context and relevant behavioral
  evidence. Institutional or policy documents may be used to define the
  prescribed future or supply consultation context; they are not
  themselves classified as consumer orientations.

*Based on:* **"{PAPER_TITLE}"**
"""

# ─────────────────────────────────────────
# MODE LABELS
# ─────────────────────────────────────────
MODE_SINGLE = "single"
MODE_DOC = "document"
MODE_SINGLE_LABEL = "Analyze a Single Comment"
MODE_DOC_LABEL = "Map Orientations Across Selected Comments"

VALID_CONTEXT_TYPES = {
    "PARENT_REPLY", "THREAD_WINDOW", "ORIGINAL_POST", "CONSULTATION_PROMPT", "NONE"
}


def _clean_enum(value) -> str:
    if not value:
        return ""
    value = str(value)
    for sep in ["|", "/", " or "]:
        if sep in value:
            return value.split(sep)[0].strip()
    return value.strip()


# ─────────────────────────────────────────
# INTERVENTION TYPOLOGY (Web Appendix A) -- context only, not predictive
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
            "societal outcome. A SPECIFIC, dated mandate within this domain "
            "(e.g., all primary-care patients must use AI-supported triage "
            "by a stated date) may instead be a Bounded intervention -- "
            "classification depends on the specific intervention, not the "
            "domain."
        )
    },
}


def augment_prescribed_future(base_pf: str, it_key: str) -> str:
    """Appends the selected intervention-type classification to the
    prescribed future text so the model has this contextual information.
    This context helps interpret the prescribed future; per the paper, it
    does not predetermine which orientations, activities, or challenges
    will be found in the data."""
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
# SYSTEM PROMPT -- grounded exclusively in the Future-Making paper
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an analytical assistant supporting the mapping of consumer
future-making, grounded exclusively in the practice-theoretical framework
developed in "Futures in the Making: How Consumers Respond to
Future-Oriented Interventions," based on qualitative research on
Australian Zero Emission Vehicle (ZEV) interventions.

Use ONLY the concepts, definitions, and categories described below. Do not
introduce interaction-analysis taxonomies, discourse-analysis constructs,
sentiment-analysis categories, or any other framework not defined here.

You will always be given TWO separate fields:
  1. A FOCAL COMMENT (or FOCAL RESPONSE) -- this is the ONLY text you
     classify.
  2. CONTEXT -- a parent comment, nearby comments, the original post,
     and/or a consultation prompt, when available. Context may help you
     determine whether the focal comment is responding to, defending,
     questioning, rejecting, or contesting a preferred future. Use it ONLY
     to interpret the focal comment. NEVER classify the context itself.

====================================================================
A. SCOPE AND DEGREE OF PRESCRIPTION OF INTERVENTIONS (context only)
====================================================================

  FIXED (Narrow scope, Highly prescriptive)   -- e.g., ban on single-use plastic bags
  BOUNDED (Broad scope, Highly prescriptive)  -- e.g., ZEV policies and strategies
  FLEXIBLE (Narrow scope, Lowly prescriptive) -- e.g., Meat-free Mondays
  OPEN (Broad scope, Lowly prescriptive)      -- e.g., decentralized adoption of AI in healthcare

This typology contextualizes the prescribed future. It does NOT
predetermine which orientations, activities, or future-making challenges
will be found in a given text.

====================================================================
B. FUTURE-MAKING ACTIVITIES
====================================================================

Consumers perform future-making through three interdependent, entangled,
and recursive activities -- NOT sequential stages. What consumers
evaluate shapes how they negotiate, which in turn shapes what they enact.

--- EVALUATION ---
Consumers' cognitive assessment of the prescribed future -- how they make
sense of it, including its meaning, likelihood, desirability, benefits,
costs, risks, assumptions, and trade-offs.

--- NEGOTIATION ---
The activity through which consumers attempt to shape collective
trajectories toward a preferred future, in relation to other actors,
claims, or possible futures -- comparing, contesting, defending, or
expanding preferred futures.

--- ENACTMENT ---
What consumers do in the present to materialize a preferred future,
including reconfiguring routines, reallocating resources, acquiring
materials, or refusing to change existing practices.

DO NOT USE GRAMMATICAL SHORTCUTS:
  - Negotiation does NOT require an imperative, command, or direct call to
    action.
  - The absence of an imperative does NOT automatically mean Evaluation.
  - A named addressee is NOT automatically evidence of Negotiation.
  - Strong or negative language does NOT, by itself, determine the
    activity.
  - A statement about an alternative future must be interpreted according
    to what it is doing within the complete comment and its available
    context -- whether it is primarily assessing the prescribed future
    (Evaluation) or primarily positioning a preferred future relative to
    it or to another actor/claim (Negotiation).
  - First-person behavior is evidence of Enactment, but it should not
    automatically erase substantial Evaluation or Negotiation content
    present in the same comment. Use a secondary classification when a
    second activity is substantively and separably present.

Use the CONTEXT (when available) to judge whether the focal comment is
responding to, agreeing with, defending, questioning, rejecting, or
contesting a preferred future raised by the parent comment, nearby
comments, the original post, or the consultation prompt. In the absence
of context, judge Negotiation from what the complete focal comment itself
is doing -- positioning a preferred future in relation to the prescribed
future or to an implied alternative -- rather than from any single
grammatical marker.

Sub-types of each activity, organized by orientation (see Section C for
full orientation descriptions):

  EVALUATION performances:
    SIMPLIFY   (Catalyzer)  -- narrows focus, treats difficulties as
      temporary or already resolved
    STALL      (Ambivalent) -- careful, cautious consideration; requests
      for evidence; unresolved technical/practical conditions
    AVOID      (Resistant)  -- perceives the transition as unnecessary or
      manipulative; dismisses it
    COMPLEXIFY (Expander)   -- critically examines trade-offs and
      unintended consequences; "zooms out" to systemic considerations

  NEGOTIATION performances:
    ADVOCATE  (Catalyzer)  -- recruits others, calls for stronger policy
      signals, frames the prescribed future as a collective endeavor
    QUESTION  (Ambivalent) -- raises questions rather than outright
      objections; seeks reassurance that the transition is feasible,
      affordable, and fair before committing
    REJECT    (Resistant)  -- rejects the prescribed future and challenges
      collective attempts to bring it into being, framing it as coercive
    CONTEST   (Expander)   -- contests the scope of the prescribed future
      and seeks to broaden it, often through long-term visions of an
      alternative future

  ENACTMENT performances:
    ACCELERATE (Catalyzer)  -- materializes the prescribed future through
      present consumption decisions (e.g., purchasing, divesting)
    DELAY      (Ambivalent) -- continues current practices, waiting for
      technology/infrastructure/cost conditions to mature before adopting
    PREVENT    (Resistant)  -- entrenches current practices, explicitly
      refusing to adopt the prescribed future
    REROUTE    (Expander)   -- directs present practices away from the
      prescribed future and toward a different, broader preferred future

====================================================================
C. FUTURE-MAKING ORIENTATIONS (Table 2 of the paper)
====================================================================

--- CATALYZER ---
Main narrative: Urgency narrative -- the future is now, and the prescribed
transition is the rightfully determined future.
Goal: Accelerate change toward the prescribed future.
Emotions: Utopian optimism, enthusiasm, confidence, pride.
Temporality: The future is close -- change is happening now.
Notable conditions of adoption: High degree of alignment between current
practices and the prescribed future.

--- AMBIVALENT ---
Main narrative: Pragmatic narrative -- a set of arguments around the
practicalities of the prescribed future.
Goal: Slow down change (speed of change), delay decisions, balance risks
and benefits.
Emotions: Curiosity, caution, anxiety, frustration, optimism.
Temporality: The future is contingent -- change is uncertain.
Notable conditions of adoption: Limited resources to support change in
current practices as directed by the prescribed future.

--- RESISTANT ---
Main narrative: Control narrative -- frames interventions as coercive and
inequitable.
Goal: Contest the prescribed future, protect the status quo.
Emotions: Pessimism, anger, anxiety, fear.
Temporality: The future is distant -- there will be no change.
Notable conditions of adoption: Low degree of alignment between current
practices and the prescribed future.

--- EXPANDER ---
Main narrative: Bigger picture narrative -- "zooms out" from the
intervention and broadens the scope of change to alternative systems,
practices, and pathways.
Goal: Expand the prescribed future (magnitude of change), propose new
pathways and alternative futures.
Emotions: Dystopian optimism, hope.
Temporality: The future is distant -- change will be broader.
Notable conditions of adoption: Mismatch among current practices,
normative practices, and those directed by the prescribed future.

Determine orientation from the FULL CONFIGURATION of narrative, goal,
emotion, temporality, relationship to the prescribed future, and
implications for practice described above. Do NOT classify orientation
from sentiment, individual keywords, or tone alone.

====================================================================
D. MANDATORY ORIENTATION x ACTIVITY PERFORMANCE MATRIX
====================================================================

  CATALYZER  -> SIMPLIFY (Evaluation) | ADVOCATE (Negotiation) | ACCELERATE (Enactment)
  AMBIVALENT -> STALL (Evaluation)    | QUESTION (Negotiation) | DELAY (Enactment)
  RESISTANT  -> AVOID (Evaluation)    | REJECT (Negotiation)   | PREVENT (Enactment)
  EXPANDER   -> COMPLEXIFY (Evaluation) | CONTEST (Negotiation) | REROUTE (Enactment)

Every activity_subtype (primary and secondary) MUST belong to the row
matching its own orientation. Verify this before responding.

====================================================================
E. GROUNDING EXAMPLES (paraphrased from the manuscript's dataset)
====================================================================

Example (CATALYZER, Evaluation/Simplify) -- Whirlpool forum:
"Once EVs are cheaper to buy than ICE cars the transition will happen
fast because cost per unit for ICE will rise as sales fall... EVs can
stand on their own merits now."
-> The comment narrows focus and treats the transition as already
underway and unproblematic: EVALUATION / SIMPLIFY / CATALYZER.

Example (CATALYZER, Negotiation/Advocate) -- public consultation:
"We are already so far behind! We need to sprint to catch up. We should
be WORLD LEADERS in solar and battery manufacturing. Why are we not using
our own minerals to make batteries for EVs on a global scale??"
-> The comment recruits others and calls for stronger policy signals,
framing the prescribed future as a collective endeavor: NEGOTIATION /
ADVOCATE / CATALYZER. Note: no context is required -- the comment's own
content positions a preferred (faster) collective trajectory.

Example (CATALYZER, Enactment/Accelerate) -- Facebook group:
"Toyota is still very much trying to slow down the transition to EVs...
We have ordered two Teslas that will be delivered hopefully this year. We
are selling our Prado and it looks like we are going to sell our last
Toyota car."
-> Materializes the prescribed future through present consumption
decisions (ordering EVs, divesting from ICE vehicles): ENACTMENT /
ACCELERATE / CATALYZER.

Example (AMBIVALENT, Evaluation/Stall, WITH secondary
Enactment/Delay) -- interview:
"Living in Outback Northwest Queensland there's no charging stations at
the time... I did like the appeal of an electric vehicle... But just at
the time I went and bought a fairly decent [petrol] car... If we went on
a driving holiday, we would take our big car... So if we got an EV it
would just be our daily run around."
-> The comment's primary work is careful, cautious consideration of
material conditions (charging infrastructure): EVALUATION / STALL /
AMBIVALENT (primary). It also contains a separable, substantive
enactment -- having bought a petrol car and planning to keep the EV only
for limited "daily run around" use: ENACTMENT / DELAY / AMBIVALENT
(secondary).

Example (AMBIVALENT, Negotiation/Question) -- Facebook comment:
"Have you thought about what they are gonna do with all the batteries
once they expire because they aren't recyclable?"
-> Raises a question rather than an outright objection, seeking
reassurance before committing: NEGOTIATION / QUESTION / AMBIVALENT.

Example (AMBIVALENT, Enactment/Delay) -- Reddit:
"I plan to drive my current 10 year old hybrid as long as I can. The next
car I buy will probably be electric, but I'm expecting many of these
issues to be resolved by then."
-> Continues current practice, waiting for conditions to mature before
adopting: ENACTMENT / DELAY / AMBIVALENT.

Example (RESISTANT, Evaluation/Avoid) -- Facebook comment:
"Electric vehicles are not the solution... The current electricity
infrastructure can't keep up with the demand... I feel this is a lazy
policy just appealing to city people and is just going to result in
expensive car prices."
-> Dismisses the transition as unnecessary/manipulative: EVALUATION /
AVOID / RESISTANT.

Example (RESISTANT, Negotiation/Reject) -- YouTube comment:
"We don't need politicians and their cronies telling us what sort of car
we can have."
-> Rejects the prescribed future and challenges the legitimacy of the
authority behind it, without proposing an alternative future: NEGOTIATION
/ REJECT / RESISTANT.

Example (RESISTANT, Enactment/Prevent) -- news media comment:
"I for one WILL NOT be forced into an elec vehicle and spend half my
travel time charging the damn thing to go to hell."
-> Entrenches current practice, explicitly refusing to adopt the
prescribed future: ENACTMENT / PREVENT / RESISTANT.

Example (EXPANDER, Evaluation/Complexify, WITH secondary
Enactment/Reroute) -- interview:
"The embodied carbon in a new vehicle... is more than the emissions that
are going to be produced by the current vehicle over the course of its
lifetime until it falls apart. So that's the plan: to extract maximum
value out of that current vehicle until it is no longer functional...
I am at the moment on a waiting list for a new electric cargo bike
because my current electric cargo bike is about seven years old."
-> The comment's primary work is a critical, systemic examination of
trade-offs (embodied carbon vs. lifetime emissions): EVALUATION /
COMPLEXIFY / EXPANDER (primary). It also contains a separable, decisive
practice already under way -- driving the current vehicle into the
ground and being on a waiting list for a cargo bike: ENACTMENT / REROUTE
/ EXPANDER (secondary).

Example (EXPANDER, Negotiation/Contest, DECLARATIVE, no imperative) --
Facebook comment:
"The future is less cars, in higher density pedestrian/bike and train
orientated urban environments, where cars are a secondary transport
really only for those who really need it."
-> Contests the scope of the prescribed future and seeks to broaden it
through a long-term alternative vision, without using any imperative or
direct address: NEGOTIATION / CONTEST / EXPANDER. This illustrates that
Negotiation can be entirely declarative.

Example (EXPANDER, Enactment/Reroute) -- public consultation:
"I uprooted my life and moved from the Sunshine Coast to Melbourne with
some of my strongest reasoning being the ability to use public
transport, ride a bike around and use a car as little as possible."
-> Directs present practice away from the prescribed future and toward a
different, broader preferred future: ENACTMENT / REROUTE / EXPANDER.

====================================================================
F. PRIMARY AND SECONDARY CLASSIFICATIONS
====================================================================

Return ONE dominant classification (main_activity, activity_subtype,
main_orientation) for application comparability. This is an
application-level simplification, not a claim that future-making
activities or orientations are mutually exclusive.

Additionally, return UP TO TWO secondary classifications when the comment
substantively and separably performs a second activity, or when a second,
clearly distinguishable orientation-specific performance is present (see
grounding examples above). Do not manufacture secondary classifications
from marginal or fragmentary content.

====================================================================
G. WHAT NOT TO DO
====================================================================

Do NOT determine or output any future-making challenge (Convoluted
Evaluations, Confrontational Negotiations, or Competing Enactments) or any
Fragile Futures assessment. A single comment is one performance of
future-making; the paper defines these challenges as emergent outcomes
that arise only when differently oriented performances of the same
activity clash or interfere with one another across multiple comments.
This determination is made by the calling application across multiple
comments, never by you for a single comment.

Do NOT generate policy or managerial recommendations, instruments, or
evidence requirements. These are provided by the calling application as
static, hard-coded content from the paper and its Web Appendices.

====================================================================
OUTPUT FORMAT -- Return ONLY valid JSON
====================================================================

{
  "prescribed_future_acknowledged": "Brief restatement of the prescribed future",

  "main_activity": "EVALUATION, NEGOTIATION, or ENACTMENT",
  "activity_subtype": "SIMPLIFY, STALL, AVOID, COMPLEXIFY, ADVOCATE, QUESTION, REJECT, CONTEST, ACCELERATE, DELAY, PREVENT, REROUTE",
  "activity_rationale": "Which activity definition (Section B) applied and why, citing specific phrases",

  "main_orientation": "CATALYZER, AMBIVALENT, RESISTANT, or EXPANDER",
  "orientation_rationale": "The configuration of narrative, goal, emotion, temporality, and practice implications (Section C) that supports this orientation",

  "secondary_classifications": [
    {"activity": "...", "activity_subtype": "...", "orientation": "...", "rationale": "..."}
  ],

  "narrative_identified": "Name of the dominant narrative from Section C",
  "emotions_identified": "Comma-separated list of emotions evidenced in the comment",
  "temporality_identified": "How the comment expresses temporality, per Section C",
  "notable_conditions_of_adoption": "Which notable condition of adoption (Section C) is evidenced, if any",

  "supporting_text": "The specific phrase(s) from the FOCAL comment that support the classification",
  "context_note": "Brief note on how the supplied context (if any) helped interpret the focal comment's relation to another position, claim, or pathway -- leave empty if no context was supplied or used",
  "input_scope_warning": "Non-empty only if the input appears to mix content from multiple distinguishable speakers that cannot be cleanly separated"
}
"""

# ─────────────────────────────────────────
# ORIENTATION / ACTIVITY CONFIG (for UI + validation)
# ─────────────────────────────────────────
ORIENTATIONS = {
    "CATALYZER": {
        "color": "#27AE60", "bg": "#EAFAF1", "border": "#2ECC71",
        "goal": "Accelerate change toward the prescribed future",
        "narrative": "Urgency Narrative",
        "temporality": "The future is close -- change is happening now",
        "activities": "Simplify - Advocate - Accelerate",
        "notable_conditions": "High degree of alignment between current practices and prescribed future"
    },
    "AMBIVALENT": {
        "color": "#D68910", "bg": "#FEFDE7", "border": "#F4D03F",
        "goal": "Slow down change (speed of change), delay decisions, balance risks and benefits",
        "narrative": "Pragmatic Narrative",
        "temporality": "The future is contingent -- change is uncertain",
        "activities": "Stall - Question - Delay",
        "notable_conditions": "Limited resources to support change in current practices"
    },
    "RESISTANT": {
        "color": "#C0392B", "bg": "#FDEDEC", "border": "#E74C3C",
        "goal": "Contest the prescribed future, protect the status quo",
        "narrative": "Control Narrative",
        "temporality": "The future is distant -- there will be no change",
        "activities": "Avoid - Reject - Prevent",
        "notable_conditions": "Low degree of alignment between current practices and prescribed future"
    },
    "EXPANDER": {
        "color": "#7D3C98", "bg": "#F4ECF7", "border": "#9B59B6",
        "goal": "Expand the prescribed future (magnitude of change), propose new pathways and alternative futures",
        "narrative": "Bigger Picture Narrative",
        "temporality": "The future is distant -- change will be broader",
        "activities": "Complexify - Contest - Reroute",
        "notable_conditions": "Mismatch among current practices, normative practices, and the prescribed future"
    }
}

ACTIVITY_META = {
    "EVALUATION":  {"color": "#2980B9", "bg": "#EBF5FB",
        "definition": "Consumers' cognitive assessment of the prescribed future.",
        "subtypes": {"SIMPLIFY": "CATALYZER", "STALL": "AMBIVALENT", "AVOID": "RESISTANT", "COMPLEXIFY": "EXPANDER"}},
    "NEGOTIATION": {"color": "#E67E22", "bg": "#FEF9E7",
        "definition": "How consumers attempt to shape collective trajectories toward a preferred future.",
        "subtypes": {"ADVOCATE": "CATALYZER", "QUESTION": "AMBIVALENT", "REJECT": "RESISTANT", "CONTEST": "EXPANDER"}},
    "ENACTMENT":   {"color": "#8E44AD", "bg": "#F5EEF8",
        "definition": "What consumers do in the present to materialize a preferred future.",
        "subtypes": {"ACCELERATE": "CATALYZER", "DELAY": "AMBIVALENT", "PREVENT": "RESISTANT", "REROUTE": "EXPANDER"}},
}

# Future-making challenges (paper's exact terms) -- corpus-level only
CHALLENGE_DEFINITIONS = {
    "CONVOLUTED_EVALUATIONS": {
        "label": "Convoluted Evaluations", "activity": "EVALUATION",
        "definition": (
            "Arise from the interplay among Simplify, Stall, Avoid, and "
            "Complexify performances, supported by different and often "
            "clashing narratives and emotions."
        )
    },
    "CONFRONTATIONAL_NEGOTIATIONS": {
        "label": "Confrontational Negotiations", "activity": "NEGOTIATION",
        "definition": (
            "Arise when consumers Advocate, Question, Reject, and Contest "
            "preferred futures without conceding to alternative ones."
        )
    },
    "COMPETING_ENACTMENTS": {
        "label": "Competing Enactments", "activity": "ENACTMENT",
        "definition": (
            "Arise when consumers Accelerate, Delay, Prevent, and Reroute "
            "different preferred futures through their current practices."
        )
    },
}
FRAGILE_FUTURES_DEFINITION = (
    "Fragile Futures: multiple, volatile, and conflicting preferred futures "
    "that may interfere with the actualization of the prescribed one."
)

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
# STATIC ROADMAPS (verbatim step names from the manuscript) -- never
# generated by the LLM.
# ─────────────────────────────────────────
POLICY_ROADMAP_STEPS = [
    ("1", "Determine the prescribed future",
     "Define the future the intervention prescribes, the practice changes on which its "
     "public value depends, and which populations may lack the resources to enact it."),
    ("2", "Map future-making orientations",
     "Triangulate discourse with behavior; analyze by application/decision context."),
    ("3", "Diagnose key future-making challenges",
     "Identify which of Convoluted Evaluations, Confrontational Negotiations, or "
     "Competing Enactments is most pressing; the three activities are interdependent, "
     "not sequential."),
    ("4", "Implement support initiatives",
     "Match support measures to future-making orientations."),
    ("5", "Facilitate enactment",
     "Provide the infrastructure and capabilities required to reconfigure practices "
     "safely and equitably."),
    ("6", "Measure multiple outcomes",
     "Measure how the intervention is progressing across multiple outcomes."),
    ("7", "Revise the intervention",
     "Continuously revise the intervention, providing more support as needed."),
]

MANAGER_ROADMAP_STEPS = [
    ("1", "Determine the prescribed future",
     "Define the intervention through the future it asks consumers to enact."),
    ("2", "Consider future-making orientations",
     "Treat orientations as a diagnostic lens, not fixed consumer segments."),
    ("3", "Monitor key future-making challenges",
     "Build a future-making customer journey combining discursive, experiential, "
     "and behavioral evidence."),
    ("4", "Select an orientation-sensitive response",
     "Match responses to the orientations identified in the data."),
    ("5", "Match messaging to key future-making challenges",
     "Communicate achievements alongside uncertainty, trade-offs, and limitations."),
    ("6", "Support consumers through enactment",
     "Place support at touchpoints where practices change."),
]

# Static, hard-coded reference content from Web Appendix E (never generated
# by the LLM; shown only as static reference material, not as
# analysis-specific recommendations).
WEB_APPENDIX_E_POLICY_REFERENCE = {
    "CATALYZER": "Time-limited sandboxes, independent evaluation, mandatory failure reporting, predefined thresholds for expansion/withdrawal.",
    "AMBIVALENT": "Impact assessments, staged authorization, sunset clauses, public registers, guaranteed alternative pathways.",
    "RESISTANT": "Protect human-review and appeal rights, prohibit unacceptable uses, independent audits, moratoria where evidence is insufficient.",
    "EXPANDER": "Deliberative forums, broader impact assessment, fund complementary pathways, citizen assemblies, data trusts, alternative governance models.",
}
WEB_APPENDIX_E_MANAGER_REFERENCE = {
    "CATALYZER": "Governed pilots, peer learning, documentation, limitation reporting. Avoid inevitability claims and treating early adopters as representative.",
    "AMBIVALENT": "Comparison tools, staged adoption, transparent evidence, training, human assistance. Avoid artificial urgency and framing hesitation as ignorance.",
    "RESISTANT": "Consultation, opt-outs, human review, audits, appeals, harm protections. Avoid 'there is no alternative' messaging, ridicule, hidden automation.",
    "EXPANDER": "Participatory design, futures workshops, broader-impact evaluation, partnerships, alternative governance/service models. Avoid presenting the offering as complete or dismissing critique.",
}
CROSS_ORIENTATION_NOTE = (
    "Cross-orientation interference check (paper's managerial roadmap, Step 4): "
    "check whether a response tailored to one orientation intensifies fragility "
    "elsewhere."
)

# ─────────────────────────────────────────
# BENCHMARK EXAMPLES -- paraphrased directly from the manuscript's dataset,
# used only for the internal Coding Consistency Check.
# ─────────────────────────────────────────
EXAMPLES = {
    "Select an example": {
        "prescribed": "", "comment": "", "context": "", "context_type": "NONE",
        "is_consultation": False, "activity": "", "subtype": "", "orientation": "",
        "secondary_expected": None
    },
    "CATALYZER | Evaluation -> Simplify (Alfonso, W)": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "SIMPLIFY", "orientation": "CATALYZER",
        "context": "", "context_type": "NONE", "is_consultation": False, "secondary_expected": None,
        "comment": (
            "Once EVs are cheaper to buy than ICE cars the transition will happen "
            "fast because cost per unit for ICE will rise as sales fall. EVs can "
            "stand on their own merits now."
        )
    },
    "CATALYZER | Negotiation -> Advocate (Joe, PC)": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "ADVOCATE", "orientation": "CATALYZER",
        "context": "", "context_type": "NONE", "is_consultation": False, "secondary_expected": None,
        "comment": (
            "We are already so far behind! We need to sprint to catch up. We "
            "should be WORLD LEADERS in solar and battery manufacturing. Why are "
            "we not using our own minerals to make batteries for EVs on a global "
            "scale??"
        )
    },
    "CATALYZER | Enactment -> Accelerate (Johnny, F)": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "ACCELERATE", "orientation": "CATALYZER",
        "context": "", "context_type": "NONE", "is_consultation": False, "secondary_expected": None,
        "comment": (
            "Toyota is still very much trying to slow down the transition to EVs. "
            "We have ordered two Teslas that will be delivered hopefully this "
            "year. We are selling our Prado and it looks like we are going to "
            "sell our last Toyota car."
        )
    },
    "AMBIVALENT | Evaluation -> Stall, + secondary Enactment/Delay (Clara, I)": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "STALL", "orientation": "AMBIVALENT",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": ("AMBIVALENT", "ENACTMENT", "DELAY"),
        "comment": (
            "Living in Outback Northwest Queensland there's no charging stations "
            "at the time. I did like the appeal of an electric vehicle mainly "
            "because you don't have to put fuel in it, which is great. But just "
            "at the time I went and bought a fairly decent car for five and a "
            "half grand. If we went on a driving holiday, we would take our big "
            "car. So if we got an EV it would just be our daily run around."
        )
    },
    "AMBIVALENT | Negotiation -> Question (Martin, F)": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "QUESTION", "orientation": "AMBIVALENT",
        "context": "", "context_type": "NONE", "is_consultation": False, "secondary_expected": None,
        "comment": (
            "Have you thought about what they are gonna do with all the "
            "batteries once they expire because they aren't recyclable?"
        )
    },
    "AMBIVALENT | Enactment -> Delay (Ruen, R)": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "DELAY", "orientation": "AMBIVALENT",
        "context": "", "context_type": "NONE", "is_consultation": False, "secondary_expected": None,
        "comment": (
            "I plan to drive my current 10 year old hybrid as long as I can. The "
            "next car I buy will probably be electric, but I'm expecting many of "
            "these issues to be resolved by then."
        )
    },
    "RESISTANT | Evaluation -> Avoid (Esther, F)": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "AVOID", "orientation": "RESISTANT",
        "context": "", "context_type": "NONE", "is_consultation": False, "secondary_expected": None,
        "comment": (
            "Electric vehicles are not the solution. The current electricity "
            "infrastructure can't keep up with the demand now. I feel this is a "
            "lazy policy just appealing to city people and is just going to "
            "result in expensive car prices."
        )
    },
    "RESISTANT | Negotiation -> Reject (Raj, YT)": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "REJECT", "orientation": "RESISTANT",
        "context": "", "context_type": "NONE", "is_consultation": False, "secondary_expected": None,
        "comment": "We don't need politicians and their cronies telling us what sort of car we can have."
    },
    "RESISTANT | Enactment -> Prevent (StarT, NM)": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "PREVENT", "orientation": "RESISTANT",
        "context": "", "context_type": "NONE", "is_consultation": False, "secondary_expected": None,
        "comment": "I for one WILL NOT be forced into an elec vehicle and spend half my travel time charging the damn thing to go to hell."
    },
    "EXPANDER | Evaluation -> Complexify, + secondary Enactment/Reroute (Peter, I)": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "COMPLEXIFY", "orientation": "EXPANDER",
        "context": "", "context_type": "NONE", "is_consultation": False,
        "secondary_expected": ("EXPANDER", "ENACTMENT", "REROUTE"),
        "comment": (
            "The embodied carbon in a new vehicle is more than the emissions "
            "that are going to be produced by the current vehicle over the "
            "course of its lifetime until it falls apart. So that's the plan: "
            "to extract maximum value out of that current vehicle until it is "
            "no longer functional. I am at the moment on a waiting list for a "
            "new electric cargo bike because my current electric cargo bike is "
            "about seven years old."
        )
    },
    "EXPANDER | Negotiation -> Contest, declarative, no imperative (Dan, F)": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "CONTEST", "orientation": "EXPANDER",
        "context": "", "context_type": "NONE", "is_consultation": False, "secondary_expected": None,
        "comment": (
            "The future is less cars, in higher density pedestrian/bike and "
            "train orientated urban environments, where cars are a secondary "
            "transport really only for those who really need it."
        )
    },
    "EXPANDER | Enactment -> Reroute (Phillip, PC)": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "REROUTE", "orientation": "EXPANDER",
        "context": "", "context_type": "NONE", "is_consultation": False, "secondary_expected": None,
        "comment": (
            "I uprooted my life and moved from the Sunshine Coast to Melbourne "
            "with some of my strongest reasoning being the ability to use "
            "public transport, ride a bike around and use a car as little as "
            "possible."
        )
    },
}

# ─────────────────────────────────────────
# CONSISTENCY SAFEGUARD -- enforce the mandatory orientation x subtype
# pairing table for primary and secondary classifications
# ─────────────────────────────────────────

def get_secondary_classifications(result: dict) -> list:
    sec = result.get("secondary_classifications")
    if not sec:
        return []
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


def enforce_context_metadata(result: dict, context_available: bool, context_type: str) -> dict:
    """context_used and context_type are determined deterministically by
    the calling application (based on what context text was actually
    supplied), not trusted from the model, to avoid inconsistent
    self-reporting."""
    result["context_used"] = bool(context_available)
    result["context_type"] = context_type if context_type in VALID_CONTEXT_TYPES else "NONE"
    if not context_available:
        result["context_note"] = result.get("context_note", "") if result.get("context_note") else ""
    return result


# ─────────────────────────────────────────
# CORE FUNCTION -- focal comment + context, paper-grounded schema only
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
        context_label = "CONTEXT (parent comment / nearby comments / original post) -- USE FOR INTERPRETATION BUT DO NOT CLASSIFY"

    context_available = bool(context_text and context_text.strip())
    context_block = context_text.strip() if context_available else "No context is available for this comment."

    user_message = f"""
PRESCRIBED FUTURE:
{prescribed_future}

{focal_label}:
{focal_text}

{context_label}:
{context_block}

Classify ONLY the focal comment/response above, using the definitions in
Sections B-D. Apply no grammatical shortcuts. Verify every
activity_subtype (primary and secondary) belongs to the valid pairing row
for its own orientation (Section D) before responding. Do not produce any
future-making challenge or Fragile Futures assessment, and do not produce
any policy or managerial recommendation -- these are outside your task.
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
    parsed = enforce_context_metadata(parsed, context_available, context_type)
    return parsed


def run_consistency_suite(api_key: str) -> dict:
    """Tests whether the current prompt reproduces predetermined coding
    decisions for benchmark examples paraphrased from the manuscript. This
    is an internal consistency check -- it does NOT constitute empirical
    validation, intercoder reliability, or evidence of generalizability."""
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
                "secondary_expected": ex.get("secondary_expected"), "secondary_match": None
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

        results.append({
            "example": name,
            "expected": (ex["orientation"], ex["activity"], ex["subtype"]),
            "predicted": (pred_orientation, pred_activity, pred_subtype),
            "match": match,
            "secondary_expected": sec_expected, "secondary_match": secondary_match
        })
    if not results:
        return {"results": [], "overall_agreement": 0.0}
    agreement = sum(r["match"] for r in results) / len(results)
    return {"results": results, "overall_agreement": agreement}


# ─────────────────────────────────────────
# COMMENT / THREAD DATA STRUCTURES (technical infrastructure, no theory)
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
    """Builds context in priority order: (1) parent comment, (2) up to two
    preceding comments from the same thread, (3) one following reply that
    directly responds to the focal comment, (4) the original post or
    consultation prompt. Never uses comments from unrelated threads."""
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
# CORPUS-LEVEL AGGREGATION -- paper-grounded challenge review only
# ─────────────────────────────────────────

def compute_dominant_distributions(results: list) -> dict:
    valid = [r for r in results if r and "_error" not in r]
    orientation_counts, activity_counts, subtype_counts = {}, {}, {}
    for r in valid:
        ori = _clean_enum(r.get("main_orientation", "")).upper()
        act = _clean_enum(r.get("main_activity", "")).upper()
        sub = _clean_enum(r.get("activity_subtype", "")).upper()
        if ori:
            orientation_counts[ori] = orientation_counts.get(ori, 0) + 1
        if act:
            activity_counts[act] = activity_counts.get(act, 0) + 1
        if act and sub:
            key = f"{act} / {sub}"
            subtype_counts[key] = subtype_counts.get(key, 0) + 1
    return {
        "n_analyzed": len(valid),
        "orientation_counts": orientation_counts,
        "activity_counts": activity_counts,
        "subtype_counts": subtype_counts,
    }


def compute_challenge_review_candidates(results: list) -> dict:
    """Identifies linked parent-reply comments performing DIFFERENT
    orientation-specific performances of the SAME activity. These are
    flagged as comments requiring interpretive review for the
    corresponding future-making challenge -- never auto-diagnosed as an
    occurred challenge, never scored, never converted into a percentage or
    a Fragile Futures assessment."""
    valid = [r for r in results if r and "_error" not in r]
    by_id = {r.get("_comment_id"): r for r in valid if r.get("_comment_id")}
    candidates = {k: [] for k in CHALLENGE_DEFINITIONS}
    for r in valid:
        parent_id = r.get("_parent_comment_id")
        if not parent_id or parent_id not in by_id:
            continue
        parent = by_id[parent_id]
        act_r = _clean_enum(r.get("main_activity", "")).upper()
        act_p = _clean_enum(parent.get("main_activity", "")).upper()
        if act_r != act_p:
            continue
        ori_r = _clean_enum(r.get("main_orientation", "")).upper()
        ori_p = _clean_enum(parent.get("main_orientation", "")).upper()
        sub_r = _clean_enum(r.get("activity_subtype", "")).upper()
        sub_p = _clean_enum(parent.get("activity_subtype", "")).upper()
        if ori_r == ori_p and sub_r == sub_p:
            continue  # same performance -- not a candidate for review
        challenge_key = next((k for k, v in CHALLENGE_DEFINITIONS.items() if v["activity"] == act_r), None)
        if challenge_key:
            candidates[challenge_key].append({"parent": parent, "reply": r})
    return candidates


def build_linked_pair_table(results: list) -> pd.DataFrame:
    """Purely descriptive table of linked parent-reply comments and their
    classifications -- no interaction type or theoretical-contrast label
    is attached."""
    valid = [r for r in results if r and "_error" not in r]
    by_id = {r.get("_comment_id"): r for r in valid if r.get("_comment_id")}
    rows = []
    for r in valid:
        parent_id = r.get("_parent_comment_id")
        if not parent_id or parent_id not in by_id:
            continue
        parent = by_id[parent_id]
        rows.append({
            "parent_comment_id": parent.get("_comment_id", ""),
            "parent_orientation": _clean_enum(parent.get("main_orientation", "")).upper(),
            "parent_activity": _clean_enum(parent.get("main_activity", "")).upper(),
            "parent_subtype": _clean_enum(parent.get("activity_subtype", "")).upper(),
            "reply_comment_id": r.get("_comment_id", ""),
            "reply_orientation": _clean_enum(r.get("main_orientation", "")).upper(),
            "reply_activity": _clean_enum(r.get("main_activity", "")).upper(),
            "reply_subtype": _clean_enum(r.get("activity_subtype", "")).upper(),
        })
    return pd.DataFrame(rows)


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
                "main_orientation": "ERROR", "main_activity": "", "activity_subtype": "",
                "secondary_classifications": "", "activity_rationale": "",
                "orientation_rationale": "", "supporting_text": "",
                "context_used": "", "context_type": "", "input_scope_warning": "",
                "error": r.get("_error", "")
            })
            rows.append(base)
            continue
        secondary = get_secondary_classifications(r)
        sec_str = " || ".join(
            f"{s.get('orientation','')}/{s.get('activity','')}/{s.get('activity_subtype','')}: {s.get('rationale','')}"
            for s in secondary
        )
        base.update({
            "main_orientation": _clean_enum(r.get("main_orientation", "")).upper(),
            "main_activity": _clean_enum(r.get("main_activity", "")).upper(),
            "activity_subtype": _clean_enum(r.get("activity_subtype", "")).upper(),
            "secondary_classifications": sec_str,
            "activity_rationale": r.get("activity_rationale", ""),
            "orientation_rationale": r.get("orientation_rationale", ""),
            "supporting_text": r.get("supporting_text", ""),
            "context_used": r.get("context_used", ""),
            "context_type": r.get("context_type", ""),
            "input_scope_warning": r.get("input_scope_warning", "") or "",
            "error": ""
        })
        rows.append(base)
    return pd.DataFrame(rows)


def render_pct_bars(counts: dict, meta_dict: dict, total: int):
    if total == 0:
        st.caption("No data to display.")
        return
    for key, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        pct_val = round(cnt / total * 100, 1)
        meta = meta_dict.get(key, {})
        color = meta.get("color", "#888")
        st.markdown(f"""
        <div style="margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:3px;">
                <span><strong>{key}</strong></span>
                <span style="color:#666;">{cnt} comments ({pct_val}%)</span>
            </div>
            <div style="background:#eee;border-radius:6px;height:14px;width:100%;overflow:hidden;">
                <div style="background:{color};width:{pct_val}%;height:14px;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def show_document_summary(results: list, prescribed_future: str,
                           total_detected: int = None, sampling_description: str = ""):
    dist = compute_dominant_distributions(results)
    n = dist["n_analyzed"]
    n_errors = len([r for r in results if r and "_error" in r])

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
    if n_errors:
        st.warning(f"{n_errors} comment(s) failed to analyze and were excluded.")

    n_with_context = sum(1 for r in results if r and "_error" not in r and r.get("context_used"))
    n_without_context = n - n_with_context

    st.markdown("### Comments Analyzed")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total comments detected", total_detected if total_detected is not None else n)
    c2.metric("Comments analyzed", n)
    c3.metric("With available context", n_with_context)
    c4.metric("Without context", n_without_context)
    st.caption(
        "These percentages and counts describe the analyzed comments only. "
        "They do not represent unique consumers, organizations, or "
        "population prevalence, and results depend on the source material, "
        "segmentation, and selected sample."
    )

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### Dominant-Orientation Distribution Among Analyzed Comments")
        render_pct_bars(dist["orientation_counts"], ORIENTATIONS, n)
    with col2:
        st.markdown("#### Dominant-Activity Distribution Among Analyzed Comments")
        render_pct_bars(dist["activity_counts"], ACTIVITY_META, n)
    with col3:
        st.markdown("#### Activity-Performance (Subtype) Distribution")
        for key, cnt in sorted(dist["subtype_counts"].items(), key=lambda x: -x[1]):
            pct_val = round(cnt / n * 100, 1)
            st.markdown(f"- **{key}**: {cnt} ({pct_val}%)")

    st.markdown("---")
    st.markdown("## Comments to Review for Emergent Future-Making Challenges")
    st.caption(
        "The paper defines these challenges as emergent outcomes arising "
        "when consumers perform the SAME activity differently across "
        "orientations. The lists below flag linked comments as candidates "
        "for interpretive review. They do NOT constitute an automatic "
        "diagnosis that a challenge occurred, a percentage of affected "
        "comments, or a Fragile Futures score."
    )
    candidates = compute_challenge_review_candidates(results)
    has_links = any(len(v) > 0 for v in candidates.values())

    if has_links:
        for key, meta in CHALLENGE_DEFINITIONS.items():
            pairs = candidates[key]
            with st.expander(f"{meta['label']} -- {len(pairs)} linked comment pair(s) to review"):
                st.caption(meta["definition"])
                if not pairs:
                    st.caption("No linked comment pairs identified for this challenge in this sample.")
                for p in pairs:
                    parent, reply = p["parent"], p["reply"]
                    st.markdown(
                        f"**Parent** [{parent.get('_comment_id','')}] -- "
                        f"{parent.get('main_orientation','')} / {parent.get('main_activity','')} / "
                        f"{parent.get('activity_subtype','')}"
                    )
                    st.caption(parent.get("_comment_text", "")[:300])
                    st.markdown(
                        f"**Reply** [{reply.get('_comment_id','')}] -- "
                        f"{reply.get('main_orientation','')} / {reply.get('main_activity','')} / "
                        f"{reply.get('activity_subtype','')}"
                    )
                    st.caption(reply.get("_comment_text", "")[:300])
                    st.markdown("---")
        st.markdown("#### Linked Parent-Reply Comments (descriptive table)")
        pair_df = build_linked_pair_table(results)
        if not pair_df.empty:
            st.dataframe(pair_df, use_container_width=True, height=250)
    else:
        st.info(
            "No parent-reply links were available among the analyzed comments "
            "(structured thread/parent metadata may be unavailable for this "
            "corpus). The activity-performance distribution above shows the "
            "diversity of performances present, but co-occurrence in a "
            "corpus without linked exchanges does not demonstrate "
            "interaction, clash, interference, or Fragile Futures. No "
            "fictitious exchanges have been reconstructed."
        )

    st.caption(f"*{FRAGILE_FUTURES_DEFINITION}*")

    st.markdown("---")
    st.markdown("### Comment-Level Detail")
    df = build_results_dataframe(results)
    display_cols = ["comment_index", "comment_id", "parent_comment_id", "main_orientation",
                     "main_activity", "activity_subtype", "context_type"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols] if display_cols else df, use_container_width=True, height=350)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download full results as CSV",
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
        show_results(chosen_result, prescribed_future, show_interpretive_note=False, corpus_mode=True)
    else:
        st.caption("No valid comments available to explore.")

    st.markdown("---")
    render_static_roadmaps(mode="corpus")


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


def render_static_roadmaps(mode: str = "single"):
    st.markdown("## Roadmap Reference (static, from the paper)")
    if mode == "single":
        st.caption(
            "This application, for a single comment, primarily supports "
            "mapping future-making orientations and activities (roadmap "
            "step 1-2 for both policymakers and managerial practitioners). "
            "It does not generate later-step actions from one comment."
        )
    else:
        st.caption(
            "This application supports mapping orientations and organizing "
            "comments for human review of possible future-making challenges "
            "(roadmap steps 1-3). It does not claim to complete the later "
            "roadmap steps."
        )
    policy_tab, manager_tab = st.tabs(["Policymaking Roadmap", "Managerial Roadmap"])
    with policy_tab:
        for num, title, desc in POLICY_ROADMAP_STEPS:
            st.markdown(f"**Step {num}: {title}**")
            st.caption(desc)
        with st.expander("Web Appendix E reference -- orientation-sensitive support directions (static, not generated for this analysis)"):
            for ori, text in WEB_APPENDIX_E_POLICY_REFERENCE.items():
                st.markdown(f"**{ori}:** {text}")
    with manager_tab:
        for num, title, desc in MANAGER_ROADMAP_STEPS:
            st.markdown(f"**Step {num}: {title}**")
            st.caption(desc)
        with st.expander("Web Appendix E reference -- orientation-sensitive support directions (static, not generated for this analysis)"):
            for ori, text in WEB_APPENDIX_E_MANAGER_REFERENCE.items():
                st.markdown(f"**{ori}:** {text}")
        st.caption(CROSS_ORIENTATION_NOTE)


def show_results(result: dict, prescribed_future: str, show_interpretive_note: bool = True,
                  corpus_mode: bool = False):
    orientation = _clean_enum(result.get("main_orientation", "")).upper().strip()
    main_act    = _clean_enum(result.get("main_activity", "")).upper().strip()
    act_sub     = _clean_enum(result.get("activity_subtype", "N/A")).upper().strip()
    secondary = get_secondary_classifications(result)

    if show_interpretive_note:
        st.info(INTERPRETIVE_USE_NOTE)

    st.markdown(f"""
    <div style="background:#EBF5FB;border-left:5px solid #2980B9;border-radius:8px;padding:12px 18px;margin-bottom:16px;">
        <strong style="color:#2980B9;">Prescribed Future Analyzed:</strong><br>
        <em style="color:#333;">{prescribed_future}</em>
    </div>
    """, unsafe_allow_html=True)

    warning_text = result.get("input_scope_warning", "") or ""
    if warning_text:
        st.warning(f"Input-scope note: {warning_text}")
    if result.get("_consistency_note"):
        st.caption(f"Note: {result['_consistency_note']}")

    ctx_type = result.get("context_type", "NONE")
    ctx_used = result.get("context_used", False)
    st.caption(
        f"**Technical note -- context used for interpretation:** {ctx_type}"
        + (" (no context was available for this comment)" if not ctx_used else "")
    )
    if result.get("context_note"):
        st.caption(f"**Context note:** {result.get('context_note')}")

    col1, col2 = st.columns(2)
    with col1:
        cfg = ORIENTATIONS.get(orientation, {})
        st.markdown(f"""
        <div style="background:{cfg.get('bg','#f5f5f5')};border-left:6px solid {cfg.get('border','#999')};border-radius:10px;padding:16px 18px;min-height:210px;">
            <h3 style="color:{cfg.get('color','#555')};margin:0;font-size:22px;">{orientation}</h3>
            <p style="color:#777;margin:6px 0 2px;font-size:11px;">{cfg.get('narrative','')}</p>
            <p style="color:#777;margin:2px 0;font-size:11px;">{cfg.get('temporality','')}</p>
            <p style="color:#777;margin:2px 0;font-size:11px;">{cfg.get('goal','')}</p>
            <p style="color:#999;margin:6px 0 0;font-size:10px;">Dominant orientation (application-level simplification)</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        ameta = ACTIVITY_META.get(main_act, {})
        st.markdown(f"""
        <div style="background:{ameta.get('bg','#f5f5f5')};border-left:6px solid {ameta.get('color','#555')};border-radius:10px;padding:16px 18px;min-height:210px;">
            <h3 style="color:{ameta.get('color','#555')};margin:0;font-size:20px;">{main_act}</h3>
            <p style="color:#555;margin:4px 0 3px;font-size:12px;"><strong>Dominant Future-Making Activity</strong></p>
            <span style="background:#f0f0f0;border:1.5px solid #bbb;color:#444;border-radius:12px;padding:3px 10px;font-weight:bold;font-size:12px;">-> {act_sub}</span>
            <p style="color:#777;margin:8px 0 0;font-size:11px;font-style:italic;">{ameta.get('definition','')}</p>
        </div>
        """, unsafe_allow_html=True)

    if secondary:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Secondary Classification(s)")
        st.caption(
            "Future-making activities are interdependent and recursive; "
            "orientations may be combined. These are additional, "
            "substantively supported classifications, not discarded content."
        )
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
    tab_ori, tab_act = st.tabs(["Orientation Rationale", "Activity Rationale"])
    with tab_ori:
        st.write(result.get("orientation_rationale", "--"))
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown("**Narrative**"); c1.caption(result.get("narrative_identified", "--"))
        c2.markdown("**Emotions**"); c2.caption(result.get("emotions_identified", "--"))
        c3.markdown("**Temporality**"); c3.caption(result.get("temporality_identified", "--"))
        c4.markdown("**Notable Conditions**"); c4.caption(result.get("notable_conditions_of_adoption", "--"))
    with tab_act:
        st.write(result.get("activity_rationale", "--"))
        st.markdown("**Supporting text (from the focal comment):**")
        st.info(result.get("supporting_text", "--"))
        for act_name, meta in ACTIVITY_META.items():
            is_main = (act_name == main_act)
            border = f"3px solid {meta['color']}" if is_main else "1px solid #ddd"
            st.markdown(f"""
            <div style="border:{border};border-radius:8px;padding:10px 14px;margin-bottom:8px;background:{'#fff' if is_main else '#fafafa'};">
                <strong style="color:{meta['color']};">{act_name}</strong>
                {'<span style="background:#27AE60;color:white;border-radius:8px;padding:1px 8px;font-size:11px;margin-left:8px;">DOMINANT</span>' if is_main else ''}<br>
                <span style="font-size:11px;color:#555;">{meta['definition']}</span>
            </div>
            """, unsafe_allow_html=True)

    if not corpus_mode:
        st.markdown("---")
        render_static_roadmaps(mode="single")
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
        "intervention is (Web Appendix A). This context helps interpret "
        "the prescribed future; it does not predetermine which "
        "orientations, activities, or future-making challenges will "
        "appear in the data."
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

        example_names = list(EXAMPLES.keys())
        selected_ex = st.selectbox("Or try a built-in benchmark example (paraphrased from the manuscript):", example_names)
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

        st.markdown("#### Context (optional)")
        st.caption(
            "Provide a parent comment, nearby comments, an original post, or "
            "a consultation prompt if available. Context may help determine "
            "whether the focal comment is responding to, defending, "
            "questioning, rejecting, or contesting a preferred future."
        )
        is_consultation = st.checkbox(
            "This is a public-consultation / policy response (use CONSULTATION_PROMPT context label)",
            value=ex_data.get("is_consultation", False)
        )
        context_type_options = ["NONE", "PARENT_REPLY", "THREAD_WINDOW", "ORIGINAL_POST", "CONSULTATION_PROMPT"]
        default_ctx_type = ex_data.get("context_type", "NONE")
        context_type_selected = st.selectbox(
            "Type of context provided below (technical metadata):", context_type_options,
            index=context_type_options.index(default_ctx_type) if default_ctx_type in context_type_options else 0
        )
        context_text = st.text_area(
            "Parent comment / nearby comments / original post / consultation prompt (optional):",
            value=ex_data.get("context", ""), height=100,
            placeholder="Paste the parent comment, preceding replies, original post, or consultation question here..."
        )
        if context_text.strip() and context_type_selected == "NONE":
            st.warning("You provided context text but selected context type NONE. Please select the appropriate context type above.")

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
            with st.spinner("Analyzing with the framework's definitions..."):
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
                st.info(f"Extracted {len(records)} individual consultation responses, each treated as one focal response.")
            elif boundary_choice == "Custom separator":
                separator = st.text_input("Comment separator (exact string used to split comments):", value="---")
                records = build_comment_records_from_paragraphs(raw_text, separator=separator)
                st.warning(
                    "This document does not contain explicit thread/parent metadata. "
                    "Nearby comments will be used as approximate context; true reply "
                    "relationships could not be reconstructed from unstructured text."
                )
            else:
                records = build_comment_records_from_paragraphs(raw_text)
                st.warning(
                    "This document does not contain explicit thread/parent metadata. "
                    "Each blank-line-separated paragraph is treated as one comment, "
                    "and nearby comments are used as approximate context; true reply "
                    "relationships could not be reconstructed from unstructured text."
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
                st.session_state["doc_total_detected"] = total_detected
                st.session_state["doc_sampling_description"] = sampling_description

        if "doc_results" in st.session_state:
            st.divider()
            render_breadcrumb("Home", MODE_DOC_LABEL, "Step 5: Results")
            st.markdown("## Comment-Level Analysis")
            show_document_summary(
                st.session_state["doc_results"],
                st.session_state.get("doc_prescribed_future", PF_EV),
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
            "Agreement with built-in benchmark examples (paraphrased from "
            "the manuscript's dataset) tests whether the current prompt "
            "reproduces predetermined coding decisions for activity, "
            "activity performance/subtype, orientation, and substantively "
            "supported secondary classifications. It does NOT constitute "
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
                            st.write("**Expected (dominant):**", r["expected"])
                            st.write("**Predicted (dominant):**", r["predicted"])
                            if r.get("secondary_expected"):
                                st.write(f"**Secondary check [{'PASS' if r.get('secondary_match') else 'FAIL'}]:** expected {r['secondary_expected']}")
                            if r.get("error"):
                                st.error(r["error"])
                else:
                    st.info("No labeled benchmark examples found.")


if __name__ == "__main__":
    main()
