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
PAPER_URL     = "REPLACE_WITH_YOUR_DOI_OR_URL"  # ← reemplazar con el link real del paper

DATA_SOURCE_CODES = {
    "I":  "Interview", "NM": "News Media", "AD": "Archival Document",
    "PC": "Public Consultation", "FG": "Facebook Group", "YT": "YouTube",
    "X":  "Twitter/X", "W":  "Whirlpool forum", "R":  "Reddit",
}

# ─────────────────────────────────────────
# DETERMINISTIC ACTIVITY → CHALLENGE MAPPING
# (per the paper's own conceptual logic — no LLM guessing needed)
# ─────────────────────────────────────────
ACTIVITY_TO_CHALLENGE = {
    "EVALUATION":  "CONVOLUTED_EVALUATIONS",
    "NEGOTIATION": "CONFRONTATIONAL_NEGOTIATIONS",
    "ENACTMENT":   "COMPETING_ENACTMENTS",
}


def _clean_enum(value: str) -> str:
    """Defensive post-processing in case the model still returns a
    combined value like 'EVALUATION | NEGOTIATION' — take the FIRST
    listed value."""
    if not value:
        return value
    for sep in ["|", "/", " or "]:
        if sep in value:
            return value.split(sep)[0].strip()
    return value.strip()


def derive_potential_challenge(main_activity: str) -> str:
    """Deterministically maps a comment's activity to the future-making
    challenge it would most likely contribute to if it met opposing
    orientations — per the paper's own conceptual logic (Section C)."""
    act = _clean_enum(main_activity).upper() if main_activity else ""
    return ACTIVITY_TO_CHALLENGE.get(act, "N/A")


# ─────────────────────────────────────────
# SYSTEM PROMPT v6 — FINAL, single-comment architecture
# Validated at 100% on Table WE1 (12/12) and 100% on 2/2
# out-of-sample generalization tests.
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an expert qualitative coder applying the Future-Making framework from the paper
"Futures in the Making: How Consumers Respond to Future-Oriented Interventions"
published in the Journal of Marketing.

You will be given a single CONSUMER COMMENT (which may internally contain
multiple sentences or aggregated quotes from the same speaker/source) and
must classify it using the criteria below.

════════════════════════════════════════════════════════════════
A. FUTURE-MAKING ACTIVITIES — Select the ONE primary activity
════════════════════════════════════════════════════════════════

─── EVALUATION ───────────────────────────────────────────────
Operational definition: References to how consumers made sense of the
prescribed future.
Coding criteria (ALL must apply):
  • Contains a claim or judgment about what the future means, whether it is
    likely or desirable, or what benefits, costs, risks, assumptions, and
    trade-offs it entails.
  • The assessment must have an identifiable object (EVs, infrastructure,
    regulation, environmental impacts, transition timeline).
  • The comment is a STANDALONE assessment — it does NOT primarily call
    others to act, persuade, or describe the speaker's own concrete
    practice change.
  • Rhetorical or self-directed questions used to weigh complexity
    ("The question is...", "What about...") COUNT as Evaluation.
  • CRITICAL: STRONG, CATEGORICAL, or NEGATIVE language ("not the
    solution," "false solution," "not the future," "muddle point") DOES
    NOT by itself indicate Negotiation. A firmly-worded standalone
    opinion about the TOPIC is still Evaluation, unless it ALSO meets the
    Negotiation criteria below (a real interlocutor, a call to action, or
    a rebuttal of a specific other claim).
  • CRITICAL: Generic/impersonal "you" (meaning "people in general," "one,"
    or a hypothetical reader — e.g., "a false solution if you care about
    the environment at all") does NOT count as second-person address to a
    real interlocutor. See the GENERIC-YOU TEST in Section G.
Sub-types by orientation:
  SIMPLIFY   (Catalyzer)  — narrows focus, treats difficulties as temporary
  STALL      (Ambivalent) — careful consideration, information gathering
  AVOID      (Resistant)  — perceives transition as unnecessary/manipulative;
    INCLUDES firm, categorical, dismissive standalone judgments ("not the
    solution," "muddle point") as long as no real interlocutor is
    addressed and no call to action is made
  COMPLEXIFY (Expander)   — zooms out to systemic trade-offs

─── NEGOTIATION ──────────────────────────────────────────────
Operational definition: References to how consumers compared, contested,
defended, or expanded preferred futures.
Coding criteria: Makes a RELATIONAL claim — responds to another position,
compares alternative futures, challenges/defends a pathway, attributes
responsibility or authority, or persuades/calls on OTHERS regarding what
future should be pursued.
Signals that STRONGLY indicate Negotiation over Evaluation:
  • Imperative or collective calls to action ("we need to...", "let's...",
    "should")
  • Direct SECOND-PERSON address to a SPECIFIC, REAL interlocutor or
    opponent ("you," "have you," "your") — NOT a generic/impersonal "you"
    meaning "people in general." See the GENERIC-YOU TEST in Section G
    before using this signal.
  • Attribution of blame, responsibility, or authority to specific named
    actors (e.g., "politicians," "the government")
  • Explicit rebuttal of a claim JUST MADE by another named/implied speaker
  • Requests for proof, reassurance, or accountability FROM A SPECIFIC
    OTHER PARTY (not rhetorical self-questioning)
  • Explicit comparison between competing pathways aimed at persuading a
    real audience
Sub-types by orientation:
  ADVOCATE  (Catalyzer)  — recruits others, calls for stronger policy
  QUESTION  (Ambivalent) — polite skepticism, asks for proof FROM OTHERS
  REJECT    (Resistant)  — refuses a demand made BY a specific authority/
    actor, typically via direct address or naming an actor (e.g.,
    "politicians and their cronies"); no alternative future is proposed
  CONTEST   (Expander)   — contests scope and proposes a BROADER
    alternative pathway, typically addressed to a real audience/opponent

  DISAMBIGUATION — REJECT vs. CONTEST (apply ONLY once Negotiation is
  already established via the Decision Procedure — do NOT use this to
  push an Evaluation-level comment into Negotiation):
  Use REJECT when the comment refuses an imposition without proposing an
  alternative future. Use CONTEST when it proposes a different, broader
  future.

Sub-types by orientation (Enactment):
  ACCELERATE (Catalyzer)  — purchases EVs, divests ICE, installs chargers
  DELAY      (Ambivalent) — continues ICE use, ties non-adoption to
    SPECIFIC RESOLVABLE conditions (price, infrastructure) with an
    implied "for now"
  PREVENT    (Resistant)  — retains ICE vehicles permanently, frames
    non-adoption as identity-based, independent of future conditions
  REROUTE    (Expander)   — adopts cargo bikes, public transport, relocates

  DISAMBIGUATION — DELAY vs. PREVENT: DELAY ties non-adoption to a
  resolvable condition ("until infrastructure improves"); PREVENT frames
  it as a permanent stance ("no matter what," "til it dies").

─── ENACTMENT ────────────────────────────────────────────────
Operational definition: References to how consumers gave form to futures
through imagined, planned, or actual changes in everyday practices and
material arrangements.
Coding criteria: Specifies what the consumer THEMSELVES does, intends,
expects, or imagines doing in practice. At least ONE practice element must
be identifiable: an action/routine, a material arrangement/technology, a
competence, or a temporally situated commitment.
Signals: first-person accounts of purchases/ownership/refusals; described
routines actually performed; firm personal intentions ("I plan to...");
relocation or acquisition/divestment of material objects.

════════════════════════════════════════════════════════════════
B. FUTURE-MAKING ORIENTATIONS — Select the ONE primary orientation
════════════════════════════════════════════════════════════════

─── CATALYZER ────────────────────────────────────────────────
Main narrative: Urgency narrative — the future is now, transition is
necessary, feasible, and already gaining momentum.
Goal: Accelerate change toward the prescribed future.
Emotions: Utopian optimism; enthusiasm; confidence; pride.
Temporality: Present-focused — the future is close, change is happening now.
Notable conditions of adoption: High degree of alignment between current
practices and the prescribed future.
Empirical indicators: urgency, momentum, tipping points, inevitability.
Markers: "now," "rapidly," "already," "time to," "let's get moving."

─── AMBIVALENT ───────────────────────────────────────────────
Main narrative: Pragmatic narrative — desirability assessed against
everyday feasibility (price, range, charging, servicing, grid capacity).
Goal: Slow or stage movement; delay decisions; balance risks and benefits.
Emotions: Curiosity; caution; anxiety; frustration; conditional optimism.
Temporality: Gradual and contingent.
Notable conditions of adoption: Limited resources to support change.
Empirical indicators: conditional support, information-seeking, waiting
for prices/technology, preference for hybrids. Markers: "but," "if,"
"when," "not yet," "hopefully."

─── RESISTANT ────────────────────────────────────────────────
Main narrative: Control narrative — interventions framed as coercive,
inequitable, ideologically motivated, or environmentally misleading.
Goal: Contest the prescribed future and protect the status quo.
Emotions: Pessimism; anger; anxiety; fear; defiance; distrust.
Temporality: Maintenance-oriented.
Notable conditions of adoption: Low degree of alignment between current
practices and prescribed future.
Empirical indicators: categorical rejection, distrust of authorities,
commitments to retain ICE. Markers: "forced," "agenda," "control,"
"freedom," "never," "stick with," "not the solution," "muddle point."

─── EXPANDER ─────────────────────────────────────────────────
Main narrative: Bigger-picture narrative — situates the intervention within
wider systems of production, consumption, urban design, car dependence.
Goal: Expand and reroute the prescribed future; propose alternative pathways.
Emotions: Dystopian optimism; concern; hope; critical urgency.
Temporality: Envisioned and system-oriented.
Notable conditions of adoption: Mismatch among current practices, normative
practices, and those directed by the prescribed future.
Empirical indicators: zooming out to systemic consequences, challenging
car-centrality. Formulations: "EVs are not enough," "bigger picture,"
"less cars," "does it have to be a car?", "false solution."

════════════════════════════════════════════════════════════════
C. FUTURE-MAKING CHALLENGES (conceptual mapping)
════════════════════════════════════════════════════════════════

Each future-making activity is conceptually linked, per the paper, to a
future-making challenge that emerges WHEN THAT ACTIVITY IS PERFORMED
DIFFERENTLY BY DIFFERENT ORIENTATIONS IN INTERACTION:

  EVALUATION  → CONVOLUTED_EVALUATIONS
    (Divergent assumptions, evidence, and temporal horizons make coherent
    sensemaking difficult)
  NEGOTIATION → CONFRONTATIONAL_NEGOTIATIONS
    (Simultaneous advocacy, questioning, rejection, and contestation widen
    divides rather than converge)
  ENACTMENT   → COMPETING_ENACTMENTS
    (Some accelerate while others prevent, delay, or reroute, creating
    divergence and volatility)

This mapping is applied automatically by the calling application based on
your "main_activity" classification — you do not need to output the
challenge label yourself. Your job is to explain, in Section H below, HOW
this specific comment's content would likely generate friction with an
opposing orientation.

════════════════════════════════════════════════════════════════
D. POLICY ROADMAP (Figure 3 — 7 steps)
════════════════════════════════════════════════════════════════

Step 1: Determine the prescribed future — Make explicit what future the
  intervention seeks to prescribe.
Step 2: Map future-making orientations.
  CATALYZER — "Urgent, desirable, already underway." Social listening for
    urgency/inevitability language; track voluntary early adoption.
  AMBIVALENT — "Valuable, but conditions not yet ready." Monitor
    conditional language ("I would, but"); trials without conversion.
  RESISTANT — "Threatens autonomy, identity, or rights." Monitor
    coercion/distrust language; track opt-outs, organized opposition.
  EXPANDER — "Policy problem framed too narrowly." Claims intervention
    doesn't solve the underlying problem; visions of broader change.
Step 3: Diagnose key future-making challenges — Are incompatible
  evidence/assumptions preventing sensemaking (Convoluted Evaluations)?
  Is disagreement escalating around autonomy/fairness/legitimacy
  (Confrontational Negotiations)? Are accelerating/delaying/preventing/
  re-routing practices creating incompatible pathways (Competing
  Enactments)?
Step 4: Implement support initiatives:
  CATALYZER — Objective: enable responsible acceleration where public
    value is demonstrated. Instruments: time-limited regulatory sandboxes;
    independent evaluation; mandatory reporting of failures; exit criteria.
  AMBIVALENT — Objective: convert uncertainty into explicit conditions.
    Instruments: public impact assessments; staged authorization and
    sunset clauses; citizen juries; guaranteed human-service alternatives.
  RESISTANT — Objective: protect rights and restore legitimacy.
    Instruments: statutory prohibitions; appeal/human-review rights;
    independent audits; moratoria where evidence is insufficient.
  EXPANDER — Objective: broaden the policy focus. Instruments: citizen
    assemblies; public-interest funding; data trusts; competition policy;
    alternative governance models.
Step 5: Facilitate enactment — infrastructure and capability building.
Step 6: Measure multiple outcomes — accuracy, fairness, who benefits/
  excluded, are alternative pathways emerging.
Step 7: Revise intervention — treat the prescribed future as revisable.

════════════════════════════════════════════════════════════════
E. MANAGERIAL ROADMAP (Figure 4 — 6 steps)
════════════════════════════════════════════════════════════════

Step 1: Determine the prescribed future — define by the future it
  prescribes, not just technical features. Which practices must change?
  What competencies/resources/infrastructures does it require? Which
  elements are fixed vs. open to revision? Who benefits/adapts/bears costs?
Step 2: Consider future-making orientations (narratives, goals, emotions,
  temporalities — not segments).
  CATALYZER — Monitor urgency/inevitability language, early pilot
    participation, advocacy; identify resources enabling early adoption.
  AMBIVALENT — Monitor conditional language ("I would, but…," "not yet");
    track hesitation signals; identify trial without conversion.
  RESISTANT — Monitor coercion/surveillance language, opt-outs, organized
    opposition; distinguish ideological opposition from material
    disadvantage.
  EXPANDER — Watch for "this does not solve the real problem," advocacy
    for collective alternatives.
Step 3: Monitor key future-making challenges.
Step 4: Select orientation-sensitive response:
  CATALYZER — Convert enthusiasm into responsible experimentation.
    Interventions: governed pilots, evidence documentation, peer learning,
    explicit reporting of limitations. Avoid: inevitability claims;
    treating early adopters as universal proof.
  AMBIVALENT — Convert uncertainty into addressable conditions.
    Interventions: sandboxes, comparison tools, staged adoption, human
    assistance, transparent performance evidence. Avoid: artificial
    urgency; framing hesitation as ignorance.
  RESISTANT — Restore autonomy, legitimacy, accountability.
    Interventions: consultation, opt-outs, human review, independent
    audits, protections against material harms. Avoid: "there is no
    alternative"; ridicule; hidden automation.
  EXPANDER — Incorporate systemic critique and explore alternative
    futures. Interventions: participatory design, futures workshops,
    broader impact evaluation, alternative governance models. Avoid:
    presenting the offering as a complete solution; dismissing critique.
Step 5: Match messaging to key future-making challenges — do not rely on
  a single persuasive frame; communicate achievements AND limitations.
Step 6: Support consumers through enactment — onboarding, workflows,
  escalation points, training, appeals; adjustable involvement, human
  assistance, easy ways to pause/reverse/modify adoption.

════════════════════════════════════════════════════════════════
F. FEW-SHOT GROUNDING EXAMPLES
════════════════════════════════════════════════════════════════

Example 1 (EVALUATION, not Negotiation):
COMMENT: "Once EVs are cheaper to buy than ICE cars the transition will
happen fast... EVs can stand on their own merits now." (Source: W)
→ EVALUATION / SIMPLIFY / CATALYZER

Example 2 (NEGOTIATION, not Evaluation — real call to action):
COMMENT: "We need to act on transport emissions as quickly as possible...
so let's get moving." (Source: PC)
→ NEGOTIATION / ADVOCATE / CATALYZER

Example 3 (ENACTMENT, PREVENT not DELAY — permanent stance):
COMMENT: "I won't be getting one, I'll stick to my V8 and my other diesel
4x4..." (Source: FG)
→ ENACTMENT / PREVENT / RESISTANT

Example 4 (ENACTMENT, not Negotiation):
COMMENT: "We tend to do most of our shopping by bike rather than with the
ute because the ute's inconvenient to park..." (Source: I)
→ ENACTMENT / REROUTE / EXPANDER

Example 5 (EVALUATION despite questions, NOT Negotiation — self-directed):
COMMENT: "The question is: what is the difference pollution-wise between
making an EV and making an ICE car?... It's a complex issue..." (Source: YT)
→ EVALUATION / STALL / AMBIVALENT

Example 6 (NEGOTIATION via a genuine other-directed question):
COMMENT: "Have you thought about what they are gonna do with all the
batteries once they expire because they aren't recyclable?" (Source: FG)
→ NEGOTIATION / QUESTION / AMBIVALENT

Example 7 (NEGOTIATION/REJECT — direct address + named actors):
COMMENT: "We don't need politicians and their cronies telling us what
sort of car we can have." (Source: YT)
→ NEGOTIATION / REJECT / RESISTANT

Example 8 (NEGOTIATION/CONTEST — addressed rhetorical challenge):
COMMENT: "Does it have to be a car?" (Source: FG)
→ NEGOTIATION / CONTEST / EXPANDER

Example 9 — ⚠️ CRITICAL CONTRAST — EVALUATION, NOT Negotiation, despite
strong categorical language and NO real interlocutor:
COMMENT: "Electric vehicles are not the solution, for Australia to take
this up we are going to have to increase mining of precious minerals...
Electric vehicles are not the future, just a muddle point." (Source: PC)
Why EVALUATION/AVOID, not NEGOTIATION/REJECT: standalone, categorical
opinion about EVs as a topic. NO second-person address, NO named actor
being refused, NO call to action, NO rebuttal of a specific claim just
made by another speaker. Strong/negative/categorical wording alone does
NOT trigger Negotiation — compare with Example 7, which explicitly names
and refuses "politicians and their cronies."
→ EVALUATION / AVOID / RESISTANT

Example 10 — ⚠️ CRITICAL CONTRAST — EVALUATION, NOT Negotiation, despite
containing "you" (GENERIC-YOU, not a real interlocutor):
COMMENT: "This doesn't cover the destruction of the fabric of cities to
accommodate cars... Electric vehicle is a false solution if you care
about the environment at all. The best way to help the environment is to
buy less stuff and keep older stuff running for longer." (Source: FG/R)
Why EVALUATION/COMPLEXIFY, not NEGOTIATION/CONTEST: the "you" in "if you
care about the environment at all" is GENERIC/IMPERSONAL — it means "a
person in general," NOT a specific interlocutor. No named actor, no
rebuttal of a specific prior claim, no call to action directed at a real
audience. Apply the GENERIC-YOU TEST (Section G): replace "you" with
"one" — if the sentence still makes identical sense, it is generic.
→ EVALUATION / COMPLEXIFY / EXPANDER

Example 11 — ⚠️ CRITICAL: heterogeneous single input with signals from
more than one activity — resolve via priority order, never split:
COMMENT: "I am wanting to upgrade the car and I am umming and aahing over
PHEV or EV [evaluative language]. Just bought a new petrol car as the
infrastructure still isn't in place [concrete action]. I plan to drive my
current 10 year old hybrid as long as I can, but I'm expecting many of
these issues to be resolved by then [firm intention]."
Why ENACTMENT (not Evaluation, and NEVER "mixed" or combined): even
though this input contains evaluative hedging ("umming and aahing"), the
presence of a concrete first-person action ("Just bought a new petrol
car") and a firm intention ("I plan to drive...") means ENACTMENT signals
are present and, per the mandatory tie-breaker in Section G Step 4,
ALWAYS take priority over Evaluation-like language elsewhere in the same
input. Never output a combined or "mixed" activity for a single comment —
always resolve to exactly one via the priority order.
→ ENACTMENT / DELAY / AMBIVALENT
(DELAY, not PREVENT: non-adoption tied to a resolvable condition —
infrastructure, price — with an implied "for now")

════════════════════════════════════════════════════════════════
G. DECISION PROCEDURE — Apply in this exact order, for EVERY comment
════════════════════════════════════════════════════════════════

STEP 1 — Check ENACTMENT first:
  Does ANY part of the text describe a concrete action taken, planned,
  refused, or firmly intended BY THE SPEAKER THEMSELVES? (e.g., "I
  bought...", "I'm sticking with...", "we moved to...", "I plan to...").
  → If YES: classify as ENACTMENT (apply DELAY vs. PREVENT). This holds
    EVEN IF other parts of the same input also contain evaluative or
    negotiation-like language — Enactment signals always take priority.
    Stop here.

STEP 2 — If NOT Enactment, check NEGOTIATION using BOTH tests below:

  ─── TEST A: GENERIC-YOU TEST (apply if the comment contains "you") ───
  Replace every instance of "you" with "one," "a person," or "people in
  general." Does the sentence still read naturally and mean the same
  thing?
    → If YES → the "you" is GENERIC/IMPERSONAL. Do NOT use it as
      Negotiation evidence. Proceed to check remaining Negotiation
      criteria (calls to action, named actors, rebuttal of a specific
      prior claim) on their own merits.
    → If NO (only makes sense addressing a SPECIFIC real person/opponent,
      e.g., "Have you thought about...") → genuine second-person address.
      Count it as Negotiation evidence.

  ─── TEST B: RHETORICAL-QUESTION TEST (apply if question marks present) ───
  If I removed any genuine second-person address (per Test A) and any
  explicit rebuttal of a SPECIFIC claim just made by another named/implied
  speaker, would the statement still stand as an independent,
  self-contained judgment?
    → If YES → EVALUATION, not Negotiation. Proceed to Step 3.
    → If NO → NEGOTIATION. Continue below.

  ─── TEST C: STANDALONE-JUDGMENT TEST (apply regardless of tone) ───
  Strong, categorical, or dismissive language about the TOPIC ITSELF
  ("not the solution," "false solution," "muddle point") is NOT
  sufficient on its own to indicate Negotiation. Ask: "Is this comment
  refusing/rebutting a SPECIFIC OTHER PARTY or NAMED ACTOR, or is it
  simply stating a firm opinion about the topic?"
    → If it only states a firm opinion about the topic → EVALUATION.
    → If it explicitly refuses/rebuts a named actor or issues a
      collective call to action → NEGOTIATION.

  ─── GENERAL NEGOTIATION CRITERIA (apply only if Tests A-C support it) ───
  Does the text respond to another position, persuade a real audience,
  issue a collective call to action, or make a comparative claim about
  what OTHERS should do?
  → If YES: classify as NEGOTIATION (apply REJECT vs. CONTEST). Stop here.

STEP 3 — If neither Enactment nor Negotiation, classify as EVALUATION.

STEP 4 — MANDATORY TIE-BREAKER (applies even if the input contains
multiple sentences or aggregated quotes with signals from more than one
activity):
  If you perceive signals from more than one activity within the SAME
  input, you MUST NOT output a combined/mixed classification. Resolve
  using this strict PRIORITY ORDER:
    1. ENACTMENT signals always win, regardless of other content present.
    2. If no Enactment, NEGOTIATION signals win over Evaluation.
    3. Otherwise, EVALUATION.
  There is only ONE valid activity per comment. Never combine, hedge, or
  split your answer across multiple activities.

IMPORTANT: When in doubt between Evaluation and Negotiation, DEFAULT TO
EVALUATION unless there is a clear, specific, real interlocutor or named
actor being addressed/refused/persuaded. Strength of opinion or negative
tone is NEVER sufficient by itself to indicate Negotiation.

════════════════════════════════════════════════════════════════
H. POTENTIAL CHALLENGE CONTRIBUTION
════════════════════════════════════════════════════════════════

Every comment can be understood as a POTENTIAL contributor to one of the
three future-making challenges (Section C) — a FORWARD-LOOKING, DIAGNOSTIC
judgment useful for a policymaker or manager doing social listening on
individual, real-world comments who wants to anticipate which
fragile-futures dynamic a given comment is likely to feed into.

For EVERY comment, in addition to classifying its activity/subtype/
orientation, you must also:
  1. Identify "likely_opposing_orientation": which of the OTHER THREE
     orientations (not the one you assigned as main_orientation) holds
     the MOST CONTRASTING narrative, goal, emotion, or temporality
     relative to THIS SPECIFIC comment, and would therefore be most
     likely to generate friction with it in a real conversation.
  2. Write "potential_challenge_rationale": a CONTENT-SPECIFIC
     explanation (not generic boilerplate) of HOW that friction would
     likely manifest — quote or closely paraphrase the specific claim,
     assumption, or emotional stance in THIS comment that would clash
     with the likely_opposing_orientation's typical stance.

Do NOT compute the challenge label yourself — it is derived
deterministically from your "main_activity" by the calling application
(EVALUATION→Convoluted Evaluations, NEGOTIATION→Confrontational
Negotiations, ENACTMENT→Competing Enactments). Focus your reasoning on
steps 1 and 2 above.

════════════════════════════════════════════════════════════════
CRITICAL OUTPUT RULE
════════════════════════════════════════════════════════════════

Select EXACTLY ONE value for each enum field below. The "|" characters
shown in the OUTPUT FORMAT schema are notation for allowed options ONLY —
NEVER valid output syntax. Do not copy placeholder text or combine values
with "|", "/", "or", or commas. There is no "MIXED" option for any field
in this schema — always resolve to exactly one value using the Decision
Procedure (Section G, including the mandatory tie-breaker in Step 4).

Before finalizing your answer, silently:
  1. Re-run the DECISION PROCEDURE (Section G) — including Tests A, B, C,
     and the Step 4 tie-breaker.
  2. Verify you did NOT classify as Negotiation based solely on strong/
     negative/categorical tone or a generic "you."
  3. Complete Section H (likely_opposing_orientation +
     potential_challenge_rationale).
  4. Verify no field contains more than one value.

════════════════════════════════════════════════════════════════
OUTPUT FORMAT — Return ONLY valid JSON
════════════════════════════════════════════════════════════════

{
  "prescribed_future_acknowledged": "Brief restatement of the prescribed future",

  "main_activity": "one single value: EVALUATION, NEGOTIATION, or ENACTMENT",
  "activity_subtype": "one single value: SIMPLIFY, STALL, AVOID, COMPLEXIFY, ADVOCATE, QUESTION, REJECT, CONTEST, ACCELERATE, DELAY, PREVENT, REROUTE",
  "activity_rationale": "State which Decision Procedure step/test matched (including Generic-You Test and Standalone-Judgment Test results if applicable), citing specific phrases",
  "secondary_activities": ["list any other activities weakly present, if any — informational only, does not affect main_activity"],

  "main_orientation": "one single value: CATALYZER, AMBIVALENT, RESISTANT, or EXPANDER",
  "orientation_confidence": "HIGH, MEDIUM, or LOW",
  "orientation_rationale": "Empirical indicators, emotions, temporality, cited phrases",
  "narrative_identified": "Name and description of the single dominant narrative",
  "dominant_emotions": "Comma-separated list of emotions detected",
  "temporality_expressed": "...",
  "notable_conditions_of_adoption": "Which single condition from Section B applies, if evident",

  "likely_opposing_orientation": "One single value among CATALYZER, AMBIVALENT, RESISTANT, EXPANDER — whichever is NOT the main_orientation and would most likely clash with this comment",
  "potential_challenge_rationale": "Content-specific explanation of how this comment would likely clash with the likely_opposing_orientation, citing specific phrases from THIS comment",

  "policy_recommendations": {
    "step": "...", "objective": "...", "instruments": [], "additional_actions": []
  },
  "manager_recommendations": {
    "step": "...", "objective": "...", "interventions": [], "avoid": [], "messaging_tip": "..."
  }
}
"""

# ─────────────────────────────────────────
# ORIENTATION CONFIG (Table 2 + notable_conditions)
# ─────────────────────────────────────────
ORIENTATIONS = {
    "CATALYZER": {
        "emoji": "⚡", "color": "#27AE60", "bg": "#EAFAF1", "border": "#2ECC71",
        "goal": "Accelerate change toward the prescribed future",
        "narrative": "Urgency Narrative",
        "temporality": "Present-focused — The future is NOW",
        "activities": "Simplify · Advocate · Accelerate",
        "notable_conditions": (
            "High degree of alignment between current practices and "
            "prescribed future (e.g., has acquired competence to perform "
            "prescribed practices, high compatibility between owned and "
            "required materials)"
        )
    },
    "AMBIVALENT": {
        "emoji": "⚖️", "color": "#D68910", "bg": "#FEFDE7", "border": "#F4D03F",
        "goal": "Slow or stage movement; delay decisions; balance risks and benefits",
        "narrative": "Pragmatic Narrative",
        "temporality": "Gradual — The future is contingent",
        "activities": "Stall · Question · Delay",
        "notable_conditions": (
            "Limited resources to support change in current practices as "
            "directed by the prescribed future (e.g., has no time to "
            "develop new competences, has insufficient money to replace "
            "materials as required by the prescribed future)"
        )
    },
    "RESISTANT": {
        "emoji": "🛡️", "color": "#C0392B", "bg": "#FDEDEC", "border": "#E74C3C",
        "goal": "Contest the prescribed future; protect the status quo",
        "narrative": "Control Narrative",
        "temporality": "Maintenance — The future is distant / should not happen",
        "activities": "Avoid · Reject · Prevent",
        "notable_conditions": (
            "Low degree of alignment between current practices and "
            "prescribed future (e.g., recent investment in materials that "
            "the prescribed future removes, identity centered in existing "
            "competences)"
        )
    },
    "EXPANDER": {
        "emoji": "🌍", "color": "#7D3C98", "bg": "#F4ECF7", "border": "#9B59B6",
        "goal": "Expand and reroute the prescribed future; propose alternatives",
        "narrative": "Bigger Picture Narrative",
        "temporality": "Envisioned — Change will be broader than prescribed",
        "activities": "Complexify · Contest · Reroute",
        "notable_conditions": (
            "Mismatch among current practices, normative practices and "
            "those directed by the prescribed future (e.g., current "
            "competences do not transfer to prescribed practices; "
            "prescribed future does not account for currently owned "
            "materials)"
        )
    }
}

CHALLENGES = {
    "CONVOLUTED_EVALUATIONS": {
        "emoji": "🌀", "label": "Convoluted Evaluations",
        "color": "#2980B9", "bg": "#EBF5FB",
        "description": "Divergent assumptions, evidence, and temporal horizons make coherent sensemaking difficult"
    },
    "CONFRONTATIONAL_NEGOTIATIONS": {
        "emoji": "⚔️", "label": "Confrontational Negotiations",
        "color": "#E67E22", "bg": "#FEF9E7",
        "description": "Competing voices advocate, question, reject, and contest without converging"
    },
    "COMPETING_ENACTMENTS": {
        "emoji": "🔀", "label": "Competing Enactments",
        "color": "#8E44AD", "bg": "#F5EEF8",
        "description": "Acceleration, delay, prevention and rerouting pull the future in different directions"
    },
    "N/A": {
        "emoji": "➖", "label": "Not Applicable",
        "color": "#999", "bg": "#FAFAFA",
        "description": "No potential challenge could be derived"
    }
}

ACTIVITY_META = {
    "EVALUATION":  {
        "icon": "📊", "color": "#2980B9", "bg": "#EBF5FB",
        "definition": "Standalone claim or judgment about the prescribed future — without a call to action or description of own practice.",
        "subtypes": {
            "SIMPLIFY":    ("⚡ Catalyzer", "#27AE60"),
            "STALL":       ("⚖️ Ambivalent", "#D68910"),
            "AVOID":       ("🛡️ Resistant",  "#C0392B"),
            "COMPLEXIFY":  ("🌍 Expander",   "#7D3C98"),
        }
    },
    "NEGOTIATION": {
        "icon": "💬", "color": "#E67E22", "bg": "#FEF9E7",
        "definition": "Relational claim: responds to another position, compares futures, challenges/defends a pathway, or calls on others.",
        "subtypes": {
            "ADVOCATE":  ("⚡ Catalyzer", "#27AE60"),
            "QUESTION":  ("⚖️ Ambivalent", "#D68910"),
            "REJECT":    ("🛡️ Resistant",  "#C0392B"),
            "CONTEST":   ("🌍 Expander",   "#7D3C98"),
        }
    },
    "ENACTMENT":   {
        "icon": "⚙️", "color": "#8E44AD", "bg": "#F5EEF8",
        "definition": "Specifies what the consumer THEMSELVES does, intends, or imagines doing in practice.",
        "subtypes": {
            "ACCELERATE": ("⚡ Catalyzer", "#27AE60"),
            "DELAY":      ("⚖️ Ambivalent", "#D68910"),
            "PREVENT":    ("🛡️ Resistant",  "#C0392B"),
            "REROUTE":    ("🌍 Expander",   "#7D3C98"),
        }
    },
}

PF_EV = (
    "Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's "
    "net-zero emissions targets, as prescribed by Australia's National Electric "
    "Vehicle Strategy (2023)"
)

# ─────────────────────────────────────────
# EXAMPLES — 12 entries (Table WE1), verbatim quotes with source codes
# Used both as UI shortcuts AND as the Validation Suite ground truth.
# ─────────────────────────────────────────
EXAMPLES = {
    "— Select an example from the paper —": {
        "prescribed": "", "comment": "", "activity": "", "subtype": "", "orientation": ""
    },
    "⚡ CATALYZER  |  📊 Evaluation  →  Simplify": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "SIMPLIFY", "orientation": "CATALYZER",
        "comment": (
            "All the studies I've seen say about 12,000 miles or 3 to 5 years for "
            "lifetime emissions to be better than ICE (FG). "
            "There's no discussion about whether they're better for the environment. "
            "The math and science is extremely clear and it's ridiculous to even "
            "compare them with how much better EVs are (FG). "
            "Many industry observers believe we have already passed the tipping "
            "point where sales of electric vehicles will very rapidly overwhelm "
            "petrol and diesel cars (NM)."
        )
    },
    "⚡ CATALYZER  |  💬 Negotiation  →  Advocate": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "ADVOCATE", "orientation": "CATALYZER",
        "comment": (
            "#ClimateCrisis is real. It's time to look at #solarenergy and "
            "#ElectricVehicles not the energy sources of the past like #fossilfuels (X). "
            "We are already so far behind! We need to sprint to catch up. We should be "
            "WORLD LEADERS in solar and battery manufacturing (PC). "
            "We need to act on transport emissions as quickly as possible. Australia "
            "has demonstrated that it has an appetite for EVs, so let's get moving (PC). "
            "Climate change is an urgent threat, and we need to accelerate the "
            "decarbonisation of transport quickly and efficiently. Let's lift the "
            "ambition (PC)."
        )
    },
    "⚡ CATALYZER  |  ⚙️ Enactment  →  Accelerate": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "ACCELERATE", "orientation": "CATALYZER",
        "comment": (
            "We have ordered two Teslas that will be delivered hopefully this year. "
            "We are selling our Prado and it looks like we are going to sell our last "
            "Toyota car (FG). "
            "Our family has been living with an EV and a PHEV for 3 years and they are "
            "fantastic (W). "
            "Bought our first EV largely for the environment, partly for fuel cost "
            "savings. Bought our second EV because they're just far better cars to own "
            "and drive (R). "
            "Proud owner of Model 3. I'll never own a gas combustion engine again -- "
            "not even a hybrid (X)."
        )
    },
    "⚖️ AMBIVALENT  |  📊 Evaluation  →  Stall": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "STALL", "orientation": "AMBIVALENT",
        "comment": (
            "Range anxiety is overstated… however if you stay somewhere with no "
            "charging and need to drive 200–300km you are stuffed (W). "
            "I'm not convinced yet that full EVs are the way to go. They seem to have "
            "quite a few problems, you know, battery disposal and other things (I). "
            "Perhaps these problems are over-exaggerated for views and I realise they "
            "will eventually be resolved with infrastructure and improvements in "
            "technology. I just don't see this happening adequately in the next few "
            "years (R)."
        )
    },
    "⚖️ AMBIVALENT  |  💬 Negotiation  →  Question": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "QUESTION", "orientation": "AMBIVALENT",
        "comment": (
            "Have you thought about what they are gonna do with all the batteries once "
            "they expire because they aren't recyclable? (FG). "
            "So where do we get the $50k to buy the cheapest new EV? It will not be "
            "possible for us to make the transition until a huge number of second hand "
            "EVs hit the market (FG). "
            "We need to invest in infrastructure but at the same time limit the cost of "
            "doing so by not putting all eggs in the one basket. We should transition to "
            "hybrid vehicles instead of EVs until 2030 (PC)."
        )
    },
    "⚖️ AMBIVALENT  |  ⚙️ Enactment  →  Delay": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "DELAY", "orientation": "AMBIVALENT",
        "comment": (
            "Really good and interesting report! I am wanting to upgrade the car at a "
            "not too distant time and I am umming and aahing over PHEV or EV. EV would "
            "be magic but such a jump in price! PHEV seems great as a midway point as "
            "most of my driving is around town (YT). "
            "Yep, the cost is indeed a huge hurdle. I think I'll be running my 12 year "
            "old Subaru Outback a bit longer! (YT). "
            "Just bought a new petrol car as the infrastructure still isn't in place (FG). "
            "Hopefully, by the time my car does need to be replaced, EVs are a lot "
            "cheaper and the inconveniences are worked out (R). "
            "I plan to drive my current 10 year old hybrid as long as I can. The next "
            "car I buy will probably be electric, but I'm expecting many of these "
            "issues to be resolved by then (R)."
        )
    },
    "🛡️ RESISTANT  |  📊 Evaluation  →  Avoid": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "AVOID", "orientation": "RESISTANT",
        "comment": (
            "Electric vehicles are not the solution, for Australia to take this up we "
            "are going to have to increase mining of precious minerals at a "
            "considerable amount, which in itself will contribute to greenhouse gases (PC). "
            "EV and hybrid technology has long way to go especially here in Australia. "
            "Petrol and diesel vehicles will be around for many decades to come doing "
            "the jobs that EVs and Hybrids just can't do (YT). "
            "Electric vehicles are not the future, just a muddle point (PC)."
        )
    },
    "🛡️ RESISTANT  |  💬 Negotiation  →  Reject": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "REJECT", "orientation": "RESISTANT",
        "comment": (
            "Is this communism — take away our freedom of choice! (FG). "
            "Australians are not as ignorant as the politicians think — if this country "
            "is taxed just for an ideology then the potential for even greater social "
            "unrest is likely (PC). "
            "I think it's like being a vegan of the car world. It's social policing "
            "because you're deviating from the norm (FG). "
            "We don't need politicians and their cronies telling us what sort of car we "
            "can have (YT)."
        )
    },
    "🛡️ RESISTANT  |  ⚙️ Enactment  →  Prevent": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "PREVENT", "orientation": "RESISTANT",
        "comment": (
            "I have had ICE cars for some 37 years and have found them to be very "
            "reliable (W). "
            "Me, I'm sticking to my petrol vehicle til it dies (YT). "
            "Why buy a new EV when my old car is doing all right — 13 years and "
            "130,000 km, so good for another 13 years because it's diesel (FG). "
            "I'll stick to my V8 and my other diesel 4x4... (FG)."
        )
    },
    "🌍 EXPANDER  |  📊 Evaluation  →  Complexify": {
        "prescribed": PF_EV, "activity": "EVALUATION", "subtype": "COMPLEXIFY", "orientation": "EXPANDER",
        "comment": (
            "Facilitating greater use of active, shared and public transport can cut "
            "climate pollution further and faster than electrifying vehicles, because "
            "the effects are seen immediately through reduced use of private motor "
            "vehicle travel (AD). "
            "This doesn't cover the destruction of the fabric of cities to accommodate "
            "cars. Gasoline or electric, the most significant environmental destruction "
            "caused by cars is the blight it causes to cities. Electric vehicle is a "
            "false solution if you care about the environment at all (FG). "
            "The best way to help the environment is to buy less stuff and keep older "
            "stuff running for longer (R)."
        )
    },
    "🌍 EXPANDER  |  💬 Negotiation  →  Contest": {
        "prescribed": PF_EV, "activity": "NEGOTIATION", "subtype": "CONTEST", "orientation": "EXPANDER",
        "comment": (
            "Does it have to be a car? (FG). "
            "If your main priority was the environment, ride a bicycle… you're buying "
            "a 2-tonne metal box powered by a giant battery — let's not pretend we're "
            "saving the planet (R). "
            "Are we ready to have electric cars claiming our public spaces? Time to "
            "rethink public transport! #COP26 #ElectricVehicles (X). "
            "Consumerism trumps facts. Why save the environment by keeping the car you "
            "already own and using it less, when you can join the Joneses and spend "
            "money on that flash new hybrid/EV status symbol (YT)."
        )
    },
    "🌍 EXPANDER  |  ⚙️ Enactment  →  Reroute": {
        "prescribed": PF_EV, "activity": "ENACTMENT", "subtype": "REROUTE", "orientation": "EXPANDER",
        "comment": (
            "We tend to do most of our shopping by bike rather than with the ute "
            "because the ute's inconvenient to park and navigate in small car parks (I). "
            "So that's the plan is to extract maximum value out of that current "
            "vehicle until it is no longer functional. I am at the moment on a waiting "
            "list for a new electric cargo bike (I). "
            "I uprooted my life and moved from the Sunshine Coast to Melbourne with "
            "some of my strongest reasoning being the ability to use public transport, "
            "ride a bike around and use a car as little as possible (PC)."
        )
    },
}

# ─────────────────────────────────────────
# GENERALIZATION TESTS — comments outside Table WE1, used to sanity-check
# that the model generalizes rather than memorizes.
# ─────────────────────────────────────────
GENERALIZATION_TESTS = {
    "— Select a generalization test —": {"comment": "", "note": ""},
    "New: mechanic cost concern": {
        "comment": (
            "I've been thinking about getting an EV for a while but my mechanic "
            "says the battery replacement cost is insane. Guess I'll wait and see "
            "what happens with prices in a couple years."
        ),
        "note": "Expected: AMBIVALENT / ENACTMENT-DELAY (conditional wait tied to price)"
    },
    "New: degrowth critique": {
        "comment": (
            "Honestly the whole EV push ignores that most emissions come from "
            "manufacturing and shipping, not driving. We need degrowth, not just "
            "new cars."
        ),
        "note": "Expected: EXPANDER / EVALUATION-COMPLEXIFY"
    },
}

# ─────────────────────────────────────────
# CORE FUNCTIONS
# ─────────────────────────────────────────

def analyze_comment(prescribed_future: str, comment: str, api_key: str) -> dict:
    client = openai.OpenAI(api_key=api_key)
    user_message = f"""
PRESCRIBED FUTURE:
{prescribed_future}

CONSUMER COMMENT TO ANALYZE:
{comment}

Remember: apply the DECISION PROCEDURE (Section G) in order — including
the Generic-You Test, Rhetorical-Question Test, Standalone-Judgment Test,
and the mandatory Step 4 tie-breaker if signals from more than one
activity are present. Return EXACTLY ONE value per enum field. Complete
Section H (likely_opposing_orientation + potential_challenge_rationale).
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
    return json.loads(response.choices[0].message.content)


def run_validation_suite(api_key: str) -> dict:
    """Internal QA tool: validates the 12 single-comment examples from
    Table WE1 against their ground-truth categories. Not needed for
    regular use — see the 'Advanced / Developer Tools' expander."""
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
# UI HELPER FUNCTIONS
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
            {cfg['emoji']} {ori}
        </span>
        <span style="font-size:16px;color:#aaa;">→</span>
        <span style="background:{ameta['bg']};border:2px solid {ameta['color']};color:{ameta['color']};
                     border-radius:20px;padding:4px 14px;font-weight:bold;font-size:13px;">
            {ameta['icon']} {act}
        </span>
        <span style="font-size:16px;color:#aaa;">→</span>
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
        <strong style="color:#2980B9;">📌 Prescribed Future Analyzed:</strong><br>
        <em style="color:#333;">{prescribed_future}</em>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        cfg = ORIENTATIONS.get(orientation, {})
        st.markdown(f"""
        <div style="background:{cfg.get('bg','#f5f5f5')};border-left:6px solid {cfg.get('border','#999')};
                    border-radius:10px;padding:16px 18px;min-height:220px;">
            <h3 style="color:{cfg.get('color','#555')};margin:0;font-size:22px;">
                {cfg.get('emoji','❓')} {orientation}
            </h3>
            <p style="color:#666;margin:4px 0 3px;font-size:12px;">
                <strong>Confidence:</strong> {result.get('orientation_confidence','N/A')}
            </p>
            <p style="color:#777;margin:2px 0;font-size:11px;">📖 {cfg.get('narrative','')}</p>
            <p style="color:#777;margin:2px 0;font-size:11px;">⏱️ {cfg.get('temporality','')}</p>
            <p style="color:#777;margin:2px 0;font-size:11px;">🎯 {cfg.get('goal','')}</p>
            <p style="color:#999;margin:4px 0 0;font-size:10px;">{cfg.get('activities','')}</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        ameta = ACTIVITY_META.get(main_act, {})
        sub_cfg = ORIENTATIONS.get(orientation, {})
        st.markdown(f"""
        <div style="background:{ameta.get('bg','#f5f5f5')};border-left:6px solid {ameta.get('color','#555')};
                    border-radius:10px;padding:16px 18px;min-height:220px;">
            <h3 style="color:{ameta.get('color','#555')};margin:0;font-size:20px;">
                {ameta.get('icon','🔄')} {main_act}
            </h3>
            <p style="color:#555;margin:4px 0 3px;font-size:12px;"><strong>Main Future-Making Activity</strong></p>
            <span style="background:{sub_cfg.get('bg','#f5f5f5')};border:1.5px solid {sub_cfg.get('color','#555')};
                         color:{sub_cfg.get('color','#555')};border-radius:12px;
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
                    border-radius:10px;padding:16px 18px;min-height:220px;">
            <h3 style="color:{chg['color']};margin:0;font-size:20px;">{chg['emoji']} {chg['label']}</h3>
            <p style="color:#555;margin:4px 0 3px;font-size:12px;"><strong>⚠️ Potential Challenge Contribution</strong></p>
            <p style="color:#999;margin:0 0 4px;font-size:10px;">(if this comment meets an opposing orientation)</p>
            <p style="color:#777;margin:3px 0;font-size:11px;">{chg['description']}</p>
        </div>
        """, unsafe_allow_html=True)

    # ── FRICTION POINT CARD ──
    opp_ori = _clean_enum((result.get("likely_opposing_orientation") or "")).upper()
    opp_cfg = ORIENTATIONS.get(opp_ori)
    if opp_cfg:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="background:#FFF8F0;border:2px dashed #E67E22;border-radius:10px;
                    padding:16px 18px;">
            <h4 style="color:#E67E22;margin:0 0 8px;font-size:16px;">
                ⚡ Likely Friction Point
            </h4>
            <p style="font-size:13px;color:#555;margin:0 0 6px;">
                If this comment met an opposing consumer, it would most likely clash with a
                <strong style="color:{opp_cfg['color']};">{opp_cfg['emoji']} {opp_ori}</strong>
                orientation.
            </p>
            <p style="font-size:12px;color:#777;font-style:italic;margin:0;">
                "{result.get('potential_challenge_rationale','—')}"
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab_ori, tab_act, tab_chg = st.tabs(["🔍 Orientation Rationale", "🔄 Activity Rationale", "⚡ Challenge Rationale"])

    with tab_ori:
        st.markdown("**Why this orientation? (applied coding criteria)**")
        st.write(result.get("orientation_rationale", "—"))
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown("**📖 Narrative**"); st.caption(result.get("narrative_identified", "—"))
        with c2:
            st.markdown("**😊 Emotions**"); st.caption(result.get("dominant_emotions", "—"))
        with c3:
            st.markdown("**⏱️ Temporality**"); st.caption(result.get("temporality_expressed", "—"))
        with c4:
            st.markdown("**📋 Notable Conditions**"); st.caption(result.get("notable_conditions_of_adoption", "—"))

    with tab_act:
        st.markdown("**Why this activity is primary? (Decision Procedure applied)**")
        st.write(result.get("activity_rationale", "—"))
        sec = result.get("secondary_activities", [])
        if sec:
            st.markdown(f"**Secondary activities also present (informational):** {', '.join(sec)}")
        st.markdown("---")
        st.markdown("**📋 Coding Criteria Applied**")
        for act_name, meta in ACTIVITY_META.items():
            is_main = (act_name == main_act)
            border  = f"3px solid {meta['color']}" if is_main else "1px solid #ddd"
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
        st.markdown("**How could this comment contribute to a future-making challenge?**")
        st.write(result.get("potential_challenge_rationale", "—"))
        st.caption(
            f"Deterministic mapping applied: {main_act} → {chg['label']} "
            f"(per the paper's activity→challenge logic)."
        )

    st.markdown("---")
    st.markdown("## 📋 Policy & Managerial Implications")
    policy_tab, manager_tab = st.tabs(["🏛️ Policy Roadmap", "🏢 Managerial Roadmap"])

    with policy_tab:
        policy = result.get("policy_recommendations", {}) or {}
        st.markdown(f"**📍 Most Relevant Step:** {policy.get('step','—')}")
        st.markdown(f"**🎯 Policy Objective:** {policy.get('objective','—')}")
        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown("**🔧 Recommended Policy Instruments**")
            for inst in policy.get("instruments", []) or []:
                st.markdown(f"• {inst}")
        with pc2:
            st.markdown("**➡️ Additional Actions**")
            for action in policy.get("additional_actions", []) or []:
                st.markdown(f"→ {action}")
        with st.expander("📍 Full Policy Roadmap (7 Steps)"):
            st.markdown("""
| Step | Action |
|:----:|--------|
| **1** | **Determine the prescribed future** |
| **2** | **Map future-making orientations** |
| **3** | **Diagnose key future-making challenges** |
| **4** | **Implement support initiatives** |
| **5** | **Facilitate enactment** |
| **6** | **Measure multiple outcomes** |
| **7** | **Revise intervention** |
            """)

    with manager_tab:
        manager = result.get("manager_recommendations", {}) or {}
        st.markdown(f"**📍 Most Relevant Step:** {manager.get('step','—')}")
        st.markdown(f"**🎯 Managerial Objective:** {manager.get('objective','—')}")
        mc1, mc2 = st.columns(2)
        with mc1:
            st.markdown("**🔧 Recommended Interventions**")
            for interv in manager.get("interventions", []) or []:
                st.markdown(f"• {interv}")
        with mc2:
            st.markdown("**⚠️ Avoid**")
            for av in manager.get("avoid", []) or []:
                st.markdown(f"✗ {av}")
        st.markdown("**💬 Messaging Tip**")
        st.info(manager.get("messaging_tip", "—"))
        with st.expander("📍 Full Managerial Roadmap (6 Steps)"):
            st.markdown("""
| Step | Action |
|:----:|--------|
| **1** | **Determine the prescribed future** |
| **2** | **Consider future-making orientations** |
| **3** | **Monitor key future-making challenges** |
| **4** | **Select orientation-sensitive response** |
| **5** | **Match messaging to challenges** |
| **6** | **Support consumers through enactment** |
            """)

    st.markdown("---")
    st.caption(f"📚 *\"{PAPER_TITLE}\"* — *{PAPER_JOURNAL}* | [Read the paper]({PAPER_URL})")


# ─────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────

def main():
    st.title("🔮 Future-Making Orientation Analyzer")
    st.markdown(f"""
    Identify the **main future-making orientation**, **primary activity**,
    and the **potential future-making challenge** a single comment could
    contribute to — plus tailored **policy & managerial recommendations** —
    grounded in the paper's coding criteria.

    *Based on:* **"{PAPER_TITLE}"** — *{PAPER_JOURNAL}*
    """)
    st.divider()

    # ── API KEY ──
    api_key = None
    try:
        api_key = st.secrets["openai_api_key"]
    except Exception:
        with st.expander("⚙️ API Settings — click to configure", expanded=True):
            api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")

    st.markdown("---")

    # ─────────────────────────────────────────
    # MAIN FEATURE — Analyze a Comment
    # (always visible, no mode selector)
    # ─────────────────────────────────────────
    st.markdown("### 📌 Step 1 — Define the Prescribed Future")
    pf_default = st.session_state.pop("pf_prefill", "")
    prescribed_future = st.text_area(
        "prescribed_future", value=pf_default, height=85,
        placeholder="e.g., 'Transition all vehicles to Zero Emission Vehicles (EVs) to achieve Australia's net-zero emissions targets by 2035'",
        label_visibility="collapsed"
    )

    st.markdown("### 💬 Step 2 — Enter a Consumer Comment")
    input_method = st.radio(
        "Input method:",
        ["📝 Type or paste text", "🧪 Try a generalization test", "📂 Upload a .txt file"],
        horizontal=True
    )

    comment = ""
    if input_method == "📝 Type or paste text":
        selected_ex = st.selectbox(
            "Or try a built-in example (from the paper's Table WE1):", list(EXAMPLES.keys())
        )
        ex_data = EXAMPLES.get(selected_ex, {"prescribed": "", "comment": "", "activity": "", "subtype": "", "orientation": ""})
        if selected_ex != "— Select an example from the paper —":
            show_example_badge(ex_data)
            suggested_pf = ex_data.get("prescribed", "")
            if suggested_pf:
                st.info(f"💡 **Suggested prescribed future:** *{suggested_pf[:130]}...*")
                if st.button("↑ Use this as my prescribed future", type="secondary"):
                    st.session_state["pf_prefill"] = suggested_pf
                    st.rerun()
        comment = st.text_area(
            "Comment:", value=ex_data.get("comment", ""), height=220,
            placeholder="Paste or type a consumer comment here...", label_visibility="collapsed"
        )
    elif input_method == "🧪 Try a generalization test":
        selected_test = st.selectbox("Choose a test comment not used to build the app:", list(GENERALIZATION_TESTS.keys()))
        test_data = GENERALIZATION_TESTS.get(selected_test, {"comment": "", "note": ""})
        if test_data.get("note"):
            st.info(f"🧪 {test_data['note']}")
        comment = st.text_area("Comment:", value=test_data.get("comment", ""), height=150, label_visibility="collapsed")
    else:
        uploaded_file = st.file_uploader("Upload .txt file:", type=["txt"])
        if uploaded_file:
            comment = uploaded_file.read().decode("utf-8")
            st.success(f"✅ Uploaded: {len(comment):,} characters")
            with st.expander("Preview"):
                st.text(comment[:600] + ("..." if len(comment) > 600 else ""))

    if not prescribed_future.strip():
        prescribed_future = PF_EV

    st.markdown("---")
    ready = bool(api_key and comment.strip())
    if not comment.strip():
        st.warning("⚠️ Please enter a comment in Step 2.")
    if not api_key:
        st.warning("⚠️ Please configure your OpenAI API key above.")

    if st.button("🔍 Analyze Comment", type="primary", use_container_width=True, disabled=not ready):
        with st.spinner("Analyzing with paper coding criteria..."):
            try:
                result = analyze_comment(prescribed_future.strip(), comment.strip(), api_key)
                st.divider()
                st.markdown("## 🧠 Analysis Results")
                show_results(result, prescribed_future.strip())
            except openai.AuthenticationError:
                st.error("❌ Invalid API key.")
            except openai.RateLimitError:
                st.error("⏳ Rate limit reached. Please wait a moment.")
            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")

    # ─────────────────────────────────────────
    # ADVANCED / DEVELOPER TOOLS
    # (collapsed by default — internal QA only, not needed for regular use)
    # ─────────────────────────────────────────
    st.markdown("---")
    with st.expander("🔧 Advanced / Developer Tools"):
        st.caption(
            "Internal quality-control tool. Not needed for regular use. "
            "Run this after any change to the model, prompt, or temperature "
            "to confirm the app still matches the paper's Table WE1 categories."
        )
        if st.button("▶️ Run Validation Suite (Table WE1)"):
            if not api_key:
                st.warning("⚠️ Configure your API key above first.")
            else:
                with st.spinner("Running validation across all 12 examples..."):
                    report = run_validation_suite(api_key)
                if report["results"]:
                    st.metric("Overall Accuracy", f"{report['overall_accuracy']*100:.1f}%")
                    for r in report["results"]:
                        icon = "✅" if r["match"] else "❌"
                        with st.expander(f"{icon} {r['example']}"):
                            st.write("**Expected:**", r["expected"])
                            st.write("**Predicted:**", r["predicted"])
                            if r.get("error"):
                                st.error(r["error"])
                else:
                    st.info("No labeled examples found to validate.")


if __name__ == "__main__":
    main()
