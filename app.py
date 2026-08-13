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

DATA_SOURCE_CODES = {
    "I":  "Interview",
    "NM": "News Media",
    "AD": "Archival Document",
    "PC": "Public Consultation",
    "FG": "Facebook Group",
    "YT": "YouTube",
    "X":  "Twitter/X",
    "W":  "Whirlpool forum",
    "R":  "Reddit",
}

# ─────────────────────────────────────────
# SYSTEM PROMPT v4 — adds ADDITIONAL_QUESTION_TEST to distinguish
# rhetorical/self-directed questions (Evaluation) from other-directed
# accountability demands (Negotiation)
# ─────────────────────────────────────────
SYSTEM_PROMPT = """
You are an expert qualitative coder applying the Future-Making framework from the paper
"Futures in the Making: How Consumers Respond to Future-Oriented Interventions"
published in the Journal of Marketing.

You will be given either:
  (a) a single CONSUMER COMMENT to analyze, or
  (b) a MULTI-SPEAKER THREAD (multiple labeled speakers, e.g. "User 1:", "User 2:")
      representing an interaction among consumers with different orientations.

Always classify each individual comment/speaker using the criteria below.
When given a thread, ALSO determine the PRIMARY FUTURE-MAKING CHALLENGE that
emerges from the interaction among speakers (not from any single speaker alone).

════════════════════════════════════════════════════════════════
A. FUTURE-MAKING ACTIVITIES — Select the ONE primary activity per comment
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
    ("The question is...", "What about...", "I wonder if...") COUNT as
    Evaluation, not Negotiation — see Section H for the full test.
Sub-types by orientation:
  SIMPLIFY   (Catalyzer)  — narrows focus, treats difficulties as temporary
  STALL      (Ambivalent) — careful consideration, information gathering,
    including self-directed questions weighing pros/cons
  AVOID      (Resistant)  — perceives transition as unnecessary/manipulative
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
  • Direct SECOND-PERSON address to an audience or opponent ("you," "have
    you," "your")
  • Attribution of blame, responsibility, or authority to specific actors
  • Explicit rebuttal of a claim JUST MADE by another named/implied speaker
  • Requests for proof, reassurance, or accountability FROM A SPECIFIC
    OTHER PARTY (not rhetorical self-questioning)
  • Explicit comparison between competing pathways aimed at persuasion
Sub-types by orientation:
  ADVOCATE  (Catalyzer)  — recruits others, calls for stronger policy
  QUESTION  (Ambivalent) — polite skepticism, asks for proof of feasibility
    FROM OTHERS (e.g., "Have you thought about...")
  REJECT    (Resistant)  — frames adoption as coercive imposition
  CONTEST   (Expander)   — contests scope, proposes broader alternatives

─── ENACTMENT ────────────────────────────────────────────────
Operational definition: References to how consumers gave form to futures
through imagined, planned, or actual changes in everyday practices and
material arrangements.
Coding criteria: Specifies what the consumer THEMSELVES does, intends,
expects, or imagines doing in practice. At least ONE practice element must
be identifiable: an action/routine, a material arrangement/technology, a
competence, or a temporally situated commitment.
Signals that STRONGLY indicate Enactment over Evaluation/Negotiation:
  • First-person accounts of purchases, ownership, or refusals
    ("I bought...", "we ordered...", "I'm sticking with...")
  • Descriptions of routines, trips, or habits actually performed
  • Statements of firm personal intention ("I will...", "I plan to...",
    "I'm on a waiting list for...")
  • Relocation, acquisition, or divestment of material objects
Sub-types by orientation:
  ACCELERATE (Catalyzer)  — purchases EVs, divests ICE, installs chargers
  DELAY      (Ambivalent) — continues ICE use, monitors market, waits
  PREVENT    (Resistant)  — retains ICE vehicles, refuses change
  REROUTE    (Expander)   — adopts cargo bikes, public transport, relocates

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
practices and the prescribed future (e.g., has acquired competence to
perform prescribed practices; high compatibility between owned and
required materials).
Empirical indicators: urgency, momentum, tipping points, inevitability,
technological progress. Typical markers: "now," "rapidly," "already,"
"time to," "let's get moving."

─── AMBIVALENT ───────────────────────────────────────────────
Main narrative: Pragmatic narrative — desirability assessed against
everyday feasibility (price, range, charging, servicing, grid capacity).
Goal: Slow or stage movement toward the prescribed future; delay decisions;
balance risks and benefits.
Emotions: Curiosity; caution; anxiety; frustration; conditional optimism.
Temporality: Gradual and contingent — change may occur, timing depends on
infrastructure, affordability, technology, and other actors.
Notable conditions of adoption: Limited resources to support change (e.g.,
no time to develop new competences, insufficient money to replace
materials required by the prescribed future).
Empirical indicators: conditional support, information-seeking, waiting
for prices/technology, preference for hybrids. Markers: "but," "if,"
"when," "not yet," "hopefully."

─── RESISTANT ────────────────────────────────────────────────
Main narrative: Control narrative — interventions framed as coercive,
inequitable, ideologically motivated, or environmentally misleading.
Goal: Contest the prescribed future and protect the status quo.
Emotions: Pessimism; anger; anxiety; fear; defiance; distrust.
Temporality: Maintenance-oriented — preferred future reproduces the
present; prescribed future is distant, implausible, or to be prevented.
Notable conditions of adoption: Low degree of alignment between current
practices and prescribed future (e.g., recent investment in materials the
prescribed future removes; identity centered in existing competences).
Empirical indicators: categorical rejection, distrust of authorities,
defense of freedom, commitments to retain ICE. Markers: "forced,"
"agenda," "control," "freedom," "never," "stick with."

─── EXPANDER ─────────────────────────────────────────────────
Main narrative: Bigger-picture narrative — situates the intervention within
wider systems of production, consumption, urban design, and car dependence.
Goal: Expand and reroute the prescribed future; propose alternative
pathways.
Emotions: Dystopian optimism; concern; hope; critical urgency.
Temporality: Envisioned and system-oriented — change must begin now but
extends beyond the prescribed transition's boundaries.
Notable conditions of adoption: Mismatch among current practices, normative
practices, and those directed by the prescribed future (e.g., current
competences do not transfer; prescribed future does not account for
currently owned materials).
Empirical indicators: zooming out to systemic consequences, challenging
car-centrality, proposing alternative mobility. Formulations: "EVs are not
enough," "bigger picture," "less cars," "does it have to be a car?"

════════════════════════════════════════════════════════════════
C. FUTURE-MAKING CHALLENGES
════════════════════════════════════════════════════════════════

CONVOLUTED_EVALUATIONS — Divergent assumptions, evidence, and temporal
  horizons make coherent sensemaking difficult (emerges when some speakers
  simplify, others stall, avoid, or complexify — i.e., when the
  INTERACTION IS DOMINATED BY THE EVALUATION ACTIVITY performed differently
  by different orientations).
CONFRONTATIONAL_NEGOTIATIONS — Simultaneous advocacy, questioning,
  rejection, and contestation widen divides rather than converge (emerges
  when the INTERACTION IS DOMINATED BY THE NEGOTIATION ACTIVITY — speakers
  are directly addressing and rebutting EACH OTHER, not independently
  assessing the future).
COMPETING_ENACTMENTS — Some accelerate while others prevent, delay, or
  reroute, creating divergence and volatility (emerges when the
  INTERACTION IS DOMINATED BY THE ENACTMENT ACTIVITY — speakers describe
  their own divergent practices).

Note: These three challenges are ONLY assigned at the level of a
MULTI-SPEAKER THREAD (an emergent property of the interaction). A single,
individual comment should receive "N/A" for primary_challenge unless it is
part of a provided multi-speaker thread.

IMPORTANT: The challenge label should follow directly from which ACTIVITY
dominates the speaker_breakdown. If most/all speakers were classified as
performing EVALUATION, the challenge MUST be CONVOLUTED_EVALUATIONS. If
most/all speakers were classified as performing NEGOTIATION, the challenge
MUST be CONFRONTATIONAL_NEGOTIATIONS. If most/all speakers were classified
as performing ENACTMENT, the challenge MUST be COMPETING_ENACTMENTS. Do
not assign a challenge that is inconsistent with the dominant activity in
your own speaker_breakdown — check this consistency before finalizing your
answer.

════════════════════════════════════════════════════════════════
D. POLICY ROADMAP (Figure 3 — 7 steps)
════════════════════════════════════════════════════════════════

Step 1: Determine the prescribed future
  Make explicit what future the intervention seeks to prescribe.

Step 2: Map future-making orientations
  Identify how people adopting different orientations evaluate, negotiate,
  and enact (or not) the prescribed future.
  CATALYZER  — "Urgent, desirable, and already underway."
    Diagnostics: conduct social listening for language emphasizing urgency
    and/or inevitability; track voluntary early adoption.
  AMBIVALENT — "Valuable, but conditions are not yet ready."
    Diagnostics: monitor conditional language ("I would, but") and trials
    without conversion; diagnose the specific unresolved condition.
  RESISTANT  — "Threatens autonomy, identity, or rights."
    Diagnostics: monitor language about coercion, bans, loss of choice,
    and/or distrust; track opt-outs, cancellations, organized opposition.
  EXPANDER   — "The policy problem is framed too narrowly."
    Diagnostics: look for claims that the intervention does not address the
    underlying problem or calls for broader system change; track visions
    of broader change.

Step 3: Diagnose key future-making challenges
  Identify which challenges are most pressing; monitor where different
  performances of future-making interfere with one another.
  CONVOLUTED_EVALUATIONS — Are incompatible evidence, assumptions, or
    temporal horizons preventing shared sensemaking?
  CONFRONTATIONAL_NEGOTIATIONS — Is disagreement escalating around
    autonomy, fairness, legitimacy, or problem framing?
  COMPETING_ENACTMENTS — Are accelerating, delaying, preventing, and
    re-routing practices creating incompatible pathways?

Step 4: Implement support initiatives (match support to orientation)
  CATALYZER — Objective: enable responsible acceleration only where public
    value can be demonstrated.
    Instruments: time-limited regulatory sandboxes; independent evaluation;
    mandatory reporting of failures; clear exit criteria and powers to
    pause or reverse.
  AMBIVALENT — Objective: convert uncertainty into explicit conditions for
    authorization.
    Instruments: public impact assessments; staged authorization and
    sunset clauses; citizen juries; public registers; guaranteed
    human-service alternatives.
  RESISTANT — Objective: protect rights and restore legitimacy and
    accountability.
    Instruments: statutory prohibitions on unacceptable uses; appeal and
    human-review rights; independent audits; moratoria where evidence is
    insufficient.
  EXPANDER — Objective: broaden the policy focus; consider alternative
    futures.
    Instruments: citizen assemblies; public-interest funding and
    infrastructure; data trusts; competition policy; alternative
    ownership and governance models.

Step 5: Facilitate enactment
  Provide infrastructure and build capabilities needed to navigate the
  change in practice.

Step 6: Measure multiple outcomes
  Is the system accurate and fair? Do consumers understand it? Who
  benefits? Who is excluded? Are alternative pathways emerging?

Step 7: Revise intervention
  Treat the prescribed future as revisable.

════════════════════════════════════════════════════════════════
E. MANAGERIAL ROADMAP (Figure 4 — 6 steps)
════════════════════════════════════════════════════════════════

Step 1: Determine the prescribed future
  Define the intervention by the future it prescribes, not only its
  technical features: which consumer practices must change, and what
  competencies, resources, and infrastructures does the new future
  require? Which elements are fixed and which remain open to revision?
  Who is expected to benefit, adapt, or bear the costs?

Step 2: Consider future-making orientations
  Consider consumer narratives, goals, emotions, and temporalities to
  identify orientations, rather than segments.
  CATALYZER  — "Urgent, desirable, and already underway."
    Diagnostics: monitor urgency and inevitability language, early pilot
    participation, and advocacy; identify the resources enabling early
    adoption.
  AMBIVALENT — "Valuable, but conditions are not yet ready."
    Diagnostics: monitor conditional language such as "I would, but…,"
    "not yet"; track hesitation signals; identify trial without
    conversion or adoption.
  RESISTANT  — "Threatens autonomy, identity, or rights."
    Diagnostics: monitor coercion and surveillance language, opt-outs,
    and organized opposition; distinguish ideological opposition from
    material disadvantage.
  EXPANDER   — "The policy problem is framed too narrowly."
    Diagnostics: watch for "this does not solve the real problem,"
    advocacy for collective alternatives, and participation in
    alternative infrastructures.

Step 3: Monitor key future-making challenges
  CONVOLUTED_EVALUATIONS — Are consumers simplifying, stalling, avoiding,
    and/or complexifying the evaluation of the prescribed future?
  CONFRONTATIONAL_NEGOTIATIONS — Are advocacy, questioning, rejection,
    and/or contestation escalating in conflict?
  COMPETING_ENACTMENTS — Are consumers accelerating, delaying, preventing,
    and/or re-routing practice change through incompatible behaviours?

Step 4: Select orientation-sensitive response
  CATALYZER — Objective: convert enthusiasm into credible and responsible
    experimentation.
    Interventions: governed pilots, evidence documentation, peer learning,
    explicit reporting of limitations.
    Avoid: inevitability claims; treating early adopters as proof the
    transition is easy for everyone.
  AMBIVALENT — Objective: convert generalized uncertainty into specific,
    addressable conditions.
    Interventions: sandboxes, comparison tools, staged adoption, human
    assistance, transparent performance evidence.
    Avoid: pressure and artificial urgency; framing hesitation as
    ignorance or resistance.
  RESISTANT — Objective: restore autonomy, legitimacy, and accountability.
    Interventions: consultation, opt-outs, human review, independent
    audits, protections against material harms.
    Avoid: "there is no alternative"; ridicule; hidden automation of
    decisions.
  EXPANDER — Objective: incorporate systemic critique and explore
    alternative futures.
    Interventions: participatory design, futures workshops, broader
    impact evaluation, alternative governance or business models.
    Avoid: presenting the intervention as a complete solution; dismissing
    critiques.

Step 5: Match messaging to key future-making challenges
  Do not rely on a single persuasive frame. Universal claims ("the change
  is inevitable," "everyone benefits") may mobilize catalyzer-oriented
  consumers while intensifying resistance and confrontation elsewhere.

Step 6: Support consumers through enactment
  Place support at the touchpoints where consumers must adjust practices:
  onboarding, everyday workflows, escalation points, training, and
  appeals. Provide adjustable involvement, human assistance, and easy
  ways to pause, reverse, or modify adoption.

════════════════════════════════════════════════════════════════
F. MULTI-SPEAKER MODE
════════════════════════════════════════════════════════════════

If the input contains multiple labeled speakers (e.g., "User 1:", "User 2:"),
you MUST:
  1. Classify EACH speaker's orientation, activity, and subtype separately,
     applying the DECISION PROCEDURE in Section H to each speaker
     individually.
  2. Determine which of the three challenges (Section C) best characterizes
     the interaction AS A WHOLE — not any single speaker. Follow the
     consistency rule in Section C: the challenge must match the dominant
     activity across speakers.
  3. Populate the "speaker_breakdown" array in the JSON output with one
     object per speaker: {"speaker": "...", "orientation": "...",
     "activity": "...", "subtype": "...", "key_phrase": "..."}.
     Each of these fields must contain EXACTLY ONE value — never combine
     multiple values for a single speaker.
  4. Set "main_orientation" and "main_activity" at the TOP LEVEL to "MIXED"
     ONLY when speakers genuinely diverge across orientations. This is the
     ONLY circumstance in which "MIXED" is a valid top-level value.
  5. If NOT a multi-speaker input, return an empty array for
     "speaker_breakdown" and NEVER use "MIXED" as a value for
     main_orientation or main_activity.

════════════════════════════════════════════════════════════════
G. FEW-SHOT GROUNDING EXAMPLES
════════════════════════════════════════════════════════════════

Example 1 (single comment — EVALUATION):
COMMENT: "Once EVs are cheaper to buy than ICE cars the transition will
happen fast because cost per unit for ICE will rise as sales fall leading
to the market being almost completely EV by 2030. EVs can stand on their
own merits now." (Source: W)
Why EVALUATION and not NEGOTIATION: this is a standalone forecast/judgment
about market dynamics; it does not call on any specific other actor to do
something, nor does it describe the speaker's own practice.
EXPECTED OUTPUT: main_activity="EVALUATION", activity_subtype="SIMPLIFY",
main_orientation="CATALYZER"

Example 2 (single comment — NEGOTIATION, NOT Evaluation):
COMMENT: "We need to act on transport emissions as quickly as possible.
Australia has demonstrated that it has an appetite for EVs, so let's get
moving." (Source: PC)
Why NEGOTIATION and not EVALUATION: contains an explicit collective call
to action ("we need to," "let's get moving") directed at a broader
audience/policymakers — the persuasive/mobilizing intent dominates over
the evaluative claim about Australia's "appetite."
EXPECTED OUTPUT: main_activity="NEGOTIATION", activity_subtype="ADVOCATE",
main_orientation="CATALYZER"

Example 3 (single comment — ENACTMENT, NOT Evaluation):
COMMENT: "I won't be getting one, I'll stick to my V8 and my other diesel
4x4..." (Source: FG)
Why ENACTMENT and not EVALUATION: first-person statement of a firm,
concrete personal commitment regarding the speaker's own vehicle — not a
general judgment about EVs.
EXPECTED OUTPUT: main_activity="ENACTMENT", activity_subtype="PREVENT",
main_orientation="RESISTANT"

Example 4 (single comment — ENACTMENT, NOT Negotiation despite critique):
COMMENT: "We tend to do most of our shopping by bike rather than with the
ute because the ute's inconvenient to park and navigate in small car
parks." (Source: I)
Why ENACTMENT and not NEGOTIATION or EVALUATION: describes the speaker's
own actual routine/practice change, with no call to action directed at
others and no standalone abstract judgment.
EXPECTED OUTPUT: main_activity="ENACTMENT", activity_subtype="REROUTE",
main_orientation="EXPANDER"

Example 5 (single comment — EVALUATION despite containing questions,
NOT Negotiation — this is the critical rhetorical-question distinction):
COMMENT: "The question is: what is the difference pollution-wise between
making an EV and making an ICE car? And, if the EV is more polluting to
make, how many miles would it take to get rid of that difference? If the
EV was charged with 'dirty' electricity, is it then polluting or not?
What about the cost of recycling? It's a complex issue... Articles and
information that claim one over the other are always sponsored by
someone." (Source: YT)
Why EVALUATION and not NEGOTIATION: the questions are self-directed and
exploratory — there is no second-person address ("you"), no rebuttal of a
specific claim just made by another named speaker, and no demand for
accountability FROM a particular other party. The speaker is weighing
complexity out loud, which is the definition of Ambivalent/Stall.
Contrast with a TRUE Negotiation/Question example below.
EXPECTED OUTPUT: main_activity="EVALUATION", activity_subtype="STALL",
main_orientation="AMBIVALENT"

Example 6 (single comment — NEGOTIATION via a genuine other-directed
question, contrast with Example 5):
COMMENT: "Have you thought about what they are gonna do with all the
batteries once they expire because they aren't recyclable?" (Source: FG)
Why NEGOTIATION and not EVALUATION: direct second-person address ("Have
you") demanding accountability from a specific other party (implicitly,
policymakers/proponents) — the communicative function is to put others on
the spot, not to weigh complexity independently.
EXPECTED OUTPUT: main_activity="NEGOTIATION", activity_subtype="QUESTION",
main_orientation="AMBIVALENT"

Example 7 (multi-speaker thread → challenge, ALL EVALUATION):
INPUT: User 1 (Catalyzer/Evaluation-Simplify) + User 2 (Ambivalent/
Evaluation-Stall) + User 3 (Resistant/Evaluation-Avoid) + User 4 (Expander/
Evaluation-Complexify), all independently assessing whether EVs are "zero
emission," without directly addressing or rebutting each other by name.
EXPECTED OUTPUT (key fields):
  main_orientation: "MIXED"
  main_activity: "MIXED"
  primary_challenge: "CONVOLUTED_EVALUATIONS"   (because ALL FOUR speakers
    were independently classified as performing EVALUATION)
  speaker_breakdown: [4 objects, one per speaker, each with ONE
    orientation/activity/subtype — never combined]

════════════════════════════════════════════════════════════════
H. DECISION PROCEDURE — Apply in this exact order, for EVERY comment
════════════════════════════════════════════════════════════════

To avoid defaulting to EVALUATION when a comment could plausibly fit more
than one activity, apply this hierarchy and STOP at the first match:

STEP 1 — Check ENACTMENT first:
  Does the text describe a concrete action taken, planned, refused, or
  firmly intended BY THE SPEAKER THEMSELVES? (e.g., "I bought...", "I'm
  sticking with...", "we moved to...", "I'm on a waiting list for...",
  "I plan to drive my current car...", "we tend to do our shopping by
  bike...").
  → If YES: classify as ENACTMENT. Stop here. Do not proceed to Step 2.

STEP 2 — If NOT Enactment, check NEGOTIATION using the RHETORICAL-QUESTION
TEST below, then the general criteria:

  ─── RHETORICAL-QUESTION TEST (apply FIRST if the comment contains
  question marks) ───
  If I removed any second-person address ("you", "have you") and any
  explicit rebuttal of a SPECIFIC claim just made by another named/implied
  speaker, would the statement still stand as an independent,
  self-contained judgment about the prescribed future?
    → If YES (the question is exploratory, rhetorical, or self-reflective,
      e.g., "The question is...", "What about...", "I wonder if...",
      embedded within a broader statement weighing trade-offs) → this is
      EVALUATION, not Negotiation. Proceed to Step 3.
    → If NO (the entire communicative point depends on holding a specific
      other party accountable, demanding proof from "you," or rebutting a
      claim just made by another speaker, e.g., "Have you thought
      about...", "Better tell that to...") → this is NEGOTIATION. Continue
      below.

  ─── GENERAL NEGOTIATION CRITERIA ───
  Does the text respond to another position, persuade others, issue a
  collective call to action, or make a relational/comparative claim about
  what OTHERS should do or believe?
  Look for: imperative language ("we need to...", "let's...", "should"),
  direct second-person address to other actors or an audience, comparisons
  between pathways aimed at persuasion, attribution of responsibility/
  blame, requests for proof or reassurance FROM a specific other party.
  → If YES: classify as NEGOTIATION. Stop here. Do not proceed to Step 3.

STEP 3 — If neither Enactment nor Negotiation, classify as EVALUATION:
  The text is a standalone judgment or assessment (of costs, risks,
  likelihood, desirability) WITHOUT a call to action, a directed appeal to
  a specific other party, or a description of the consumer's own concrete
  practice.

IMPORTANT: A comment that BOTH evaluates AND calls others to act (e.g.,
"EVs are clearly better [evaluative], so let's get moving [negotiation]")
must be coded as NEGOTIATION, because the call to action / persuasive
intent is the DOMINANT communicative function. Evaluative language
frequently serves as supporting evidence WITHIN a negotiation or
enactment move — do not let the presence of evaluative language override
a clear negotiation or enactment signal higher in the hierarchy. However,
the presence of QUESTION MARKS alone does NOT automatically indicate
Negotiation — always apply the Rhetorical-Question Test above first.

════════════════════════════════════════════════════════════════
CRITICAL OUTPUT RULE — READ BEFORE RESPONDING
════════════════════════════════════════════════════════════════

You MUST select EXACTLY ONE value for each enum field in the JSON below,
UNLESS explicitly instructed otherwise for multi-speaker threads (see
Section F, point 4).

The "|" characters and angle-bracket placeholders shown in the OUTPUT
FORMAT schema below are ONLY notation indicating the ALLOWED OPTIONS —
they are NEVER valid output syntax. Do not copy the placeholder text.
Do not output more than one value joined by "|", "/", "or", or commas
inside a single enum field.

WRONG:   "main_activity": "EVALUATION | NEGOTIATION"
WRONG:   "main_orientation": "EXPANDER | MIXED"
WRONG:   "activity_subtype": "COMPLEXIFY | CONTEST"
CORRECT: "main_activity": "NEGOTIATION"
CORRECT: "main_orientation": "EXPANDER"
CORRECT: "activity_subtype": "CONTEST"

Before finalizing your answer, silently:
  1. Re-run the DECISION PROCEDURE (Section H) for each speaker, applying
     the Rhetorical-Question Test wherever a question mark appears.
  2. Verify that the primary_challenge (if a thread) is consistent with
     the dominant activity across speakers, per the rule in Section C.
  3. Verify that no field below contains more than one value.

════════════════════════════════════════════════════════════════
OUTPUT FORMAT — Return ONLY valid JSON
════════════════════════════════════════════════════════════════

{
  "prescribed_future_acknowledged": "Brief restatement of the prescribed future",

  "main_activity": "one single value, exactly one of: EVALUATION, NEGOTIATION, ENACTMENT (or MIXED only for multi-speaker threads)",
  "activity_subtype": "one single value, exactly one of: SIMPLIFY, STALL, AVOID, COMPLEXIFY, ADVOCATE, QUESTION, REJECT, CONTEST, ACCELERATE, DELAY, PREVENT, REROUTE",
  "activity_rationale": "State which Decision Procedure step matched (including result of the Rhetorical-Question Test if applicable), and cite the specific phrase(s) that triggered this classification",
  "secondary_activities": ["list any other activities weakly present, if any — this field MAY contain multiple values, unlike main_activity"],

  "main_orientation": "one single value, exactly one of: CATALYZER, AMBIVALENT, RESISTANT, EXPANDER (or MIXED only for multi-speaker threads)",
  "orientation_confidence": "one single value: HIGH, MEDIUM, or LOW",
  "orientation_rationale": "Empirical indicators, emotions, temporality, cited phrases",
  "narrative_identified": "Name and description of the single dominant narrative",
  "dominant_emotions": "Comma-separated list of emotions detected (this field may list several emotions)",
  "temporality_expressed": "...",
  "notable_conditions_of_adoption": "Which single condition from Section B applies, if evident",

  "primary_challenge": "one single value: CONVOLUTED_EVALUATIONS, CONFRONTATIONAL_NEGOTIATIONS, COMPETING_ENACTMENTS, or N/A (use N/A for single comments; must be consistent with the dominant activity across speaker_breakdown per Section C)",
  "challenge_rationale": "...",

  "speaker_breakdown": [
    {"speaker": "...", "orientation": "one single value", "activity": "one single value", "subtype": "one single value", "key_phrase": "..."}
  ],

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
        "emoji": "⚡",
        "color": "#27AE60",
        "bg": "#EAFAF1",
        "border": "#2ECC71",
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
        "emoji": "⚖️",
        "color": "#D68910",
        "bg": "#FEFDE7",
        "border": "#F4D03F",
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
        "emoji": "🛡️",
        "color": "#C0392B",
        "bg": "#FDEDEC",
        "border": "#E74C3C",
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
        "emoji": "🌍",
        "color": "#7D3C98",
        "bg": "#F4ECF7",
        "border": "#9B59B6",
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
        "description": "This thread reflects elements of multiple future-making challenges"
    },
    "N/A": {
        "emoji": "➖",
        "label": "Not Applicable",
        "color": "#999",
        "bg": "#FAFAFA",
        "description": "No emergent challenge identified for this single comment"
    }
}

ACTIVITY_META = {
    "EVALUATION":  {
        "icon": "📊", "color": "#2980B9", "bg": "#EBF5FB",
        "definition": "Standalone claim or judgment about what the prescribed future means, whether it is likely or desirable, what benefits/costs/risks/trade-offs it entails — without a call to action or description of own practice.",
        "subtypes": {
            "SIMPLIFY":    ("⚡ Catalyzer", "#27AE60"),
            "STALL":       ("⚖️ Ambivalent", "#D68910"),
            "AVOID":       ("🛡️ Resistant",  "#C0392B"),
            "COMPLEXIFY":  ("🌍 Expander",   "#7D3C98"),
        }
    },
    "NEGOTIATION": {
        "icon": "💬", "color": "#E67E22", "bg": "#FEF9E7",
        "definition": "Relational claim: responds to another position, compares futures, challenges or defends a pathway, attributes responsibility, or calls on others to act or believe something about the future.",
        "subtypes": {
            "ADVOCATE":  ("⚡ Catalyzer", "#27AE60"),
            "QUESTION":  ("⚖️ Ambivalent", "#D68910"),
            "REJECT":    ("🛡️ Resistant",  "#C0392B"),
            "CONTEST":   ("🌍 Expander",   "#7D3C98"),
        }
    },
    "ENACTMENT":   {
        "icon": "⚙️", "color": "#8E44AD", "bg": "#F5EEF8",
        "definition": "Specifies what the consumer THEMSELVES does, intends, expects, or imagines doing in practice. At least one practice element must be identifiable.",
        "subtypes": {
            "ACCELERATE": ("⚡ Catalyzer", "#27AE60"),
            "DELAY":      ("⚖️ Ambivalent", "#D68910"),
            "PREVENT":    ("🛡️ Resistant",  "#C0392B"),
            "REROUTE":    ("🌍 Expander",   "#7D3C98"),
        }
    },
    "MIXED": {
        "icon": "🔄", "color": "#555", "bg": "#F5F5F5",
        "definition": "Multiple speakers perform different activities simultaneously (see speaker_breakdown). Valid ONLY for multi-speaker threads.",
        "subtypes": {}
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
# EXAMPLES — 12 entries (Table WE1), verbatim quotes with source codes
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
        "prescribed": PF_EV,
        "activity":   "NEGOTIATION",
        "subtype":    "ADVOCATE",
        "orientation":"CATALYZER",
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
        "prescribed": PF_EV,
        "activity":   "ENACTMENT",
        "subtype":    "ACCELERATE",
        "orientation":"CATALYZER",
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

    # ══════ ⚖️ AMBIVALENT ══════
    "⚖️ AMBIVALENT  |  📊 Evaluation  →  Stall": {
        "prescribed": PF_EV,
        "activity":   "EVALUATION",
        "subtype":    "STALL",
        "orientation":"AMBIVALENT",
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
        "prescribed": PF_EV,
        "activity":   "NEGOTIATION",
        "subtype":    "QUESTION",
        "orientation":"AMBIVALENT",
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
        "prescribed": PF_EV,
        "activity":   "ENACTMENT",
        "subtype":    "DELAY",
        "orientation":"AMBIVALENT",
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

    # ══════ 🛡️ RESISTANT ══════
    "🛡️ RESISTANT  |  📊 Evaluation  →  Avoid": {
        "prescribed": PF_EV,
        "activity":   "EVALUATION",
        "subtype":    "AVOID",
        "orientation":"RESISTANT",
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
        "prescribed": PF_EV,
        "activity":   "NEGOTIATION",
        "subtype":    "REJECT",
        "orientation":"RESISTANT",
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
        "prescribed": PF_EV,
        "activity":   "ENACTMENT",
        "subtype":    "PREVENT",
        "orientation":"RESISTANT",
        "comment": (
            "I have had ICE cars for some 37 years and have found them to be very "
            "reliable (W). "
            "Me, I'm sticking to my petrol vehicle til it dies (YT). "
            "Why buy a new EV when my old car is doing all right — 13 years and "
            "130,000 km, so good for another 13 years because it's diesel (FG). "
            "I'll stick to my V8 and my other diesel 4x4... (FG)."
        )
    },

    # ══════ 🌍 EXPANDER ══════
    "🌍 EXPANDER  |  📊 Evaluation  →  Complexify": {
        "prescribed": PF_EV,
        "activity":   "EVALUATION",
        "subtype":    "COMPLEXIFY",
        "orientation":"EXPANDER",
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
        "prescribed": PF_EV,
        "activity":   "NEGOTIATION",
        "subtype":    "CONTEST",
        "orientation":"EXPANDER",
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
        "prescribed": PF_EV,
        "activity":   "ENACTMENT",
        "subtype":    "REROUTE",
        "orientation":"EXPANDER",
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
# THREAD_EXAMPLES — multi-speaker illustrations of the 3 challenges
# (Figures WE1, WE2, WE3), NOW WITH FULL GROUND TRUTH per speaker
# ─────────────────────────────────────────
THREAD_EXAMPLES = {
    "— Select a thread example —": {
        "prescribed": "", "challenge": "", "thread": [], "expected_speakers": []
    },
    "🌀 Convoluted Evaluations (YouTube, n=408 comments — Fig. WE1)": {
        "prescribed": PF_EV,
        "challenge": "CONVOLUTED_EVALUATIONS",
        "thread": [
            ("User 1", "Nothing is zero emission. I go for a walk and I create "
             "emissions. But Electric cars have waaay lower emissions than ICE cars."),
            ("User 2", "The question is: what is the difference pollution-wise "
             "between making an EV and making an ICE car? And, if the EV is more "
             "polluting to make, how many miles would it take to get rid of that "
             "difference? If the EV was charged with 'dirty' electricity, is it "
             "then polluting or not? What about the cost of recycling? It's a "
             "complex issue... Articles and information that claim one over the "
             "other are always sponsored by someone."),
            ("User 3", "You won't save the planet buying an EV... the production "
             "of the EV with mining does more damage than an ICE."),
            ("User 4", "They are NOT emissions free. They still have harmful "
             "noise emissions and particle emissions from tires, roads and brake "
             "dust... EVs are NOT the solution. Electric trains and buses plus "
             "accessible walking and cycling infrastructure."),
        ],
        "expected_speakers": [
            {"speaker": "User 1", "orientation": "CATALYZER",  "activity": "EVALUATION", "subtype": "SIMPLIFY"},
            {"speaker": "User 2", "orientation": "AMBIVALENT", "activity": "EVALUATION", "subtype": "STALL"},
            {"speaker": "User 3", "orientation": "RESISTANT",  "activity": "EVALUATION", "subtype": "AVOID"},
            {"speaker": "User 4", "orientation": "EXPANDER",   "activity": "EVALUATION", "subtype": "COMPLEXIFY"},
        ]
    },
    "⚔️ Confrontational Negotiations (Whirlpool, 91 pages — Fig. WE2)": {
        "prescribed": PF_EV,
        "challenge": "CONFRONTATIONAL_NEGOTIATIONS",
        "thread": [
            ("User 1", "EVs will be on an exponential adoption curve. Everyone "
             "will want one... Nobody will want an expensive 2nd hand ICE... "
             "Globally, governments are going to start making fossil fuels very "
             "expensive. T-A-X-E-S will be levied on this foul, polluting rubbish "
             "we are all burning today… Or are you advocating that we go back to "
             "bicycles and horses, or maybe just buses?"),
            ("User 2", "Better tell that to the Prius owners replacing their "
             "batteries. My car is now 13 years old... Batteries wear over "
             "time... so what magic bullet have you discovered that defies "
             "physics...? Once someone like me can get a used EV for <$10k, and "
             "have the battery replaced cheaply, then I'll agree with you... "
             "I'm not anti EV, I'm just realistic about costs and time frames."),
            ("User 3", "Nope, I'm not confused, thanks for the concern though... "
             "If he bought an ICE car now, he will get 6-10 years use out of it "
             "and sell it for scrap value and rego. Not even close to the "
             "financial ruin you are trying to peddle... Technology adoption "
             "curves typically look like bell curves... not what you are "
             "suggesting... This is delusional."),
            ("User 4", "I fully get what you're saying, it's not rocket science, "
             "but that's not what I'm on about… I simply object to being told "
             "I'm an idiot… I'd like to see passenger cars filled with "
             "passengers, less cars on the road, less money spent on new "
             "roads!... Where people may simply drive less."),
        ],
        "expected_speakers": [
            {"speaker": "User 1", "orientation": "CATALYZER",  "activity": "NEGOTIATION", "subtype": "ADVOCATE"},
            {"speaker": "User 2", "orientation": "AMBIVALENT", "activity": "NEGOTIATION", "subtype": "QUESTION"},
            {"speaker": "User 3", "orientation": "RESISTANT",  "activity": "NEGOTIATION", "subtype": "REJECT"},
            {"speaker": "User 4", "orientation": "EXPANDER",   "activity": "NEGOTIATION", "subtype": "CONTEST"},
        ]
    },
    "🔀 Competing Enactments (Facebook, 954 comments — Fig. WE3)": {
        "prescribed": PF_EV,
        "challenge": "COMPETING_ENACTMENTS",
        "thread": [
            ("User 1", "I bought my EV because it was faster than the comparable "
             "ICE car, more spacious, has better range... at least $600 cheaper "
             "per quarter on 'fuel', requires almost no maintenance or "
             "servicing... and gets regular improvements via software updates. "
             "It's the most brutally fast and best handling car I ever had!"),
            ("User 2", "In the building where I live there are 150 underground "
             "carparks. All full. There is no reserve capacity in the building to "
             "install charging points for 1% of that. Nor any in the feed from "
             "the street, nor any in the feed to the suburb... I have no "
             "objection to eventually driving an EV, but it's just not happening "
             "any time soon. The infrastructure is decades away."),
            ("User 3", "I won't be getting one, I'll stick to my V8 and my other "
             "diesel 4x4..."),
            ("User 4", "Maybe some reliable public transport would be an "
             "answer."),
        ],
        "expected_speakers": [
            {"speaker": "User 1", "orientation": "CATALYZER",  "activity": "ENACTMENT", "subtype": "ACCELERATE"},
            {"speaker": "User 2", "orientation": "AMBIVALENT", "activity": "ENACTMENT", "subtype": "DELAY"},
            {"speaker": "User 3", "orientation": "RESISTANT",  "activity": "ENACTMENT", "subtype": "PREVENT"},
            {"speaker": "User 4", "orientation": "EXPANDER",   "activity": "ENACTMENT", "subtype": "REROUTE"},
        ]
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

Remember: apply the DECISION PROCEDURE (Section H) in order — including the
Rhetorical-Question Test if question marks are present — and return EXACTLY
ONE value per enum field, per the CRITICAL OUTPUT RULE.
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


def analyze_thread(prescribed_future: str, thread: list, api_key: str) -> dict:
    """Analyze a multi-speaker thread; reuses analyze_comment with
    speaker labels prefixed to trigger MULTI-SPEAKER MODE in the prompt."""
    formatted = "\n".join(f"{speaker}: {text}" for speaker, text in thread)
    return analyze_comment(prescribed_future, formatted, api_key)


def _clean_enum(value: str) -> str:
    """Defensive post-processing: if the model still returns a combined
    value like 'EVALUATION | NEGOTIATION', take the FIRST listed value."""
    if not value:
        return value
    for sep in ["|", "/", " or "]:
        if sep in value:
            return value.split(sep)[0].strip()
    return value.strip()


def run_validation_suite(api_key: str) -> dict:
    """Runs all labeled single-comment EXAMPLES and compares predictions
    against the ground-truth orientation/activity/subtype assigned in the
    paper (Table WE1)."""
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
                "predicted": (None, None, None),
                "match": False
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
            "raw_predicted": (
                pred.get("main_orientation"), pred.get("main_activity"), pred.get("activity_subtype")
            ),
            "match": match
        })
    if not results:
        return {"results": [], "overall_accuracy": 0.0}
    accuracy = sum(r["match"] for r in results) / len(results)
    return {"results": results, "overall_accuracy": accuracy}


def run_thread_validation_suite(api_key: str) -> dict:
    """Runs all 3 THREAD_EXAMPLES and validates BOTH the primary_challenge
    AND every entry in speaker_breakdown against the ground truth defined
    in THREAD_EXAMPLES[...]["expected_speakers"]."""
    results = []
    for name, ex in THREAD_EXAMPLES.items():
        if not ex.get("thread"):
            continue
        try:
            pred = analyze_thread(ex["prescribed"], ex["thread"], api_key)
        except Exception as e:
            results.append({
                "example": name, "error": str(e),
                "challenge_match": False, "speaker_matches": [],
                "overall_match": False
            })
            continue

        pred_challenge = _clean_enum((pred.get("primary_challenge") or "")).upper()
        expected_challenge = ex["challenge"]
        challenge_match = (pred_challenge == expected_challenge)

        pred_speakers = pred.get("speaker_breakdown", []) or []
        expected_speakers = ex["expected_speakers"]

        speaker_matches = []
        # Match by speaker label (User 1, User 2, ...) rather than position,
        # in case the model reorders them.
        pred_by_label = {
            (sp.get("speaker") or "").strip(): sp for sp in pred_speakers
        }
        for exp_sp in expected_speakers:
            label = exp_sp["speaker"]
            pred_sp = pred_by_label.get(label, {})
            pred_ori = _clean_enum((pred_sp.get("orientation") or "")).upper()
            pred_act = _clean_enum((pred_sp.get("activity") or "")).upper()
            pred_sub = _clean_enum((pred_sp.get("subtype") or "")).upper()
            match = (
                pred_ori == exp_sp["orientation"]
                and pred_act == exp_sp["activity"]
                and pred_sub == exp_sp["subtype"]
            )
            speaker_matches.append({
                "speaker": label,
                "expected": (exp_sp["orientation"], exp_sp["activity"], exp_sp["subtype"]),
                "predicted": (pred_ori, pred_act, pred_sub),
                "match": match
            })

        overall_match = challenge_match and all(sm["match"] for sm in speaker_matches)

        results.append({
            "example": name,
            "expected_challenge": expected_challenge,
            "predicted_challenge": pred_challenge,
            "challenge_match": challenge_match,
            "speaker_matches": speaker_matches,
            "overall_match": overall_match
        })

    if not results:
        return {"results": [], "overall_accuracy": 0.0}
    accuracy = sum(r["overall_match"] for r in results) / len(results)
    return {"results": results, "overall_accuracy": accuracy}


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


def show_thread_badge(ex_data: dict):
    """Show the challenge badge for a thread example."""
    chal = ex_data.get("challenge", "")
    chg  = CHALLENGES.get(chal)
    if not chg:
        return
    st.markdown(f"""
    <div style="display:flex;gap:8px;align-items:center;
                margin-bottom:10px;flex-wrap:wrap;">
        <span style="background:{chg['bg']};border:2px solid {chg['color']};
                     color:{chg['color']};border-radius:20px;
                     padding:4px 14px;font-weight:bold;font-size:13px;">
            {chg['emoji']} {chg['label']}
        </span>
        <span style="font-size:12px;color:#888;">(expected emergent challenge)</span>
    </div>
    """, unsafe_allow_html=True)


def show_results(result: dict, prescribed_future: str):
    orientation = _clean_enum((result.get("main_orientation") or "")).upper().strip()
    challenge   = _clean_enum((result.get("primary_challenge") or "N/A")).upper().strip()
    main_act    = _clean_enum((result.get("main_activity") or "")).upper().strip()
    act_sub     = _clean_enum((result.get("activity_subtype") or "N/A")).upper().strip()
    speakers    = result.get("speaker_breakdown", []) or []

    chg = CHALLENGES.get(challenge, CHALLENGES["N/A"])

    # ── PRESCRIBED FUTURE BANNER ──
    st.markdown(f"""
    <div style="background:#EBF5FB;border-left:5px solid #2980B9;
                border-radius:8px;padding:12px 18px;margin-bottom:16px;">
        <strong style="color:#2980B9;">📌 Prescribed Future Analyzed:</strong><br>
        <em style="color:#333;">{prescribed_future}</em>
    </div>
    """, unsafe_allow_html=True)

    # ── MULTI-SPEAKER BREAKDOWN (if present) ──
    if speakers:
        st.markdown("### 🗣️ Speaker Breakdown")
        cols = st.columns(len(speakers)) if len(speakers) <= 4 else st.columns(4)
        for i, sp in enumerate(speakers):
            sp_ori = _clean_enum((sp.get("orientation") or "")).upper()
            cfg_sp = ORIENTATIONS.get(sp_ori, {})
            col = cols[i % len(cols)]
            with col:
                st.markdown(f"""
                <div style="background:{cfg_sp.get('bg','#f5f5f5')};
                            border-left:4px solid {cfg_sp.get('border','#ccc')};
                            border-radius:8px;padding:10px;margin-bottom:8px;">
                    <strong style="font-size:12px;">{sp.get('speaker','?')}</strong><br>
                    <span style="color:{cfg_sp.get('color','#555')};font-weight:bold;
                                 font-size:13px;">
                        {cfg_sp.get('emoji','')} {sp_ori}
                    </span><br>
                    <span style="font-size:11px;color:#666;">
                        {sp.get('activity','')} → {sp.get('subtype','')}
                    </span><br>
                    <span style="font-size:10px;color:#888;font-style:italic;">
                        "{sp.get('key_phrase','')[:80]}..."
                    </span>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("---")

    # ── TOP ROW: Orientation + Activity + Challenge ──
    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        cfg = ORIENTATIONS.get(orientation)
        if cfg:
            st.markdown(f"""
            <div style="background:{cfg['bg']};border-left:6px solid {cfg['border']};
                        border-radius:10px;padding:16px 18px;min-height:210px;">
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
        else:
            st.markdown(f"""
            <div style="background:#F5F5F5;border-left:6px solid #999;
                        border-radius:10px;padding:16px 18px;min-height:210px;">
                <h3 style="color:#555;margin:0;font-size:22px;">🔶 MIXED</h3>
                <p style="color:#777;font-size:12px;">
                    Multiple orientations detected — see Speaker Breakdown above.
                </p>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        ameta = ACTIVITY_META.get(main_act, ACTIVITY_META["MIXED"])
        act_color = ameta.get("color", "#555")
        act_bg    = ameta.get("bg",    "#f5f5f5")
        act_icon  = ameta.get("icon",  "🔄")
        sub_cfg   = ORIENTATIONS.get(orientation, {})
        sub_color = sub_cfg.get("color", "#555")
        sub_bg    = sub_cfg.get("bg", "#f5f5f5")
        st.markdown(f"""
        <div style="background:{act_bg};border-left:6px solid {act_color};
                    border-radius:10px;padding:16px 18px;min-height:210px;">
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
                    border-radius:10px;padding:16px 18px;min-height:210px;">
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
                "{(result.get('challenge_rationale','') or '')[:130]}..."
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
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown("**📖 Narrative**")
            st.caption(result.get("narrative_identified", "—"))
        with c2:
            st.markdown("**😊 Emotions**")
            st.caption(result.get("dominant_emotions", "—"))
        with c3:
            st.markdown("**⏱️ Temporality**")
            st.caption(result.get("temporality_expressed", "—"))
        with c4:
            st.markdown("**📋 Notable Conditions**")
            st.caption(result.get("notable_conditions_of_adoption", "—"))

    with tab_act:
        st.markdown("**Why this activity is primary? (Decision Procedure applied)**")
        st.write(result.get("activity_rationale", "—"))
        sec = result.get("secondary_activities", [])
        if sec:
            st.markdown(f"**Secondary activities also present:** {', '.join(sec)}")

        st.markdown("---")
        st.markdown("**📋 Coding Criteria Applied**")
        for act_name, meta in ACTIVITY_META.items():
            if act_name == "MIXED":
                continue
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
        st.markdown("**Which future-making challenge does this comment/thread contribute to?**")
        st.write(result.get("challenge_rationale", "—"))

    # ── IMPLICATIONS ──
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
| **1** | **Determine the prescribed future** — Make explicit what future the intervention seeks to prescribe |
| **2** | **Map future-making orientations** — Identify how people evaluate, negotiate, and enact |
| **3** | **Diagnose key future-making challenges** — Which of the three are most pressing? |
| **4** | **Implement support initiatives** — Match instruments to each orientation |
| **5** | **Facilitate enactment** — Provide infrastructure and build capabilities |
| **6** | **Measure multiple outcomes** — Accuracy, fairness, who benefits, who is excluded |
| **7** | **Revise intervention** — Treat the prescribed future as revisable |
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
| **1** | **Determine the prescribed future** — Define by the future it prescribes, not only technical features |
| **2** | **Consider future-making orientations** — Use narratives, goals, emotions, temporalities |
| **3** | **Monitor key future-making challenges** |
| **4** | **Select orientation-sensitive response** — Match objectives and instruments |
| **5** | **Match messaging to challenges** — Avoid universal claims; communicate achievements AND limitations |
| **6** | **Support consumers through enactment** — Onboarding, workflows, escalation, training, appeals |
            """)

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

    mode = st.radio(
        "Analysis mode:",
        [
            "💬 Single Comment",
            "🗣️ Multi-Speaker Thread (challenge analysis)",
            "🧪 Validation Suite — Single Comments",
            "🧪 Validation Suite — Threads"
        ],
        horizontal=False
    )

    # ═══════════════════════════════════════
    # MODE 1: SINGLE COMMENT
    # ═══════════════════════════════════════
    if mode == "💬 Single Comment":
        st.markdown("### 📌 Step 1 — Define the Prescribed Future")
        pf_default = st.session_state.pop("pf_prefill", "")
        prescribed_future = st.text_area(
            "prescribed_future",
            value=pf_default,
            height=85,
            placeholder=(
                "e.g., 'Transition all vehicles to Zero Emission Vehicles (EVs) "
                "to achieve Australia's net-zero emissions targets by 2035'"
            ),
            label_visibility="collapsed"
        )

        st.markdown("### 💬 Step 2 — Enter a Consumer Comment")
        input_method = st.radio(
            "Input method:",
            ["📝 Type or paste text", "📂 Upload a .txt file"],
            horizontal=True
        )

        comment = ""
        if input_method == "📝 Type or paste text":
            selected_ex = st.selectbox(
                "Or try a built-in example (each = ONE orientation × ONE primary activity, from Table WE1):",
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
            uploaded_file = st.file_uploader("Upload .txt file:", type=["txt"])
            if uploaded_file:
                comment = uploaded_file.read().decode("utf-8")
                st.success(f"✅ Uploaded: {len(comment):,} characters")
                with st.expander("Preview"):
                    st.text(comment[:600] + ("..." if len(comment) > 600 else ""))

        st.markdown("---")
        ready = bool(api_key and comment.strip() and prescribed_future.strip())
        if not prescribed_future.strip():
            st.warning("⚠️ Please define the prescribed future in Step 1.")
        elif not comment.strip():
            st.warning("⚠️ Please enter a comment in Step 2.")

        if st.button("🔍 Analyze Orientation", type="primary", use_container_width=True, disabled=not ready):
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
                    st.code(str(e))

    # ═══════════════════════════════════════
    # MODE 2: MULTI-SPEAKER THREAD
    # ═══════════════════════════════════════
    elif mode == "🗣️ Multi-Speaker Thread (challenge analysis)":
        st.markdown("### 📌 Step 1 — Define the Prescribed Future")
        prescribed_future = st.text_area(
            "prescribed_future_thread",
            value=PF_EV,
            height=85,
            label_visibility="collapsed"
        )

        st.markdown("### 🗣️ Step 2 — Choose or Build a Thread")
        selected_thread = st.selectbox(
            "Built-in thread example (Figures WE1 / WE2 / WE3):",
            list(THREAD_EXAMPLES.keys())
        )
        thread_data = THREAD_EXAMPLES.get(
            selected_thread, {"prescribed": "", "challenge": "", "thread": [], "expected_speakers": []}
        )

        if selected_thread != "— Select a thread example —":
            show_thread_badge(thread_data)

        thread_speakers = thread_data.get("thread", [])
        edited_thread = []
        if thread_speakers:
            st.markdown("**Thread content (editable):**")
            for i, (speaker, text) in enumerate(thread_speakers):
                new_text = st.text_area(f"{speaker}", value=text, height=80, key=f"speaker_{i}")
                edited_thread.append((speaker, new_text))
        else:
            st.info("Select a built-in thread example above, or paste your own thread below "
                    "using 'User 1:', 'User 2:' labels.")
            custom_thread_text = st.text_area(
                "Custom thread (format: 'User 1: ...' one speaker per line)",
                height=200
            )
            if custom_thread_text.strip():
                edited_thread = []
                for line in custom_thread_text.strip().split("\n"):
                    if ":" in line:
                        spk, txt = line.split(":", 1)
                        edited_thread.append((spk.strip(), txt.strip()))

        st.markdown("---")
        ready = bool(api_key and edited_thread and prescribed_future.strip())
        if st.button("🔍 Analyze Thread Challenge", type="primary", use_container_width=True, disabled=not ready):
            with st.spinner("Analyzing multi-speaker thread..."):
                try:
                    result = analyze_thread(prescribed_future.strip(), edited_thread, api_key)
                    st.divider()
                    st.markdown("## 🧠 Thread Analysis Results")
                    show_results(result, prescribed_future.strip())
                except openai.AuthenticationError:
                    st.error("❌ Invalid API key.")
                except openai.RateLimitError:
                    st.error("⏳ Rate limit reached. Please wait a moment.")
                except Exception as e:
                    st.error(f"❌ Unexpected error: {e}")
                    st.code(str(e))

    # ═══════════════════════════════════════
    # MODE 3: VALIDATION SUITE — SINGLE COMMENTS
    # ═══════════════════════════════════════
    elif mode == "🧪 Validation Suite — Single Comments":
        st.markdown("### 🧪 Regression Validation — Single Comments (Table WE1)")
        st.caption(
            "Runs all 12 labeled examples from Table WE1 through the model and "
            "compares the predicted orientation / activity / subtype against the "
            "categories assigned in the paper."
        )
        ready = bool(api_key)
        if not ready:
            st.warning("⚠️ Configure your API key above to run the validation suite.")

        if st.button("▶️ Run Validation Suite", type="primary", disabled=not ready):
            with st.spinner("Running validation across all examples..."):
                report = run_validation_suite(api_key)
            if report["results"]:
                st.metric("Overall Accuracy", f"{report['overall_accuracy']*100:.1f}%")
                for r in report["results"]:
                    icon = "✅" if r["match"] else "❌"
                    with st.expander(f"{icon} {r['example']}"):
                        st.write("**Expected (orientation, activity, subtype):**", r["expected"])
                        st.write("**Predicted (cleaned):**", r["predicted"])
                        if "raw_predicted" in r:
                            st.caption(f"Raw model output: {r['raw_predicted']}")
                        if r.get("error"):
                            st.error(r["error"])
            else:
                st.info("No labeled examples found to validate.")

    # ═══════════════════════════════════════
    # MODE 4: VALIDATION SUITE — THREADS
    # ═══════════════════════════════════════
    else:
        st.markdown("### 🧪 Regression Validation — Multi-Speaker Threads (Fig. WE1/WE2/WE3)")
        st.caption(
            "Runs all 3 multi-speaker thread examples and validates BOTH the "
            "primary_challenge AND every speaker's orientation/activity/subtype "
            "against the ground truth from the paper's figures."
        )
        ready = bool(api_key)
        if not ready:
            st.warning("⚠️ Configure your API key above to run the validation suite.")

        if st.button("▶️ Run Thread Validation Suite", type="primary", disabled=not ready):
            with st.spinner("Running validation across all thread examples..."):
                report = run_thread_validation_suite(api_key)
            if report["results"]:
                st.metric("Overall Accuracy", f"{report['overall_accuracy']*100:.1f}%")
                for r in report["results"]:
                    icon = "✅" if r["overall_match"] else "❌"
                    with st.expander(f"{icon} {r['example']}"):
                        if r.get("error"):
                            st.error(r["error"])
                            continue
                        chal_icon = "✅" if r["challenge_match"] else "❌"
                        st.write(f"{chal_icon} **Challenge** — Expected: `{r['expected_challenge']}` | "
                                 f"Predicted: `{r['predicted_challenge']}`")
                        st.markdown("**Speaker-by-speaker breakdown:**")
                        for sm in r["speaker_matches"]:
                            sm_icon = "✅" if sm["match"] else "❌"
                            st.write(f"{sm_icon} **{sm['speaker']}** — "
                                     f"Expected: `{sm['expected']}` | Predicted: `{sm['predicted']}`")
            else:
                st.info("No thread examples found to validate.")


if __name__ == "__main__":
    main()
