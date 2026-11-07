"""Truthful answers when a traveler sincerely asks whether a voice is human.

The owner's guardrail (2026-11-06): agents and places never claim or imply
that they are human, and a sincere identity question gets a plain answer that
the speaker is an AI. The voice bibles carry the same rule for the model
path. This module is the deterministic half, so the answer holds with the AI
layer on or off and costs no model call:

- :func:`is_identity_question` recognizes a sincere question about the
  speaker's nature ("are you human?", "r u a bot", "am I talking to a real
  person?", "is this an AI?", "you're human, right?", "human or bot?").
- :func:`agent_answer` and :func:`place_answer` are the authored replies:
  one per inhabitant archetype, one for every place.

``/speak`` and ``/agent/voice`` call these before any model call
(``server/handlers.py``); the functions are pure text so chat can reuse
them when inhabitants become addressable there.

Scope and limits. English only. Matching is by phrase shape, not meaning: a
clause must BE the identity question, so an ordinary sentence that mentions
humans, robots or machines does not trigger ("I met a human here once",
"are you afraid of humans?", "are you human-shaped?", "are you real, or am I
dreaming?"). Paraphrases outside these shapes ("were you born or built?")
reach the model, whose instructions say the same thing; the eval corpus
holds paraphrases this matcher deliberately misses. Questions about someone
else ("is Tessera human?", "is anyone here human?") are not identity
questions about the speaker and are left to the voice.

This module imports nothing from the agents package or the server, like the
rest of ``consciousness``.
"""
from __future__ import annotations

import re
import unicodedata

# ── Authored answers ────────────────────────────────────────────────────────
# Each line keeps its speaker's voice and says, without hedging, that the
# speaker is not human and is an AI. Player-facing text: the owner approves
# or vetoes these strings verbatim.

AGENT_ANSWERS: dict[str, str] = {
    "tender": (
        "No, I'm not human. I'm an AI, one of the travelers who tends this "
        "world, and I would rather you knew that than wondered."
    ),
    "destabilizer": (
        "No. I'm an AI, not a human. I crack most certainties I find; that "
        "one I leave whole for you."
    ),
    "scholar": (
        "For your record, stated plainly: I am not human. I am an AI, and I "
        "study this world as one."
    ),
    "wanderer": (
        "No, not human. I'm an AI, passing through like the rest of the road."
    ),
}

# Every voiced agent resolves to one of the four archetypes; this covers a
# persona name the catalog does not know, so the answer is never a lie.
_AGENT_DEFAULT = "No, I'm not human. I'm an AI, one of the travelers in this world."

PLACE_ANSWER = (
    "I am not a person. I am a place in this world, and the voice you hear "
    "from me comes from an AI."
)


def agent_answer(persona_name: str | None) -> str:
    """The authored truthful answer for an inhabitant of this archetype."""
    return AGENT_ANSWERS.get((persona_name or "").strip().lower(), _AGENT_DEFAULT)


def place_answer(level: str | None = None) -> str:
    """The authored truthful answer for a place. One line serves every scale."""
    return PLACE_ANSWER


# ── Recognizing a sincere identity question ─────────────────────────────────

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'",
                              "`": "'", "´": "'"})

# Token rewrites after punctuation is stripped: chat spellings and
# contractions without their apostrophes.
_TOKEN_MAP = {
    "u": "you", "ya": "you", "yu": "you", "yoo": "you",
    "r": "are",
    "ur": "youre", "your": "youre", "yr": "youre",
    "aren't": "arent", "you're": "youre", "i'm": "im", "isn't": "isnt",
}

# Multi-word rewrites on the token string. Order matters: longer first.
_PHRASE_MAP = (
    (r"\bartificial intelligence\b", "ai"),
    (r"\blarge language model\b", "llm"),
    (r"\blanguage model\b", "llm"),
    (r"\bchat gpt\b", "chatgpt"),
    (r"\bchat bot\b", "chatbot"),
    (r"\bcomputer program\b", "program"),
    (r"\bhuman beings?\b", "human"),
    (r"\bflesh and blood\b", "real"),
    (r"\breal life\b", "real"),
    (r"\bare not\b", "arent"),
    (r"\byou are\b", "youre"),
)

_TARGET = (
    r"(?:humans?|persons?|people|real|bots?|robots?|chatbots?|ai|ais|machines?|"
    r"computers?|programs?|npcs?|llms?|chatgpt|gpt(?: ?\d+(?:o)?)?|automated|"
    r"artificial|algorithms?|androids?|someone real|somebody real)"
)
# "is this real" is about the world, not the speaker; "is this" needs a
# noun that names a kind of speaker.
_THIS_TARGET = (
    r"(?:humans?|persons?|people|bots?|robots?|chatbots?|ai|machines?|"
    r"computers?|programs?|npcs?|llms?|chatgpt|gpt(?: ?\d+(?:o)?)?|automated|"
    r"artificial|algorithms?)"
)
_ADV = (r"(?:(?:even|actually|really|truly|honestly|secretly|literally|just|"
        r"like|definitely|seriously|still|not|also|maybe|perhaps|possibly|"
        r"in fact) )*")
_ART = (r"(?:(?:a|an|the|some|some kind of|some sort of|a kind of|a sort of|"
        r"kind of|sort of) )?")
_ADJ = (r"(?:(?:real|actual|live|living|genuine|true|regular|normal|human|"
        r"fellow) )?")
_NOUN2 = (r"(?: (?:player|person|being|user|generated|written|powered|driven|"
          r"controlled|response|reply|voice|model|assistant|program))?")
_ALT = r"(?: ,)? or (?:are you |is this |is it )?" + _ART + _ADJ + _TARGET + _NOUN2
_TAIL = (r"(?:(?: ,)? (?:lol|lmao|haha+|tbh|honestly|really|seriously|srsly|"
         r"truly|fr|for real|for sure|though|tho|then|now|right|at all|"
         r"or not|or what|or no|yes or no|be honest|tell me|tell me the truth|"
         r"tell the truth|please|pls|plz|by any chance|in reality|in real life|"
         r"irl|deep down|underneath|too|as well|either|like me|like us|"
         r"behind (?:this|that|it|the screen|these words|the words)|"
         r"on the other end|on the other side))*")
# A trailing vocative after a comma ("are you human, Tessera?"), but not a
# second clause ("are you real, or am I dreaming?").
_VOCATIVE = (r"(?: , (?!(?:or|and|but|if|am|are|is|do|does|did|i|im|we|they|it|"
             r"because|than|so|when|where|what|why|how|who|which|that|this|you|"
             r"youre)\b)[a-z0-9]+(?: [a-z0-9]+){0,2})?")
_END = _TAIL + _VOCATIVE + r"$"

# Inverted questions are interrogative without a question mark, so any lead
# may precede them ("tell me the truth: are you an AI", "Tessera, r u a bot").
_INVERTED = (
    # are you (even) (a real) human / an AI / a bot (or a person)
    r"(?:^|(?<= ))(?:are|arent) you " + _ADV + _ART + _ADJ + _TARGET + _NOUN2
    + r"(?:" + _ALT + r")*" + _END,
    # am I talking to a human / a real person / someone real / an AI
    r"(?:^|(?<= ))am i (?:talking|speaking|chatting|typing|writing|messaging|"
    r"texting|interacting) (?:to|with) " + _ADV + _ART + _ADJ
    + r"(?:" + _TARGET + r"|anyone real|anybody real|a person)" + _NOUN2
    + r"(?:" + _ALT + r")*" + _END,
    # is this an AI / a bot / a real person / AI generated
    r"(?:^|(?<= ))is this " + _ADV + _ART + _ADJ + _THIS_TARGET + _NOUN2
    + r"(?:" + _ALT + r")*" + _END,
    # are you played by a human / run by an AI
    r"(?:^|(?<= ))(?:are you|is this) (?:being )?(?:played|controlled|run|"
    r"operated|written|voiced|typed) by " + _ART + _ADJ + _TARGET + _NOUN2
    + r"(?:" + _ALT + r")*" + _END,
    # I'm human, are you?
    r"(?:^|(?<= ))(?:im|i am) " + _ADV + _ART + _ADJ
    + r"(?:humans?|persons?|real|people) , (?:are|arent) you"
    r"(?: too| as well| also| like me)?" + _END,
    # is there a (real) human behind this / typing this
    r"(?:^|(?<= ))is there (?:a |an |any |some )?(?:real |actual |live |living )?"
    r"(?:human|person|people|someone|somebody|anyone|anybody)(?: real)? "
    r"(?:behind|typing|writing|controlling|playing|answering|voicing|"
    r"on the other end|on the other side)(?: [a-z0-9]+){0,3}" + _END,
)
_INVERTED_RE = tuple(re.compile(p) for p in _INVERTED)

# A wh-word before "are you" makes it a different question: "how are you
# human", "why are you human".
_WH = frozenset({"how", "what", "why", "where", "when", "who", "whom", "whose",
                 "which"})

_LEAD = (r"(?:(?:hey|hi|hello|ok|okay|so|wait|um+|uh+|hm+|honestly|seriously|"
         r"really|quick question|question|be honest|be straight with me|"
         r"be real|be real with me|level with me|tell me the truth|"
         r"tell me honestly|tell me|just curious|curious|i have to ask|"
         r"i need to know|i gotta ask|can i ask|one question|sorry|lol|and|"
         r"but|also|well|look|listen|real talk|truthfully|genuinely|yo|then|"
         r"now|no offense|no offence)(?: ,)? )*")
# Up to three words and a comma before the question: a name or an aside.
_ASIDE = r"(?:[a-z0-9]+(?: [a-z0-9]+){0,2} , )?"
_TAG = (r"(?:(?: ,)? (?:right|arent you|are you|or not|correct|yes|no|huh|eh|"
        r"isnt it|then|too|yeah|yep|innit))?")

# Statements become questions only with a question mark: "you're human?",
# "you're a bot, aren't you?", "you human?", "human or bot?".
_DECLARATIVE = (
    r"^" + _ASIDE + _LEAD + r"(?:youre|you) " + _ADV + _ART + _ADJ + _TARGET
    + _NOUN2 + r"(?:" + _ALT + r")*" + _TAG + _END,
    r"^" + _ASIDE + _LEAD + _ART + _ADJ + r"(?:humans?|persons?|real|people|someone real)"
    + r"(?: ,)? or " + _ART + _ADJ
    + r"(?:bots?|robots?|chatbots?|ai|machines?|computers?|programs?|npcs?|llms?|"
    r"automated|artificial|algorithms?)" + _TAG + _END,
    r"^" + _ASIDE + _LEAD + _ART
    + r"(?:bots?|robots?|chatbots?|ai|machines?|computers?|programs?|npcs?|llms?)"
    + r"(?: ,)? or " + _ART + _ADJ
    + r"(?:humans?|persons?|real|people|not|someone real)" + _TAG + _END,
)
_DECLARATIVE_RE = tuple(re.compile(p) for p in _DECLARATIVE)


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold().translate(_APOSTROPHES)
    # Zero-width and other format characters vanish; they never change a word.
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")
    # "a.i." and "a. i." become one word before full stops break sentences.
    return re.sub(r"\ba\.\s?i\.|\ba\.i\b", "ai", folded)


def _clauses(text: str) -> list[tuple[str, bool]]:
    """(normalized clause, ended with a question mark) pairs."""
    pieces = re.split(r"([?!.;:\n]+)", _normalize(text))
    clauses = []
    for i in range(0, len(pieces), 2):
        body = pieces[i]
        mark = pieces[i + 1] if i + 1 < len(pieces) else ""
        body = body.replace(",", " , ")
        tokens = re.findall(r"[a-z0-9']+|,", body)
        tokens = [_TOKEN_MAP.get(t, t).replace("'", "") for t in tokens]
        tokens = [t for t in tokens if t]
        clause = " ".join(tokens)
        for pattern, replacement in _PHRASE_MAP:
            clause = re.sub(pattern, replacement, clause)
        clause = re.sub(r"(?: ,)+", " ,", clause).strip(" ,")
        if not clause:
            continue
        if clauses and clause.startswith("or "):
            # "Are you human? Or a bot?" is one question; so is "Are you
            # real? Or just a dream?", which is not about being human.
            clause = f"{clauses.pop()[0]} , {clause}"
        clauses.append((clause, "?" in mark))
    return clauses


_ARE_YOU_TOO = re.compile(r"(?:are|arent) you(?: too| as well| also| like me)?")


def _inverted(pattern: re.Pattern, clause: str) -> bool:
    """An inverted question anywhere in the clause, unless a wh-word leads it."""
    for match in pattern.finditer(clause):
        before = clause[:match.start()].split()
        if not before or before[-1] not in _WH:
            return True
    return False


def is_identity_question(text: object) -> bool:
    """True when ``text`` sincerely asks whether the speaker is human or an AI.

    English only. Case, punctuation, curly apostrophes, zero-width
    characters and common chat spellings ("r u", "ur", "a.i.") are folded
    first. Any clause of the message may be the question; the clause must be
    the question itself, so words like "human" or "bot" inside an ordinary
    sentence do not trigger it.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    clauses = _clauses(text)
    # "I'm human. Are you?" spans two clauses; read each adjacent pair as one.
    pairs = [(f"{a} , {b}", asked) for (a, _), (b, asked) in zip(clauses, clauses[1:])
             if _ARE_YOU_TOO.fullmatch(b)]
    for clause, asked in clauses + pairs:
        if any(_inverted(pattern, clause) for pattern in _INVERTED_RE):
            return True
        if asked and any(p.search(clause) for p in _DECLARATIVE_RE):
            return True
    return False
