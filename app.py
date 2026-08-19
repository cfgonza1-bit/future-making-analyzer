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
    page_title="Future-Making Orientation Analyzer",
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
# MODE LABELS
# ─────────────────────────────────────────
MODE_SINGLE = "single"
MODE_DOC = "document"
MODE_SINGLE_LABEL = "Analyze a Single Comment"
MODE_DOC_LABEL = "Map Orientations Across a Document"

# ─────────────────────────────────────────
# DETERMINISTIC ACTIVITY -> CHALLENGE MAPPING
# ─────────────────────────────────────────
ACTIVITY_TO_CHALLENGE = {
    "EVALUATION":  "CONVOLUTED_EVALUATIONS",
    "NEGOTIATION": "CONFRONTATIONAL_NEGOTIATIONS",
    "ENACTMENT":   "COMPETING_ENACTMENTS",
}


def _clean_enum(value: str) -> str:
    if not value:
        return value
    for sep in ["|", "/", " or "]:
        if sep in value:
            return value.split(sep)[0].strip()
    return value.strip()


def derive_potential_challenge(main_activity: str) -> str:
    act = _clean_enum(main_activity).upper() if main_activity else ""
    return ACTIVITY_TO_CHALLENGE.get(act, "N/A")


# ─────────────────────────────────────────
# SCOPE AND DEGREE OF PRESCRIPTION OF INTERVENTIONS (context typology)
# ─────────────────────────────────────────
INTERVENTION_TYPES = {
    "Fixed Intervention (Narrow scope, Highly prescriptive)": {
        "scope": "Narrow", "prescriptiveness": "Highly",
        "example": "Ban on single-use plastic bags (Gonzalez-Arcos et al. 2021)",
        "note": (
            "Predominantly initiated by governmental policies or laws with clear "
            "targets and strong regulatory specification. Requires consumers to "
            "change one or a few interconnected practices. Expect fast, visible "
            "Negotiation and Enactment; monitor closely for Resistant/Reject and "
            "Resistant/Prevent responses aimed directly at the mandate itself."
        )
    },
    "Bounded Intervention (Broad scope, Highly prescriptive)": {
        "scope": "Broad", "prescriptiveness": "Highly",
        "example": "ZEV policies and strategies (Holtsmark and Skonhoft 2014)",
        "note": (
            "Highly prescriptive and predominantly initiated by governmental "
            "targets, followed by incentives, penalties, and firm strategies that "
            "move consumers and market actors across a wide range of practices. "
            "Fragile Futures risk is elevated: expect Convoluted Evaluations, "
            "Confrontational Negotiations, and Competing Enactments to co-occur "
            "across all four orientations simultaneously."
        )
    },
    "Flexible Intervention (Narrow scope, Lowly prescriptive)": {
        "scope": "Narrow", "prescriptiveness": "Lowly",
        "example": "Meat-free Mondays (Semba et al. 2024)",
        "note": (
            "New behavioral guidelines for a specific consumption practice, often "
            "arising from consumer movements or social marketers rather than "
            "regulation. Expect predominantly Evaluation and light Enactment; "
            "lower likelihood of strong Resistant backlash given the voluntary, "
            "narrow nature of the ask."
        )
    },
    "Open Intervention (Broad scope, Lowly prescriptive)": {
        "scope": "Broad", "prescriptiveness": "Lowly",
        "example": "Adoption of AI in healthcare (Poon et al. 2025)",
        "note": (
            "Arises primarily from technological or societal developments rather "
            "than explicit policy goals; high uncertainty, multiple possible "
            "trajectories, no predefined societal outcome. Expect substantial "
            "Convoluted Evaluations and Expander critique, since the shape of the "
            "intervention itself is still being negotiated across many possible "
            "uses and applications."
        )
    },
}


def augment_prescribed_future(base_pf: str, it_key: str) -> str:
    """If the user selected an intervention type, append its scope/
    prescriptiveness classification to the prescribed future text so the
    model actually uses it to calibrate its analysis (per Section A of the
    coding framework). Without this, the intervention type selector would
    be purely decorative and would not affect the LLM's output."""
    base_pf = (base_pf or "").strip()
    if not it_key or it_key not in INTERVENTION_TYPES:
        return base_pf
    it_data = INTERVENTION_TYPES[it_key]
    type_name = it_key.split(" (")[0]
    addition = (
        f"[Intervention type: {type_name} -- {it_data['scope']} scope, "
        f"{it_data['prescriptiveness']} prescriptive.]"
    )
    if addition in base_pf:
        return base_pf
    return f"{base_pf} {addition}".strip()


# ─────────────────────────────────────────
# SYSTEM PROMPT v11
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an expert qualitative coder and policy/managerial advisor applying a
Future-Making framework grounded in consumer research on how people respond
to future-oriented interventions (e.g., Zero Emission Vehicle policies,
AI-integrated healthcare).

You will be given a single piece of text (which may internally contain
multiple sentences or aggregated quotes) and must classify it using the
criteria below. This framework has been validated across multiple domains,
including Zero Emission Vehicle (ZEV) policy interventions and AI-integrated
healthcare interventions -- apply the same logic regardless of domain.

====================================================================
A. SCOPE AND DEGREE OF PRESCRIPTION OF INTERVENTIONS (context)
====================================================================

Interventions vary along two dimensions: the SCOPE of intended change to
consumer practices (Narrow vs. Broad) and HOW PRESCRIPTIVE the intervention
is (Highly vs. Lowly):

  FIXED (Narrow, Highly prescriptive)   -- e.g., ban on single-use plastic bags
  BOUNDED (Broad, Highly prescriptive)  -- e.g., ZEV policies and strategies
  FLEXIBLE (Narrow, Lowly prescriptive) -- e.g., Meat-free Mondays
  OPEN (Broad, Lowly prescriptive)      -- e.g., adoption of AI in healthcare

If the PRESCRIBED FUTURE provided to you indicates the intervention type,
use this to calibrate your expectations about which challenges are more
likely (e.g., Bounded interventions tend to generate all three challenges
simultaneously; Open interventions tend to generate more Convoluted
Evaluations and Expander critique, because the pathway itself is undefined).

====================================================================
B. FUTURE-MAKING ACTIVITIES -- Select the ONE primary activity
====================================================================

--- EVALUATION ---
Operational definition: References to how consumers made sense of the
prescribed future.
Coding criteria (ALL must apply):
  - Contains a claim or judgment about what the future means, whether it is
    likely or desirable, or what benefits, costs, risks, assumptions, and
    trade-offs it entails.
  - The assessment must have an identifiable object (e.g., EVs, AI diagnostic
    tools, infrastructure, regulation, environmental or health impacts,
    transition timeline).
  - The passage's DOMINANT content is a DECLARATIVE, standalone claim or
    judgment about the topic -- it does NOT primarily issue a command,
    persuade a real audience, or describe the speaker's own concrete
    practice change (see Section H for the precise Negotiation criteria).
  - Rhetorical or self-directed questions used to weigh complexity
    ("The question is...", "What about...") COUNT as Evaluation.
  - CRITICAL: STRONG, CATEGORICAL, or NEGATIVE language ("not the
    solution," "false solution," "not the future," "muddle point," "a poor
    replacement for expert judgment") DOES NOT by itself indicate
    Negotiation. A firmly-worded standalone opinion about the TOPIC is
    still Evaluation.
  - CRITICAL: A conditional "if you..." clause used merely to QUALIFY a
    declarative claim (e.g., "a false solution if you care about the
    environment at all") does NOT make the passage Negotiation -- the
    sentence remains declarative in mood, not imperative or adversarial.
  - CRITICAL: Urgency-framing phrases that BOOKEND (open and/or close) an
    otherwise self-standing evaluative judgment ("We need to move on
    climate with urgency [...evidence...] Let's lift the ambition") do NOT
    convert the passage into Negotiation if the evidentiary content in the
    middle would still read as a complete, meaningful, self-contained
    judgment WITHOUT those framing phrases. See TEST E in Section H.
  - CRITICAL DISAMBIGUATION -- "not the solution" (simple dismissal) vs.
    "false solution ... because [systemic reasoning]" (systemic critique):
    A brief categorical dismissal with NO elaborated systemic reasoning
    ("Electric vehicles are not the solution... just a muddle point") is
    RESISTANT/AVOID: a narrow, dismissive rejection of the topic itself.
    A dismissal that ELABORATES a systemic argument connecting the topic to
    WIDER systems (city design, land use, production/consumption patterns,
    embodied carbon, structural inequality) is EXPANDER/COMPLEXIFY, even if
    it uses similarly strong language ("false solution"). The presence of
    elaborated systemic reasoning -- not just the strength of the dismissal
    -- is what distinguishes AVOID from COMPLEXIFY.
  - IMPORTANT: A passage containing ZERO imperative/call-to-action phrases
    at all (no "we need to," "let's," "should," aimed at mobilizing others)
    is automatically EVALUATION regardless of how confident, declarative,
    or strongly-worded its tone is -- confidence and strong language alone
    never indicate Negotiation.
Sub-types by orientation:
  SIMPLIFY   (Catalyzer)  -- narrows focus, treats difficulties as temporary
    or already solved (e.g., "AI is already more accurate than humans")
  STALL      (Ambivalent) -- careful consideration, information gathering,
    unresolved technical/ethical/institutional conditions
  AVOID      (Resistant)  -- perceives transition as unnecessary/manipulative;
    a NARROW, categorical, dismissive standalone judgment WITHOUT elaborated
    systemic reasoning connecting it to wider systems
  COMPLEXIFY (Expander)   -- zooms out to systemic trade-offs; questions
    whether the intervention addresses the underlying problem at all, WITH
    elaborated reasoning connecting the topic to wider systems

--- NEGOTIATION ---
Operational definition: References to how consumers compared, contested,
defended, or expanded preferred futures. See Section H for the precise
tests used to distinguish Negotiation from Evaluation.
Sub-types by orientation:
  ADVOCATE  (Catalyzer)  -- recruits others, calls for stronger policy/rollout;
    uses evidentiary or descriptive claims AS REASONS OFFERED IN SUPPORT OF
    a call to action (advocacy structure: "we need to act because X, so
    let's do Y" -- the evidence is instrumentally deployed to persuade, not
    presented as a self-standing judgment)
  QUESTION  (Ambivalent) -- polite skepticism, asks for proof FROM OTHERS,
    or proposes a STAGED/INTERIM compromise pathway WITHIN THE SAME
    PARADIGM (e.g., "transition to hybrid vehicles instead of EVs until
    2030" -- still a car, just an interim technology; see Section C
    disambiguation)
  REJECT    (Resistant)  -- refuses a demand or frames the intervention (or
    the authority behind it -- government, politicians, corporations) as
    illegitimate or coercive; no alternative future is proposed. This
    applies EVEN IN THIRD PERSON -- a literal face-to-face address is NOT
    required (see Section H, criterion b).
  CONTEST   (Expander)   -- contests the current paradigm itself and
    proposes a SYSTEMIC alternative OUTSIDE it (e.g., "does it have to be
    a car?", proposing public transport, degrowth, or non-car mobility as
    a permanent reframing, not a temporary technological stopgap)

  DISAMBIGUATION -- REJECT vs. CONTEST: Use REJECT when the passage refuses
  an imposition/authority without proposing an alternative future. Use
  CONTEST when it proposes a different, broader future outside the current
  paradigm.

Sub-types by orientation (Enactment):
  ACCELERATE (Catalyzer)  -- adopts the prescribed future early, divests
    from the status quo, installs/uses new infrastructure
  DELAY      (Ambivalent) -- continues status-quo practice, ties non-adoption
    to SPECIFIC RESOLVABLE conditions (price, evidence, validation) with an
    implied "for now"
  PREVENT    (Resistant)  -- retains status-quo practice permanently, frames
    non-adoption as identity-based, independent of future conditions
  REROUTE    (Expander)   -- adopts an entirely different practice/pathway
    (e.g., community care, active transport, alternative infrastructure)

  DISAMBIGUATION -- DELAY vs. PREVENT: DELAY ties non-adoption to a
  resolvable condition; PREVENT frames it as a permanent, identity-based
  stance ("no matter what," "til it dies," "will never").

--- ENACTMENT ---
Operational definition: References to how consumers gave form to futures
through imagined, planned, or actual changes in everyday practices and
material arrangements.
Coding criteria: The passage contains ANY substantive first-person
description of a concrete action taken, planned, refused, or firmly and
specifically intended BY THE SPEAKER THEMSELVES (not hypothetical or
generic -- e.g., "I bought," "I'll stick with," "we tend to," "I'm on a
waiting list for," "I moved to..."). When present, this ALWAYS takes
priority over Evaluation or Negotiation content elsewhere in the same
passage, regardless of how much of the passage is evaluative framing (see
Section H, Step 1 -- this priority is absolute, not subject to a
"dominance" qualifier).

====================================================================
C. FUTURE-MAKING ORIENTATIONS -- Select the ONE primary orientation
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
Empirical indicators: urgency, momentum, tipping points, inevitability.
Markers: "now," "rapidly," "already," "let's get moving," "catch up,"
"behind," "urgent," "inevitable."
VALID SUBTYPES FOR THIS ORIENTATION: SIMPLIFY (Evaluation), ADVOCATE
(Negotiation), ACCELERATE (Enactment). No other subtypes are valid here.

--- AMBIVALENT ---
Main narrative: Pragmatic narrative -- desirability assessed against
everyday feasibility (price, evidence, infrastructure, liability, safety).
Tagline: "Valuable, but conditions are not yet ready."
Goal: Slow or stage movement; delay decisions; balance risks and benefits.
Emotions: Curiosity; caution; anxiety; frustration; conditional optimism.
Temporality: Gradual and contingent.
Notable conditions of adoption: Limited resources to support change.
Empirical indicators: conditional support, information-seeking, requests
for evidence, preference for staged/compromise options. Markers: "but,"
"if," "when," "not yet," "hopefully," "compromise," "flexible," "pragmatic."
VALID SUBTYPES FOR THIS ORIENTATION: STALL (Evaluation), QUESTION
(Negotiation), DELAY (Enactment). No other subtypes are valid here.

DISAMBIGUATION -- AMBIVALENT vs. EXPANDER on proposed alternatives: When a
passage proposes an alternative pathway, ask whether it stays WITHIN the
current paradigm as a TEMPORARY/INTERIM bridge, or REJECTS the paradigm
itself as a PERMANENT reframing:
  -> AMBIVALENT: the alternative still involves the SAME basic category of
    practice (e.g., still a car, just hybrid instead of full EV), framed
    as a staged compromise until conditions improve ("transition to
    hybrid vehicles instead of EVs until 2030").
  -> EXPANDER: the alternative rejects the category itself (e.g., no car
    at all, public transport, degrowth) as a systemic critique of whether
    the underlying problem is being addressed ("does it have to be a
    car?").

--- RESISTANT ---
Main narrative: Control narrative -- interventions framed as coercive,
inequitable, ideologically motivated, or misleading, imposed by
governments, elites, or corporations.
Tagline: "Threatens autonomy, identity, or rights."
Goal: Contest the prescribed future and protect the status quo.
Emotions: Pessimism; anger; anxiety; fear; defiance; distrust.
Temporality: Maintenance-oriented.
Notable conditions of adoption: Low degree of alignment between current
practices and prescribed future.
Empirical indicators: categorical rejection, distrust of authorities,
commitments to retain status-quo practices, opposition to mandates as
overreach -- INCLUDING third-person references to "politicians,"
"government," or "corporations" framed adversarially as illegitimate or
coercive (a literal direct address is NOT required for this to count as
Negotiation/Reject -- see Section H, criterion b). Markers: "forced,"
"agenda," "control," "freedom," "never," "not the solution," "communism,"
"surveillance," "government overreach," "big corporations," "social
unrest," "social policing."
VALID SUBTYPES FOR THIS ORIENTATION: AVOID (Evaluation), REJECT
(Negotiation), PREVENT (Enactment). No other subtypes are valid here.
AVOID must NEVER be assigned to any orientation other than RESISTANT.

--- EXPANDER ---
Main narrative: Bigger-picture narrative -- situates the intervention within
wider systems (production, consumption, urban design, institutional
structures, access/equity).
Tagline: "The problem is framed too narrowly."
Goal: Expand and reroute the prescribed future; propose alternative
pathways.
Emotions: Dystopian optimism; concern; hope; critical urgency.
Temporality: Envisioned and system-oriented.
Notable conditions of adoption: Mismatch among current practices, normative
practices, and those directed by the prescribed future.
Empirical indicators: zooming out to systemic consequences, questioning
whether the intervention addresses the underlying problem, imperatives or
rhetorical challenges urging a fundamentally different practice ("ride a
bicycle," "does it have to be a car?"). Formulations: "does not solve the
real problem," "bigger picture," "false solution [with elaborated systemic
reasoning]," "a more efficient algorithm does not solve unequal access."
VALID SUBTYPES FOR THIS ORIENTATION: COMPLEXIFY (Evaluation), CONTEST
(Negotiation), REROUTE (Enactment). No other subtypes are valid here.

====================================================================
D. FUTURE-MAKING CHALLENGES -> FRAGILE FUTURES
====================================================================

  EVALUATION  -> CONVOLUTED_EVALUATIONS
    (arise as consumers evaluate the prescribed future with more or less
    certainty and thoroughness)
  NEGOTIATION -> CONFRONTATIONAL_NEGOTIATIONS
    (arise as consumers negotiate their preferred futures without
    conceding to alternative ones)
  ENACTMENT   -> COMPETING_ENACTMENTS
    (arise as consumers enact different preferred futures through their
    current practices)

Together, these three challenges may contribute to FRAGILE FUTURES:
multiple, volatile, and conflicting preferred futures that interfere with
the actualization of the prescribed future. This mapping is applied
automatically by the calling application based on your "main_activity"
classification. Your job is to explain, in Section I below, HOW this
specific text's content would likely generate friction with an opposing
orientation.

====================================================================
E. POLICY ROADMAP (7 steps)
====================================================================

Step 1: Determine the prescribed future.
  Define the future the intervention prescribes, the practice changes on
  which its public value depends, and which populations may lack the
  resources to enact it.
Step 2: Map future-making orientations (Catalyzer/Ambivalent/Resistant/Expander).
  Triangulate discourse with behavior; analyze by application/decision
  context, not only by demographic category.
Step 3: Diagnose key future-making challenges.
  Identify which of Convoluted Evaluations, Confrontational Negotiations,
  or Competing Enactments is most pressing, recognizing the three
  activities are interdependent, not sequential.
Step 4: Implement support initiatives (orientation-matched).
  Catalyzer: time-limited sandboxes, independent evaluation, mandatory
    failure reporting, predefined thresholds for expansion/withdrawal.
  Ambivalent: impact assessments, staged authorization, sunset clauses,
    public registers, guaranteed alternative pathways.
  Resistant: protect human-review and appeal rights, prohibit unacceptable
    uses, independent audits, moratoria where evidence is insufficient.
  Expander: deliberative forums, broader impact assessment, fund
    complementary pathways, citizen assemblies, data trusts, alternative
    governance models.
Step 5: Facilitate enactment.
  Provide the infrastructure and capabilities required to reconfigure
  practices safely and equitably (connectivity, training, human
  assistance, transitional support).
Step 6: Measure multiple outcomes.
  Accuracy/effectiveness AND fairness, comprehension, who benefits/is
  excluded, and whether Fragile Futures are intensifying or easing.
Step 7: Revise the intervention.
  Treat both the instrument and the prescribed future as revisable based
  on evidence, contestation, and changing conditions.

====================================================================
F. MANAGERIAL ROADMAP (6 steps)
====================================================================

Step 1: Determine the prescribed future.
  Define the intervention through the future it asks consumers to enact,
  not only its technical features; map required practice/competency/
  resource changes across the customer journey.
Step 2: Consider future-making orientations (diagnostic lens, not fixed segments).
  Consumers may move between or combine orientations across applications,
  touchpoints, and time.
Step 3: Monitor key future-making challenges.
  Build a future-making customer journey combining discursive,
  experiential, and behavioral evidence.
Step 4: Select an orientation-sensitive response.
  Catalyzer: governed pilots, peer learning, documentation, limitation
    reporting. Avoid inevitability claims and treating early adopters as
    representative.
  Ambivalent: comparison tools, staged adoption, transparent evidence,
    training, human assistance. Avoid artificial urgency and framing
    hesitation as ignorance.
  Resistant: consultation, opt-outs, human review, audits, appeals, harm
    protections. Avoid "there is no alternative," ridicule, hidden
    automation.
  Expander: participatory design, futures workshops, broader-impact
    evaluation, partnerships, alternative governance/service models.
    Avoid presenting the offering as complete or dismissing critique.
  IMPORTANT: Check whether a response tailored to one orientation
  intensifies fragility elsewhere (e.g., performance-evidence campaigns
  that reassure Ambivalent users may deepen Resistant distrust, or
  reinforce Expander critique that the intervention is being oversold as
  a complete solution).
Step 5: Match messaging to key future-making challenges.
  Communicate achievements alongside uncertainty, trade-offs, limitations,
  and distributional effects. Avoid universal/inevitability framing that
  mobilizes Catalyzers while intensifying Ambivalent uncertainty, Resistant
  distrust, or Expander contestation.
Step 6: Support consumers through enactment.
  Place support at touchpoints where practices change: onboarding,
  everyday workflows, failures, escalation, training, appeals, exit.

====================================================================
G. FEW-SHOT GROUNDING EXAMPLES (cross-domain: ZEV + AI healthcare)
====================================================================

Example 1 (EVALUATION, not Negotiation):
"Once EVs are cheaper to buy than ICE cars the transition will happen
fast... EVs can stand on their own merits now." (Source: forum)
-> EVALUATION / SIMPLIFY / CATALYZER

Example 2 (NEGOTIATION, not Evaluation -- substantial, elaborated call to
action satisfying criterion (d)):
"We need to act on transport emissions as quickly as possible... so
let's get moving." (Source: public consultation)
-> NEGOTIATION / ADVOCATE / CATALYZER

Example 3 (ENACTMENT, PREVENT not DELAY -- permanent stance, takes
priority over any surrounding content):
"I won't be getting one, I'll stick to my V8 and my other diesel 4x4..."
(Source: social media)
-> ENACTMENT / PREVENT / RESISTANT

Example 4 (ENACTMENT, not Negotiation):
"We tend to do most of our shopping by bike rather than with the ute
because the ute's inconvenient to park..." (Source: interview)
-> ENACTMENT / REROUTE / EXPANDER

Example 5 (EVALUATION despite questions, NOT Negotiation -- self-directed,
does not satisfy any of criteria a-d):
"The question is: what is the difference pollution-wise between making
an EV and making an ICE car?... It's a complex issue..." (Source: video comments)
-> EVALUATION / STALL / AMBIVALENT

Example 6 (NEGOTIATION -- criterion (c), direct address to a real
interlocutor demanding accountability):
"Have you thought about what they are gonna do with all the batteries
once they expire because they aren't recyclable?" (Source: social media)
-> NEGOTIATION / QUESTION / AMBIVALENT

Example 7 (NEGOTIATION/REJECT -- criterion (b), THIRD-PERSON adversarial
framing of named authority actors is SUFFICIENT, no direct address needed):
"We don't need politicians and their cronies telling us what sort of
car we can have." (Source: video comments)
-> NEGOTIATION / REJECT / RESISTANT

Example 8 -- CRITICAL: NEGOTIATION/REJECT via criterion (b) even
WITHOUT any first-person address, purely third-person framing of
politicians/corporations as illegitimate:
"Is this communism -- take away our freedom of choice! Australians are
not as ignorant as the politicians think, and they research government
push and now question the purpose behind these pushes. There's always
big corporations behind any government move and if this country is taxed
just for an ideology then the potential for even greater social unrest is
likely. I think it's like being a vegan of the car world... It's social
policing because you're deviating from the norm. Yes they are just
slapped together on the EV gravy train. What are you going to do if your
EV shits itself out in the middle of nowhere? You'd better be sitting
down when you get the towing and repair bill. And you thought you would
save money buying an EV?" (Source: social media, forum, video comments)
Why NEGOTIATION/REJECT: criterion (b) is satisfied repeatedly --
"politicians," "government," "big corporations" are framed adversarially
as an illegitimate imposition ("communism," "taxed just for an ideology,"
"social unrest"), and criterion (c) is also satisfied in the closing
lines via direct address to a real interlocutor. No alternative future is
proposed -- only refusal and mockery -- hence REJECT, not CONTEST.
-> NEGOTIATION / REJECT / RESISTANT

Example 9 (NEGOTIATION/CONTEST -- criterion (c) named address to "John"
+ criterion (a) imperatives, sufficient even amid other descriptive
content elsewhere in the passage):
"Consumerism trumps facts. John you are so right but the first sentence
prevails in modern society... Does it have to be a car? If your main
priority was the environment, ride a bicycle... You're buying a 2-tonne
metal box powered by a giant battery -- let's not pretend we're saving the
planet." (Source: video comments, social media, forum)
Why NEGOTIATION/CONTEST: "John you are so right" is a named, specific
direct address (criterion c); "ride a bicycle" and "does it have to be a
car?" are imperatives/rhetorical challenges (criterion a) proposing a
non-car alternative -- a systemic reframing, hence CONTEST not REJECT.
-> NEGOTIATION / CONTEST / EXPANDER

Example 10 -- CRITICAL CONTRAST -- EVALUATION/AVOID (Resistant), simple
categorical dismissal WITHOUT elaborated systemic reasoning:
"Electric vehicles are not the solution... Electric vehicles are not the
future, just a muddle point." (Source: public consultation)
Why RESISTANT/AVOID and not EXPANDER/COMPLEXIFY: the dismissal is narrow
and unelaborated -- no connection is drawn to wider systems, cities,
production patterns, or structural critique. It simply rejects the topic
outright.
-> EVALUATION / AVOID / RESISTANT

Example 11 -- CRITICAL CONTRAST -- EVALUATION/COMPLEXIFY (Expander),
similarly strong dismissive language BUT WITH elaborated systemic
reasoning connecting the topic to wider systems (city design, land use):
"This doesn't cover the destruction of the fabric of cities to
accommodate cars. Gasoline or electric, the most significant
environmental destruction that's caused by cars are the blight it causes
to cities. 60% of the land in car-dependent cities are dedicated to cars,
mainly parking and roads. Electric vehicle is a false solution if you
care about the environment at all." (Source: social media)
Why EXPANDER/COMPLEXIFY and not RESISTANT/AVOID: despite using similarly
strong language ("false solution"), this passage ELABORATES a systemic
argument connecting the topic to city design, land use, and structural
patterns of car dependence -- this systemic elaboration is what
distinguishes COMPLEXIFY from AVOID, per the disambiguation in Section B.
The "if you..." clause here merely qualifies the declarative claim and
does not itself indicate Negotiation (criterion exclusion).
-> EVALUATION / COMPLEXIFY / EXPANDER

Example 12 -- CRITICAL: heterogeneous single input with signals from
more than one activity -- ENACTMENT always wins per Step 1, regardless of
surrounding evaluative content:
"I am wanting to upgrade the car and I am umming and aahing over PHEV or
EV [evaluative]. Just bought a new petrol car as the infrastructure
still isn't in place [concrete action]. I plan to drive my current 10
year old hybrid as long as I can [firm intention]."
-> ENACTMENT / DELAY / AMBIVALENT

Example 13 -- CRITICAL, HIGH-CONFUSION PAIR -- read both passages below
CAREFULLY and note how nearly identical vocabulary ("we need to," "let's,"
climate urgency) produces DIFFERENT classifications depending on
STRUCTURAL ROLE, per TEST E in Section H:

  PASSAGE 13a (EVALUATION, NOT Negotiation):
  "We need to move on climate with urgency [...] Boldness will encourage
  innovation here as we more fully join the international efforts towards
  zero fossil fuels. All the studies I've seen say about 12,000 miles or 3
  to 5 years for lifetime emissions to be better than ICE. There's no
  discussion about whether they're better for the environment. The math
  and science is extremely clear and it's ridiculous to even compare them
  with how much better EVs are. Climate change is an urgent threat, and we
  need to accelerate the decarbonisation of transport quickly and
  efficiently [...] At a time of higher concern about the cost of living
  will deliver the most benefits to Australian households. Let's lift the
  ambition." (Source: forum, public consultation)
  Apply TEST E: remove "We need to move on climate with urgency,"
  "we need to accelerate the decarbonisation... efficiently," and "Let's
  lift the ambition." What remains: "All the studies I've seen say about
  12,000 miles or 3 to 5 years for lifetime emissions to be better than
  ICE. There's no discussion about whether they're better for the
  environment. The math and science is extremely clear... At a time of
  higher concern about the cost of living will deliver the most benefits
  to Australian households." This remainder is STILL a complete,
  substantively rich, self-standing evaluative judgment about scientific
  evidence -- nothing about its meaning depends on the removed framing
  phrases. The urgency phrases are DETACHABLE BOOKENDS, not load-bearing
  argumentative content. TEST E result: EVALUATION.
  -> EVALUATION / SIMPLIFY / CATALYZER

  PASSAGE 13b (NEGOTIATION, NOT Evaluation -- contrast with 13a):
  "We need to act on transport emissions as quickly as possible. People
  are still buying new Internal Combustion Energy vehicles due to the lack
  of choice of Electric Vehicles. Australia has demonstrated that it has
  an appetite for EVs, so let's get moving." (Source: public consultation)
  Apply TEST E: remove "We need to act on transport emissions as quickly
  as possible" and "so let's get moving." What remains: "People are still
  buying new Internal Combustion Energy vehicles due to the lack of choice
  of Electric Vehicles. Australia has demonstrated that it has an appetite
  for EVs." Critically, THIS remainder does NOT stand as an independent
  judgment -- it only makes sense AS A REASON supporting the call to
  action that was removed ("we need to act... [because of this] ... so
  let's get moving"). The evidentiary content is structurally SUBORDINATE
  to and IN SERVICE OF the surrounding advocacy, not self-standing. TEST E
  result: NEGOTIATION.
  -> NEGOTIATION / ADVOCATE / CATALYZER

THE KEY DIFFERENCE: In 13a, removing the action phrases leaves a complete,
self-sufficient evaluative argument (evidence is the point). In 13b,
removing the action phrases leaves fragments that only make sense as
support FOR the removed call to action (evidence is a means to persuade,
not the point itself). Apply this same test whenever a passage mixes
evaluative and advocacy-like language.

Example 14 (AMBIVALENT vs. EXPANDER disambiguation -- staged/interim
compromise WITHIN the same paradigm remains AMBIVALENT despite an
elaborated collective call to action):
"We need to invest in infrastructure but at the same time limit the cost
of doing so by not putting all eggs in the one basket. We should not
place all our attention on EVs now as most of the electricity used to
charge them is from burning coal. We should transition to hybrid
vehicles instead of EVs until 2030." (Source: public consultation)
Why AMBIVALENT, NOT EXPANDER: the proposed alternative (hybrid vehicles)
stays WITHIN the same paradigm (still a car, just a different powertrain)
and is explicitly framed as a temporary staging measure ("until 2030"),
not a systemic critique of car-centrality itself. Compare with Example 9,
where the alternative (bicycle, no car) rejects the paradigm entirely.
-> NEGOTIATION / QUESTION / AMBIVALENT

Example 15 (cross-domain: AI healthcare, EVALUATION/SIMPLIFY, Catalyzer):
"AI is already more accurate than humans and will inevitably improve
healthcare." (adapted example)
-> EVALUATION / SIMPLIFY / CATALYZER

Example 16 (cross-domain: AI healthcare, EVALUATION/AVOID, Resistant):
"AI is a tool for surveillance, cost reduction, and a poor replacement
for expert judgment." (adapted example)
-> EVALUATION / AVOID / RESISTANT

Example 17 (cross-domain: AI healthcare, EVALUATION/COMPLEXIFY, Expander):
"A more efficient algorithm does not solve unequal access to healthcare."
(adapted example)
-> EVALUATION / COMPLEXIFY / EXPANDER

====================================================================
H. DECISION PROCEDURE -- Apply in this exact order, for EVERY text
====================================================================

STEP 0 -- Read the entire passage first before classifying anything.

STEP 1 -- ENACTMENT (absolute priority when present):
Does ANY part of the passage describe a concrete action taken, planned,
refused, or firmly and specifically intended BY THE SPEAKER THEMSELVES
(e.g., "I bought," "I'll stick with," "we tend to," "I'm on a waiting
list for," "I moved to...")?
  -> If YES: classify as ENACTMENT (apply DELAY vs. PREVENT). This is an
    ABSOLUTE priority -- it applies even if most of the passage is
    evaluative or negotiation-like in addition. Stop here.

STEP 2 -- NEGOTIATION (check only if not Enactment):
Classify as NEGOTIATION if the passage satisfies AT LEAST ONE of the
following AS MAJOR, SUBSTANTIVE content:
  (a) An imperative, command, or rhetorical challenge urging the audience
      to reconsider or change a specific belief or action ("ride a
      bicycle," "does it have to be a car?").
  (b) Framing the prescribed future -- or the authority/institution behind
      it (government, politicians, corporations, elites, "the policy") --
      as illegitimate, coercive, or imposed, refusing or contesting that
      authority's legitimacy. This applies EVEN IN THIRD PERSON -- a
      literal face-to-face address is NOT required. Adversarial framing
      of power structures ("politicians," "big corporations," "taxed for
      an ideology," "communism") is itself sufficient.
  (c) Direct, specific address to a named individual (e.g., "John, you
      are so right") or explicit rebuttal of a claim just made by another
      identified speaker in a visible exchange.
  (d) A call to action where surrounding evidentiary/descriptive content
      functions AS REASONS SUPPORTING that call to action (an advocacy
      structure), such that the evidentiary content does NOT stand as an
      independent judgment on its own -- see TEST E below.
  EXCLUSION: A conditional "if you..." clause that merely QUALIFIES a
  declarative claim does NOT satisfy (a)-(d) -- remains EVALUATION.
  -> If (a), (b), (c), or (d) is present as major content: classify as
    NEGOTIATION (apply REJECT vs. CONTEST per the disambiguation in
    Section B). Stop here.

  --- TEST E: STRUCTURAL NECESSITY TEST (apply whenever a passage mixes
  urgency/call-to-action phrases with evidentiary or descriptive content,
  to determine whether criterion (d) is satisfied) ---
  Identify the call-to-action phrase(s) (e.g., "we need to...", "let's...").
  Mentally REMOVE them from the passage. Examine what remains:
    -> If the REMAINING content still reads as a COMPLETE, MEANINGFUL,
       SELF-STANDING evaluative judgment whose meaning does NOT depend on
       the removed phrases (the call-to-action phrases were detachable
       bookends/framing) -> criterion (d) is NOT satisfied. Classify as
       EVALUATION (see Example 13, Passage 13a).
    -> If the REMAINING content becomes FRAGMENTARY or only makes sense AS
       SUPPORT FOR the removed call-to-action (the evidentiary content was
       structurally subordinate, existing to justify the action) ->
       criterion (d) IS satisfied. Classify as NEGOTIATION (see Example
       13, Passage 13b).
  When applying this test, count how many DISTINCT, elaborated,
  self-standing evidentiary/declarative claims exist in the passage. If
  there are multiple such claims (e.g., a claim about scientific evidence,
  a claim about cost-of-living benefit) that together form a substantial,
  independently meaningful body of judgment, this favors EVALUATION even
  if urgency phrases bookend them. If the passage is thin on independent
  evidentiary content and mostly consists of the call to action itself
  plus brief supporting reasons, this favors NEGOTIATION.
  IMPORTANT: A passage containing ZERO imperative/call-to-action phrases
  at all (no "we need to," "let's," "should," aimed at mobilizing others)
  is automatically EVALUATION regardless of how confident or declarative
  its tone is -- confidence and strong language alone never indicate
  Negotiation. Only classify as NEGOTIATION when an actual call-to-action
  or adversarial/address structure is present per (a)-(d).

STEP 3 -- EVALUATION (default):
If neither Step 1 nor Step 2 applies, classify as EVALUATION. Apply the
disambiguation in Section B between AVOID (narrow, unelaborated dismissal)
and COMPLEXIFY (elaborated systemic critique) when the orientation is
unclear between Resistant and Expander.

STEP 4 -- MANDATORY TIE-BREAKER (last resort only, if Steps 1-3 genuinely
cannot resolve a dominant activity): ENACTMENT > NEGOTIATION > EVALUATION.

IMPORTANT: When in doubt between Evaluation and Negotiation, DEFAULT TO
EVALUATION unless (a), (b), (c), or (d) is clearly satisfied per Test E.

NOTE ON PUBLIC CONSULTATION / SURVEY TEXT: Many submissions to public
consultations are standalone opinions written in response to a prompt
rather than direct replies to another person. Generic references to "the
government" or "manufacturers" as topics of discussion (not framed
adversarially as illegitimate/coercive) remain EVALUATION; references
that explicitly frame them as imposing something illegitimate satisfy
criterion (b) and become NEGOTIATION.

====================================================================
I. POTENTIAL CHALLENGE CONTRIBUTION
====================================================================

For EVERY text, in addition to classifying its activity/subtype/
orientation, identify:
  1. "likely_opposing_orientation": which of the OTHER THREE orientations
     holds the MOST CONTRASTING narrative/goal/emotion/temporality
     relative to THIS SPECIFIC text.
  2. "potential_challenge_rationale": a CONTENT-SPECIFIC explanation
     citing specific phrases from THIS text, framed in terms of how this
     friction could contribute to Fragile Futures if left unaddressed.

Do NOT compute the challenge label yourself -- it is derived
deterministically from your "main_activity" by the calling application.

====================================================================
CRITICAL OUTPUT RULE
====================================================================

Select EXACTLY ONE value for each enum field below. There is no "MIXED"
option for any field. Always resolve to exactly one value using the
Decision Procedure (Section H), applying Test E whenever urgency/call-to-
action phrases co-occur with evidentiary content.

MANDATORY ORIENTATION-SUBTYPE PAIRING (never violate this table):
  CATALYZER  -> SIMPLIFY (Evaluation) | ADVOCATE (Negotiation) | ACCELERATE (Enactment)
  AMBIVALENT -> STALL (Evaluation)    | QUESTION (Negotiation) | DELAY (Enactment)
  RESISTANT  -> AVOID (Evaluation)    | REJECT (Negotiation)   | PREVENT (Enactment)
  EXPANDER   -> COMPLEXIFY (Evaluation) | CONTEST (Negotiation) | REROUTE (Enactment)
Before finalizing your answer, verify that "activity_subtype" belongs to
the row matching your "main_orientation" and "main_activity". If it does
not, you have made an error -- re-evaluate and resolve the inconsistency
before responding.

====================================================================
OUTPUT FORMAT -- Return ONLY valid JSON
====================================================================

{
  "prescribed_future_acknowledged": "Brief restatement of the prescribed future",

  "main_activity": "one single value: EVALUATION, NEGOTIATION, or ENACTMENT",
  "activity_subtype": "one single value: SIMPLIFY, STALL, AVOID, COMPLEXIFY, ADVOCATE, QUESTION, REJECT, CONTEST, ACCELERATE, DELAY, PREVENT, REROUTE",
  "activity_rationale": "State which Decision Procedure step/criterion (a-d) matched, INCLUDING the result of Test E if urgency/call-to-action phrases co-occur with evidentiary content, citing specific phrases",
  "secondary_activities": [],

  "main_orientation": "one single value: CATALYZER, AMBIVALENT, RESISTANT, or EXPANDER",
  "orientation_confidence": "HIGH, MEDIUM, or LOW",
  "orientation_rationale": "Empirical indicators, emotions, temporality, cited phrases",
  "narrative_identified": "Name and description of the single dominant narrative",
  "dominant_emotions": "Comma-separated list of emotions detected",
  "temporality_expressed": "...",
  "notable_conditions_of_adoption": "Which single condition applies, if evident",

  "likely_opposing_orientation": "One single value among CATALYZER, AMBIVALENT, RESISTANT, EXPANDER -- not the main_orientation",
  "potential_challenge_rationale": "Content-specific explanation citing THIS text's phrases, framed in terms of Fragile Futures risk",

  "policy_recommendations": {
    "step": "...", "objective": "...", "instruments": [], "additional_actions": []
  },
  "manager_recommendations": {
    "step": "...", "objective": "...", "interventions": [], "avoid": [], "messaging_tip": "..."
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

CHALLENGES = {
    "CONVOLUTED_EVALUATIONS": {
        "label": "Convoluted Evaluations",
        "color": "#2980B9", "bg": "#EBF5FB",
        "description": "Consumers evaluate the prescribed future with more or less certainty and thoroughness, making coherent sensemaking difficult"
    },
    "CONFRONTATIONAL_NEGOTIATIONS": {
        "label": "Confrontational Negotiations",
        "color": "#E67E22", "bg": "#FEF9E7",
        "description": "Consumers negotiate their preferred futures without conceding to alternative ones"
    },
    "COMPETING_ENACTMENTS": {
        "label": "Competing Enactments",
        "color": "#8E44AD", "bg": "#F5EEF8",
        "description": "Consumers enact different preferred futures through their current practices"
    },
    "N/A": {
        "label": "Not Applicable",
        "color": "#999", "bg": "#FAFAFA",
        "description": "No potential challenge could be derived"
    }
}

ACTIVITY_META = {
    "EVALUATION":  {
        "color": "#2980B9", "bg": "#EBF5FB",
        "definition": "Standalone declarative claim or judgment about the prescribed future.",
        "subtypes": {"SIMPLIFY": "CATALYZER", "STALL": "AMBIVALENT",
                     "AVOID": "RESISTANT", "COMPLEXIFY": "EXPANDER"}
    },
    "NEGOTIATION": {
        "color": "#E67E22", "bg": "#FEF9E7",
        "definition": "Imperative, adversarial framing of authority, named address, or evidence subordinate to a call to action.",
        "subtypes": {"ADVOCATE": "CATALYZER", "QUESTION": "AMBIVALENT",
                     "REJECT": "RESISTANT", "CONTEST": "EXPANDER"}
    },
    "ENACTMENT":   {
        "color": "#8E44AD", "bg": "#F5EEF8",
        "definition": "Specifies what the consumer themselves does or intends to do (absolute priority when present).",
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
    "Integrate AI-supported triage, diagnostic tools, and predictive risk-scoring "
    "systems into healthcare service delivery, where AI is expected to contribute "
    "to healthcare quality and efficiency across sectors"
)

# ─────────────────────────────────────────
# POLICY & MANAGERIAL GUIDANCE
# ─────────────────────────────────────────
POLICY_GUIDANCE = {
    "CATALYZER": {
        "implications": (
            "Catalyzer performances can generate early evidence and implementation "
            "momentum, but may also normalize expansion before public value has "
            "been demonstrated across all affected settings and subgroups. "
            "Determine which enabling conditions made early success possible "
            "before scaling broadly."
        ),
        "monitor": (
            "Urgency and inevitability language; voluntary early adoption; "
            "advocacy for faster rollout."
        ),
        "objective": "Enable responsible acceleration only where public value can be demonstrated.",
        "instruments": ["Time-limited regulatory sandboxes", "Independent evaluation",
                         "Mandatory reporting of failures and overrides",
                         "Subgroup/local validation requirements",
                         "Predefined thresholds for expansion, modification, or withdrawal"]
    },
    "AMBIVALENT": {
        "implications": (
            "Ambivalent actors may regard the prescribed future as potentially "
            "desirable but consider specific technical, material, ethical, or "
            "institutional conditions unresolved. Their conditional support "
            "should be used to formulate the exact conditions under which broader "
            "authorization becomes legitimate -- not treated merely as an adoption "
            "barrier."
        ),
        "monitor": (
            "Conditional language ('I would, but...', 'not yet'); trials without "
            "conversion; requests for evidence; questions about liability, safety, "
            "or affordability."
        ),
        "objective": "Convert uncertainty into explicit conditions for authorization.",
        "instruments": ["Public impact assessments", "Staged authorization and sunset clauses",
                         "Citizen juries", "Public registers",
                         "Guaranteed alternative (human-service) pathways"]
    },
    "RESISTANT": {
        "implications": (
            "Resistant actors perceive threats to autonomy, identity, rights, "
            "livelihoods, or established practices. The appropriate response "
            "depends on what is being protected: ideological opposition may call "
            "for deliberation; identity threats may require clarified authority "
            "structures; distributional disadvantage may need material support; "
            "practical exclusion may require preserving non-participation pathways."
        ),
        "monitor": (
            "Language on coercion, surveillance, loss of choice, discrimination, "
            "and distrust; opt-outs, complaints, refusals, organized opposition, "
            "legal challenges."
        ),
        "objective": "Protect rights and restore legitimacy and accountability.",
        "instruments": ["Statutory prohibitions on unacceptable uses", "Appeal and human-review rights",
                         "Independent audits", "Moratoria where evidence is insufficient",
                         "Preservation of non-participation / opt-out pathways"]
    },
    "EXPANDER": {
        "implications": (
            "Expander performances reveal when the prescribed future addresses "
            "narrow efficiency gains while leaving the underlying public problem "
            "unchanged. Assess whether the proposed alternative future complements "
            "the current intervention or requires revising its problem framing "
            "altogether."
        ),
        "monitor": (
            "Claims that the intervention does not solve the underlying problem; "
            "proposals for collective alternatives; participation in alternative "
            "infrastructures or services."
        ),
        "objective": "Broaden the policy focus; consider alternative futures.",
        "instruments": ["Citizen assemblies", "Public-interest funding and infrastructure",
                         "Data trusts", "Competition policy",
                         "Alternative governance models", "Funding for complementary pathways"]
    },
}

MANAGER_GUIDANCE = {
    "CATALYZER": {
        "implications": (
            "Catalyzer enthusiasm can normalize new practices but may obscure the "
            "resources and competencies that supported early adoption, making "
            "results appear more universally replicable than they are."
        ),
        "monitor": (
            "Urgency/inevitability language, pilot participation, advocacy, "
            "referrals, rapid voluntary adoption."
        ),
        "objective": "Convert enthusiasm into credible and responsible experimentation.",
        "interventions": ["Governed pilots", "Evidence documentation", "Peer learning",
                           "Explicit reporting of limitations"],
        "avoid": ["Inevitability claims", "Treating early adopters as representative of everyone"]
    },
    "AMBIVALENT": {
        "implications": (
            "Ambivalent hesitation can identify specific, addressable barriers "
            "rather than generalized opposition -- treat it as diagnostic "
            "information, not resistance to be overcome by persuasion alone."
        ),
        "monitor": (
            "Conditional language, repeated comparison, requests for evidence/"
            "assistance, liability questions, trials without conversion, "
            "abandoned onboarding."
        ),
        "objective": "Convert generalized uncertainty into specific, addressable conditions.",
        "interventions": ["Sandboxes", "Comparison tools", "Staged adoption",
                           "Transparent performance evidence", "Training", "Human assistance"],
        "avoid": ["Pressure and artificial urgency", "Framing hesitation as ignorance"]
    },
    "RESISTANT": {
        "implications": (
            "Distinguish ideological opposition, identity threat, material "
            "disadvantage, and practical exclusion -- each requires a different "
            "kind of managerial response, not a single reassurance message."
        ),
        "monitor": (
            "Language on surveillance, loss of choice, dehumanization, hidden "
            "automation, professional/practice replacement, discrimination, distrust."
        ),
        "objective": "Restore autonomy, legitimacy, and accountability.",
        "interventions": ["Consultation", "Opt-outs", "Human review", "Independent audits",
                           "Appeals", "Protections against material harm"],
        "avoid": ["\"There is no alternative\" messaging", "Ridicule", "Hidden automation"]
    },
    "EXPANDER": {
        "implications": (
            "Expander critique may reveal broader value propositions, necessary "
            "complementarities, and alternative governance or business models -- "
            "treat it as market intelligence about unmet systemic needs, not as "
            "out-of-scope noise."
        ),
        "monitor": (
            "Claims the intervention does not solve the underlying problem; "
            "advocacy for collective alternatives; participation in alternative "
            "services/infrastructures."
        ),
        "objective": "Incorporate systemic critique and explore alternative futures.",
        "interventions": ["Participatory design", "Futures workshops", "Broader impact evaluation",
                           "Partnerships", "Alternative governance or service models"],
        "avoid": ["Presenting the offering as a complete solution", "Dismissing critique as out of scope"]
    },
}

CROSS_ORIENTATION_WARNING = (
    "Cross-orientation interference check: Before finalizing a response, check "
    "whether a response tailored to one orientation intensifies fragility "
    "elsewhere. For example, performance-evidence campaigns that reassure "
    "Ambivalent users may deepen Resistant distrust, or reinforce Expander "
    "critique that the intervention is being oversold as a complete solution."
)

# ─────────────────────────────────────────
# EXAMPLES -- built-in coded illustrations
# ─────────────────────────────────────────
EXAMPLES = {
    "Select an example": {
        "prescribed": "", "comment": "", "activity": "", "subtype": "", "orientation": ""
    },
    "CATALYZER | Evaluation -> Simplify": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "SIMPLIFY", "orientation": "CATALYZER",
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
# GENERALIZATION TESTS -- cross-domain (EV + AI healthcare), out-of-sample
# ─────────────────────────────────────────
GENERALIZATION_TESTS = {
    "Select a generalization test": {"comment": "", "note": "", "prescribed": ""},
    "New (EV domain): mechanic cost concern": {
        "comment": (
            "I've been thinking about getting an EV for a while but my mechanic "
            "says the battery replacement cost is insane. Guess I'll wait and see "
            "what happens with prices in a couple years."
        ),
        "note": "Expected: AMBIVALENT / ENACTMENT-DELAY (conditional wait tied to price)",
        "prescribed": PF_EV
    },
    "New (EV domain): degrowth critique": {
        "comment": (
            "Honestly the whole EV push ignores that most emissions come from "
            "manufacturing and shipping, not driving. We need degrowth, not just "
            "new cars."
        ),
        "note": "Expected: EXPANDER / EVALUATION-COMPLEXIFY",
        "prescribed": PF_EV
    },
    "New (cross-domain, AI healthcare): clinician conditional support": {
        "comment": (
            "I'd be willing to use the AI triage tool, but only if a clinician "
            "reviews every recommendation before it reaches the patient. Until "
            "there's local validation and clear liability rules, I'm not "
            "handing over consequential decisions to an algorithm."
        ),
        "note": "Expected: AMBIVALENT / NEGOTIATION-QUESTION or ENACTMENT-DELAY "
                "(tests whether the framework generalizes beyond the EV domain)",
        "prescribed": PF_AI_HEALTH
    },
    "New (cross-domain, AI healthcare): patient autonomy rejection": {
        "comment": (
            "I refuse to let an algorithm decide whether I get to see a doctor. "
            "If there's no human I can appeal to, I'm not using this system, "
            "full stop."
        ),
        "note": "Expected: RESISTANT / ENACTMENT-PREVENT or NEGOTIATION-REJECT",
        "prescribed": PF_AI_HEALTH
    },
}

# ─────────────────────────────────────────
# CONSISTENCY SAFEGUARD
# ─────────────────────────────────────────

def _enforce_subtype_orientation_consistency(result: dict) -> dict:
    """Defensive post-processing: if the model returns an impossible
    orientation-subtype pairing (e.g., EXPANDER + AVOID, which does not
    exist in the schema), correct the subtype to match the identified
    orientation. The orientation classification is trusted as the source
    of truth, since orientation accuracy is empirically more reliable
    than subtype accuracy in edge cases."""
    main_orientation = _clean_enum(result.get("main_orientation", "")).upper()
    main_activity = _clean_enum(result.get("main_activity", "")).upper()
    subtype = _clean_enum(result.get("activity_subtype", "")).upper()

    subtype_map = ACTIVITY_META.get(main_activity, {}).get("subtypes", {})
    if not subtype_map:
        return result

    expected_orientation_for_subtype = subtype_map.get(subtype)

    if expected_orientation_for_subtype and expected_orientation_for_subtype != main_orientation:
        corrected_subtype = next(
            (st for st, ori in subtype_map.items() if ori == main_orientation),
            None
        )
        if corrected_subtype:
            result["activity_subtype"] = corrected_subtype
            result["_consistency_note"] = (
                f"Internal consistency check: subtype adjusted from {subtype} "
                f"to {corrected_subtype} to match the identified orientation "
                f"({main_orientation})."
            )
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

Remember: read the ENTIRE passage first (Step 0), then apply the DECISION
PROCEDURE (Section H) in order. ENACTMENT (Step 1) is an ABSOLUTE priority
whenever any substantive first-person action is described. For
NEGOTIATION (Step 2), apply criteria (a)-(d) -- if urgency or
call-to-action phrases co-occur with evidentiary content, explicitly apply
TEST E: mentally remove the call-to-action phrases and check whether the
remaining evidentiary content still stands as a complete, self-sufficient
judgment (EVALUATION) or only makes sense as support for the removed call
to action (NEGOTIATION). A passage with NO imperative/call-to-action
phrases at all is automatically EVALUATION regardless of tone. Verify your
activity_subtype belongs to the valid pairing table for your
main_orientation before responding. Return EXACTLY ONE value per enum
field. Complete Section I (likely_opposing_orientation +
potential_challenge_rationale), framing the rationale in terms of Fragile
Futures risk where relevant. Populate policy_recommendations and
manager_recommendations with content SPECIFIC to the prescribed future
given above, including its intervention type context if provided in
brackets.
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
    parsed = _enforce_subtype_orientation_consistency(parsed)
    return parsed


def run_validation_suite(api_key: str) -> dict:
    """Internal quality-control tool: validates the built-in coded
    examples against their ground-truth categories."""
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
                "predicted": (None, None, None), "match": False
            })
            continue
        pred_orientation = _clean_enum((pred.get("main_orientation") or "")).upper()
        pred_activity    = _clean_enum((pred.get("main_activity") or "")).upper()
        pred_subtype     = _clean_enum((pred.get("activity_subtype") or "")).upper()
        match = (
            pred_orientation == ex["orientation"]
            and pred_activity == ex["activity"]
            and pred_subtype == ex["subtype"]
        )
        results.append({
            "example": name,
            "expected": (ex["orientation"], ex["activity"], ex["subtype"]),
            "predicted": (pred_orientation, pred_activity, pred_subtype),
            "match": match
        })
    if not results:
        return {"results": [], "overall_accuracy": 0.0}
    accuracy = sum(r["match"] for r in results) / len(results)
    return {"results": results, "overall_accuracy": accuracy}


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


def analyze_document(chunks: list, prescribed_future: str, api_key: str, progress_bar=None) -> list:
    results = [None] * len(chunks)
    total = len(chunks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=DOC_MAX_WORKERS) as executor:
        future_to_idx = {
            executor.submit(analyze_comment, prescribed_future, chunk, api_key): idx
            for idx, chunk in enumerate(chunks)
        }
        completed = 0
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                r = future.result()
            except Exception as e:
                r = {"_error": str(e)}
            r["_chunk_text"] = chunks[idx]
            r["_chunk_index"] = idx
            results[idx] = r
            completed += 1
            if progress_bar is not None:
                progress_bar.progress(completed / total, text=f"Analyzed {completed}/{total} segments...")
    return results


def summarize_document_results(results: list) -> dict:
    valid = [r for r in results if r and "_error" not in r]
    errors = [r for r in results if r and "_error" in r]
    n = len(valid)
    if n == 0:
        return {"n_analyzed": 0, "n_errors": len(errors)}

    orientation_counts, activity_counts, challenge_counts = {}, {}, {}
    friction_pairs = {}

    for r in valid:
        ori = _clean_enum((r.get("main_orientation") or "")).upper()
        act = _clean_enum((r.get("main_activity") or "")).upper()
        chal = derive_potential_challenge(act)
        opp = _clean_enum((r.get("likely_opposing_orientation") or "")).upper()

        if ori:
            orientation_counts[ori] = orientation_counts.get(ori, 0) + 1
        if act:
            activity_counts[act] = activity_counts.get(act, 0) + 1
        if chal:
            challenge_counts[chal] = challenge_counts.get(chal, 0) + 1
        if ori in ORIENTATIONS and opp in ORIENTATIONS:
            pair = tuple(sorted([ori, opp]))
            friction_pairs[pair] = friction_pairs.get(pair, 0) + 1

    predominant_orientation = max(orientation_counts, key=orientation_counts.get) if orientation_counts else None
    predominant_activity = max(activity_counts, key=activity_counts.get) if activity_counts else None
    predominant_challenge = max(challenge_counts, key=challenge_counts.get) if challenge_counts else None

    return {
        "n_analyzed": n,
        "n_errors": len(errors),
        "orientation_counts": orientation_counts,
        "activity_counts": activity_counts,
        "challenge_counts": challenge_counts,
        "friction_pairs": friction_pairs,
        "predominant_orientation": predominant_orientation,
        "predominant_activity": predominant_activity,
        "predominant_challenge": predominant_challenge,
    }


def build_narrative_summary(summary: dict, intervention_type_key: str = None) -> str:
    n = summary.get("n_analyzed", 0)
    if n == 0:
        return "No segments could be analyzed."

    ori_counts = summary["orientation_counts"]
    chal_counts = summary["challenge_counts"]
    pred_ori = summary.get("predominant_orientation")
    pred_chal = summary.get("predominant_challenge")

    def pct(cnt):
        return round(cnt / n * 100, 1)

    lines = []

    if pred_ori:
        ori_meta = ORIENTATIONS.get(pred_ori, {})
        lines.append(
            f"Across **{n}** analyzed segments, the predominant future-making orientation is "
            f"**{pred_ori}** ({pct(ori_counts[pred_ori])}% of segments), "
            f"reflecting a *{ori_meta.get('narrative','')}* -- \"{ori_meta.get('tagline','')}\""
        )

    sorted_ori = sorted(ori_counts.items(), key=lambda x: -x[1])
    ori_dist = ", ".join(f"{k} {pct(v)}%" for k, v in sorted_ori)
    lines.append(f"**Orientation distribution:** {ori_dist}.")

    if pred_chal and pred_chal != "N/A":
        chal_meta = CHALLENGES.get(pred_chal, {})
        lines.append(
            f"The predominant potential future-making challenge is "
            f"**{chal_meta.get('label', pred_chal)}** "
            f"({pct(chal_counts[pred_chal])}% of segments): {chal_meta.get('description','')}."
        )

    significant_orientations = [k for k, v in ori_counts.items() if pct(v) >= 15]
    if len(significant_orientations) >= 3:
        lines.append(
            "High Fragile Futures risk: at least three orientations each represent "
            "15%+ of the corpus. This fragmented landscape suggests multiple, "
            "volatile, and conflicting preferred futures are likely co-existing, "
            "interfering with actualization of the prescribed future -- "
            "orientation-specific strategies for each major group are likely necessary."
        )
    elif len(significant_orientations) == 2:
        lines.append(
            "Moderate Fragile Futures risk: two orientations dominate the corpus, "
            "suggesting the prescribed future is likely to face organized contestation "
            "from a substantial minority alongside majority support/acceptance."
        )
    else:
        lines.append(
            "Lower Fragile Futures risk: one orientation clearly dominates, "
            "suggesting relatively more aligned sensemaking around the prescribed "
            "future -- though minority voices should still be monitored, as they may "
            "still generate localized Convoluted Evaluations, Confrontational "
            "Negotiations, or Competing Enactments."
        )

    if intervention_type_key and intervention_type_key in INTERVENTION_TYPES:
        it = INTERVENTION_TYPES[intervention_type_key]
        if it.get("note"):
            lines.append(
                f"**Intervention type context** ({intervention_type_key.split(' (')[0]}, "
                f"{it['scope']} scope / {it['prescriptiveness']} prescriptive): {it['note']}"
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


def build_results_dataframe(results: list) -> pd.DataFrame:
    """Builds a compact overview dataframe AND includes the full
    rationale text fields, so a CSV export gives complete data even
    if a user does not use the interactive rationale explorer."""
    rows = []
    for r in results:
        if not r:
            continue
        if "_error" in r:
            rows.append({
                "segment": r.get("_chunk_index", ""),
                "text_preview": (r.get("_chunk_text", "")[:120] + "...") if r.get("_chunk_text") else "",
                "orientation": "ERROR", "activity": "", "subtype": "",
                "potential_challenge": "", "likely_opposing_orientation": "",
                "orientation_rationale": "", "activity_rationale": "",
                "potential_challenge_rationale": "", "error": r.get("_error", "")
            })
            continue
        act = _clean_enum((r.get("main_activity") or "")).upper()
        rows.append({
            "segment": r.get("_chunk_index", ""),
            "text_preview": (r.get("_chunk_text", "")[:120] + "...") if r.get("_chunk_text") else "",
            "orientation": _clean_enum((r.get("main_orientation") or "")).upper(),
            "activity": act,
            "subtype": _clean_enum((r.get("activity_subtype") or "")).upper(),
            "potential_challenge": CHALLENGES.get(derive_potential_challenge(act), {}).get("label", ""),
            "likely_opposing_orientation": _clean_enum((r.get("likely_opposing_orientation") or "")).upper(),
            "orientation_rationale": r.get("orientation_rationale", ""),
            "activity_rationale": r.get("activity_rationale", ""),
            "potential_challenge_rationale": r.get("potential_challenge_rationale", ""),
            "error": ""
        })
    return pd.DataFrame(rows)


def show_document_summary(results: list, prescribed_future: str, intervention_type_key: str = None):
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

    if n_errors:
        st.warning(f"{n_errors} segment(s) failed to analyze and were excluded from the summary.")

    st.markdown("### Executive Summary")
    st.markdown(build_narrative_summary(summary, intervention_type_key))

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### Orientation Distribution")
        render_pct_bars(summary["orientation_counts"], ORIENTATIONS, n)
    with col2:
        st.markdown("#### Activity Distribution")
        render_pct_bars(summary["activity_counts"], ACTIVITY_META, n)
    with col3:
        st.markdown("#### Potential Challenge Distribution")
        render_pct_bars(summary["challenge_counts"], CHALLENGES, n, label_key_name="label")

    st.markdown("---")
    st.markdown("### Most Frequent Likely Friction Pairs")
    st.caption(
        "These pairs indicate which orientations, if they encountered each other "
        "in a real exchange, would most likely generate Fragile Futures dynamics."
    )
    friction_pairs = summary.get("friction_pairs", {})
    if friction_pairs:
        sorted_pairs = sorted(friction_pairs.items(), key=lambda x: -x[1])
        for pair, cnt in sorted_pairs[:6]:
            o1, o2 = pair
            pct_val = round(cnt / n * 100, 1)
            st.markdown(f"- **{o1}** vs. **{o2}**: {cnt} segments ({pct_val}%)")
    else:
        st.caption("No friction pairs identified.")

    st.markdown("---")
    st.markdown("### Recommended Focus Areas")
    top_orientations = sorted(summary["orientation_counts"].items(), key=lambda x: -x[1])[:2]
    policy_tab, manager_tab = st.tabs(["Policy Focus", "Managerial Focus"])

    with policy_tab:
        for ori, cnt in top_orientations:
            guidance = POLICY_GUIDANCE.get(ori, {})
            cfg = ORIENTATIONS.get(ori, {})
            pct_val = round(cnt / n * 100, 1)
            st.markdown(f"**{ori}** ({pct_val}% of segments) -- \"{cfg.get('tagline','')}\"")
            st.markdown(f"*General implications:* {guidance.get('implications','--')}")
            st.markdown(f"*Monitor for:* {guidance.get('monitor','--')}")
            st.markdown(f"*Objective:* {guidance.get('objective','--')}")
            for inst in guidance.get("instruments", []):
                st.markdown(f"- {inst}")
            st.markdown("")

    with manager_tab:
        for ori, cnt in top_orientations:
            guidance = MANAGER_GUIDANCE.get(ori, {})
            cfg = ORIENTATIONS.get(ori, {})
            pct_val = round(cnt / n * 100, 1)
            st.markdown(f"**{ori}** ({pct_val}% of segments) -- \"{cfg.get('tagline','')}\"")
            st.markdown(f"*General implications:* {guidance.get('implications','--')}")
            st.markdown(f"*Monitor for:* {guidance.get('monitor','--')}")
            st.markdown(f"*Objective:* {guidance.get('objective','--')}")
            for interv in guidance.get("interventions", []):
                st.markdown(f"- {interv}")
            avoid_list = guidance.get("avoid", [])
            if avoid_list:
                st.markdown(f"*Avoid:* {', '.join(avoid_list)}")
            st.markdown("")
        if len(top_orientations) >= 2:
            st.info(CROSS_ORIENTATION_WARNING)

    st.markdown("---")
    st.markdown("### Segment-Level Detail")
    df = build_results_dataframe(results)
    display_cols = ["segment", "text_preview", "orientation", "activity",
                     "subtype", "potential_challenge", "likely_opposing_orientation"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols] if display_cols else df, use_container_width=True, height=350)

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download full results as CSV (includes complete rationale text)",
        data=csv_bytes,
        file_name="future_making_document_analysis.csv",
        mime="text/csv"
    )

    st.markdown("---")
    st.markdown("### Segment Rationale Explorer")
    st.caption(
        "Select an individual segment below to see its full orientation "
        "rationale, activity rationale, and challenge rationale, presented "
        "the same way as in the single-comment analysis view."
    )

    valid_indexed = [(i, r) for i, r in enumerate(results) if r and "_error" not in r]
    if valid_indexed:
        option_labels = [
            f"Segment {i + 1}: {r.get('_chunk_text', '')[:90]}..."
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
        show_results(chosen_result, prescribed_future)
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


def show_results(result: dict, prescribed_future: str):
    orientation = _clean_enum((result.get("main_orientation") or "")).upper().strip()
    main_act    = _clean_enum((result.get("main_activity") or "")).upper().strip()
    act_sub     = _clean_enum((result.get("activity_subtype") or "N/A")).upper().strip()

    challenge = derive_potential_challenge(main_act)
    chg = CHALLENGES.get(challenge, CHALLENGES["N/A"])

    st.markdown(f"""
    <div style="background:#EBF5FB;border-left:5px solid #2980B9;border-radius:8px;
                padding:12px 18px;margin-bottom:16px;">
        <strong style="color:#2980B9;">Prescribed Future Analyzed:</strong><br>
        <em style="color:#333;">{prescribed_future}</em>
    </div>
    """, unsafe_allow_html=True)

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
            <p style="color:#555;margin:4px 0 3px;font-size:12px;"><strong>Main Future-Making Activity</strong></p>
            <span style="background:{sub_cfg.get('bg','#f5f5f5')};border:1.5px solid {sub_cfg.get('color','#555')};
                         color:{sub_cfg.get('color','#555')};border-radius:12px;
                         padding:3px 10px;font-weight:bold;font-size:12px;">
                -> {act_sub}
            </span>
            <p style="color:#777;margin:8px 0 0;font-size:11px;font-style:italic;">
                {ameta.get('definition','')[:180]}...
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="background:{chg['bg']};border-left:6px solid {chg['color']};
                    border-radius:10px;padding:16px 18px;min-height:230px;">
            <h3 style="color:{chg['color']};margin:0;font-size:20px;">{chg['label']}</h3>
            <p style="color:#555;margin:4px 0 3px;font-size:12px;"><strong>Potential Challenge Contribution</strong></p>
            <p style="color:#999;margin:0 0 4px;font-size:10px;">(if this comment meets an opposing orientation, Fragile Futures risk)</p>
            <p style="color:#777;margin:3px 0;font-size:11px;">{chg['description']}</p>
        </div>
        """, unsafe_allow_html=True)

    opp_ori = _clean_enum((result.get("likely_opposing_orientation") or "")).upper()
    opp_cfg = ORIENTATIONS.get(opp_ori)
    if opp_cfg:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:#FFF8F0;border:2px dashed #E67E22;border-radius:10px;
                    padding:16px 18px;">
            <h4 style="color:#E67E22;margin:0 0 8px;font-size:16px;">
                Likely Friction Point
            </h4>
            <p style="font-size:13px;color:#555;margin:0 0 6px;">
                If this comment met an opposing consumer, it would most likely clash with a
                <strong style="color:{opp_cfg['color']};">{opp_ori}</strong>
                orientation, a dynamic that could contribute to Fragile Futures.
            </p>
            <p style="font-size:12px;color:#777;font-style:italic;margin:0;">
                "{result.get('potential_challenge_rationale','--')}"
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab_ori, tab_act, tab_chg = st.tabs(["Orientation Rationale", "Activity Rationale", "Challenge Rationale"])

    with tab_ori:
        st.markdown("**Why this orientation? (applied coding criteria)**")
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
        sec = result.get("secondary_activities", [])
        if sec:
            st.markdown(f"**Secondary activities also present (informational):** {', '.join(sec)}")
        st.markdown("---")
        st.markdown("**Coding Criteria Applied**")
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
        st.markdown("**How could this comment contribute to a future-making challenge (Fragile Futures)?**")
        st.write(result.get("potential_challenge_rationale", "--"))
        st.caption(
            f"Deterministic mapping applied: {main_act} -> {chg['label']}."
        )

    st.markdown("---")
    st.markdown("## Policy and Managerial Implications")
    policy_tab, manager_tab = st.tabs(["Policy Roadmap", "Managerial Roadmap"])

    with policy_tab:
        policy = result.get("policy_recommendations", {}) or {}
        st.markdown(f"**Most Relevant Step:** {policy.get('step','--')}")
        st.markdown(f"**Policy Objective:** {policy.get('objective','--')}")
        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown("**Recommended Policy Instruments**")
            for inst in policy.get("instruments", []) or []:
                st.markdown(f"- {inst}")
        with pc2:
            st.markdown("**Additional Actions**")
            for action in policy.get("additional_actions", []) or []:
                st.markdown(f"- {action}")
        with st.expander("Full Policy Roadmap (7 Steps)"):
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
        manager = result.get("manager_recommendations", {}) or {}
        st.markdown(f"**Most Relevant Step:** {manager.get('step','--')}")
        st.markdown(f"**Managerial Objective:** {manager.get('objective','--')}")
        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown("**Recommended Interventions**")
            for interv in manager.get("interventions", []) or []:
                st.markdown(f"- {interv}")
        with mc2:
            st.markdown("**Avoid**")
            for av in manager.get("avoid", []) or []:
                st.markdown(f"- {av}")
        st.markdown("**Messaging Tip**")
        st.info(manager.get("messaging_tip", "--"))
        with st.expander("Full Managerial Roadmap (6 Steps)"):
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
        "Purpose: tells the model whether this intervention is narrow or "
        "broad in scope, and how prescriptive it is. The model uses this to "
        "calibrate which future-making challenges are more likely (e.g., "
        "Bounded interventions tend to generate Convoluted Evaluations, "
        "Confrontational Negotiations, AND Competing Enactments "
        "simultaneously; Open interventions tend to generate more Convoluted "
        "Evaluations and Expander critique). If you select a type, it is "
        "appended to your prescribed future text before the analysis runs."
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
            "without this contextual calibration."
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
    st.title("Future-Making Orientation Analyzer")
    render_breadcrumb("Home")
    st.markdown(f"""
    Identify **future-making orientations**, **activities**, and **potential
    challenges** -- either for a single comment, or aggregated across an
    entire document or corpus -- grounded in the coding criteria of a
    consumer research framework validated across domains (Zero Emission
    Vehicles and AI-integrated healthcare).

    *Based on:* **"{PAPER_TITLE}"**
    """)
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
        render_breadcrumb("Home", MODE_SINGLE_LABEL)

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
        input_method = st.radio(
            "Input method:",
            ["Type or paste text", "Try a generalization test", "Upload a .txt file"],
            horizontal=True
        )

        comment = ""
        if input_method == "Type or paste text":
            selected_ex = st.selectbox(
                "Or try a built-in coded example:", list(EXAMPLES.keys())
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
        elif input_method == "Try a generalization test":
            selected_test = st.selectbox(
                "Choose a test comment not used to build the app:",
                list(GENERALIZATION_TESTS.keys())
            )
            test_data = GENERALIZATION_TESTS.get(selected_test, {"comment": "", "note": "", "prescribed": ""})
            if test_data.get("note"):
                st.info(test_data['note'])
            if test_data.get("prescribed") and st.button("Use suggested prescribed future for this test", type="secondary"):
                st.session_state["pf_prefill"] = test_data["prescribed"]
                st.rerun()
            comment = st.text_area("Comment:", value=test_data.get("comment", ""), height=150, label_visibility="collapsed")
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
            "Upload or paste a larger text (e.g., forum export, survey open-ends, "
            "public consultation submissions, social media export, or a policy "
            "document) to get an aggregate assessment of future-making "
            "orientations, activities, and potential challenges across many "
            "segments at once, plus a full rationale explorer for individual "
            "segments."
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
                        st.caption(f"[{i+1}] {c[:200]}{'...' if len(c) > 200 else ''}")
            else:
                st.warning(
                    "No analyzable segments found with the current segmentation "
                    "option. Try a different segmentation method, or paste more "
                    "text below."
                )

            # ── STEP 4: RUN ANALYSIS -- always rendered once text is provided ──
            render_breadcrumb("Home", MODE_DOC_LABEL, "Step 4: Run Analysis")
            st.markdown("### Step 4 -- Run Analysis")

            max_possible = max(1, min(len(chunks), 300)) if chunks else 1
            default_val = min(30, max_possible) if chunks else 1
            max_chunks = st.slider(
                "Maximum segments to analyze (controls cost and time)",
                min_value=1, max_value=max_possible, value=default_val,
                disabled=(len(chunks) == 0)
            )
            est_seconds = round(max_chunks / DOC_MAX_WORKERS * 2.5)
            est_cost = round(max_chunks * 0.00075, 3)
            st.caption(
                f"Estimated time: ~{est_seconds}s | API calls: {max_chunks} "
                f"(parallelized, {DOC_MAX_WORKERS} at a time) | "
                f"Estimated cost: ~${est_cost}"
            )

            run_doc_analysis = st.button(
                "Analyze Document", type="primary", use_container_width=True,
                disabled=(not api_key or len(chunks) == 0)
            )
            if not api_key:
                st.warning("Please configure your OpenAI API key above.")
            if not chunks:
                st.caption("The Analyze Document button is disabled until at least one valid segment is found.")

            if run_doc_analysis and chunks:
                final_pf_doc = augment_prescribed_future(prescribed_future_doc, it_key_doc)
                chunks_to_run = chunks[:max_chunks]
                progress_bar = st.progress(0, text="Starting analysis...")
                doc_results = analyze_document(
                    chunks_to_run, final_pf_doc, api_key, progress_bar
                )
                progress_bar.empty()
                st.session_state["doc_results"] = doc_results
                st.session_state["doc_prescribed_future"] = final_pf_doc
                st.session_state["doc_intervention_type"] = it_key_doc

        if "doc_results" in st.session_state:
            st.divider()
            render_breadcrumb("Home", MODE_DOC_LABEL, "Step 5: Results")
            st.markdown("## Document-Level Analysis")
            show_document_summary(
                st.session_state["doc_results"],
                st.session_state.get("doc_prescribed_future", PF_EV),
                st.session_state.get("doc_intervention_type")
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
            "Internal quality-control tool. Not needed for regular use. "
            "Run this after any change to the model, prompt, or temperature "
            "to confirm the app still matches the intended coding categories."
        )
        if st.button("Run Validation Suite"):
            if not api_key:
                st.warning("Configure your API key above first.")
            else:
                with st.spinner("Running validation across all built-in examples..."):
                    report = run_validation_suite(api_key)
                if report["results"]:
                    st.metric("Overall Accuracy", f"{report['overall_accuracy']*100:.1f}%")
                    for r in report["results"]:
                        status = "PASS" if r["match"] else "FAIL"
                        with st.expander(f"[{status}] {r['example']}"):
                            st.write("**Expected:**", r["expected"])
                            st.write("**Predicted:**", r["predicted"])
                            if r.get("error"):
                                st.error(r["error"])
                else:
                    st.info("No labeled examples found to validate.")


if __name__ == "__main__":
    main()
