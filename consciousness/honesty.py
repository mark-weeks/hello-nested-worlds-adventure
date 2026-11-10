"""Truthful answers when a traveler sincerely asks whether a voice is human.

The owner's guardrail (2026-11-06): agents never claim or imply that they
are human, and a sincere identity question gets a plain answer that the agent
is an AI. The guardrail names agents, not places: extending it to places
(:func:`place_answer` and the place bible's line) is proposed in PR #158 and
awaits the owner's decision. The voice bibles instruct the model the same
way. This module is the deterministic half: on ``/speak`` and
``/agent/voice`` a line it reads, put to a place or a known agent and passed
by the moderation screen, gets the authored answer with the AI layer on or
off, and the answer itself takes no voice call (an escalated or held line
and an unknown agent keep their quiet or hold line):

- :func:`is_identity_question` recognizes a line that IS a sincere question
  about the speaker's nature ("are you human?", "r u a bot", "am I talking to
  a real person?", "is this an AI?", "you're human, right?", "human or
  bot?"), perhaps with a greeting, a name it answers to or a short lead
  around it.
- :func:`agent_answer` and :func:`place_answer` are the authored replies:
  one per inhabitant archetype, one for every place below the root and one
  for the root.

``/speak`` and ``/agent/voice`` read the line first and, after the place
lookup and the moderation screen, give the authored answer instead of the
voice call (``server/handlers.py``). The functions are pure text.

Scope and limits. English only. Matching is by phrase shape, not meaning:

- A clause must BE the identity question, so an ordinary sentence that
  mentions humans, robots or machines does not trigger ("I met a human here
  once", "are you afraid of humans?", "is this a machine?", "is there anyone
  behind the seal?", "is a machine running it?", "your people?", "are you
  real, or am I dreaming?"). An agent or an envoy is a role in this world,
  so a bare "are you an agent?" is not one while "are you an AI agent?" is,
  and "is this the machine I'm talking to?" points at one in the room.
- The whole line must be the question: every other clause is a greeting, a
  name, a short lead ("be honest") or "I'm human" ("I am"), and the line is
  at most :data:`MAX_CHARS` long. The question offers at most four alternatives
  ("human or a bot or an AI or a program?"); a longer list takes the
  normal path. "Tell me a story. Are you human?" or "Are you
  human? Want to work on this puzzle with me?" asks for more than the
  authored line says, so it takes the route's normal path, where the voice
  bible carries the same rule.
- A name is one the speaker answers to: a form of address every speaker
  shares (:data:`_ADDRESS_NAMES`: an archetype's, a scale's ("room",
  "galaxy") or a plain one ("friend", "traveler", "old one")), or the
  speaker's own name, which the route passes in ``own_names`` (the
  inhabitant's name for ``/agent/voice``, none for a place). Any other
  word where a name could stand is a request, so "Are you human? Help!",
  "Hi, open the door. Are you human?" and "Are you human, help me
  escape?" take the normal path. A place's own name is not known here, so
  "Hello, Ashen Ember Sphere. Are you human?" takes it too.
- Reported speech is not a question to the speaker ('she asked me "are you
  human?"', "the sign says: are you human").
- Questions about someone else ("is Tessera human?"), put to someone else
  ("Tessera, are you human?" asked of a place or of Vex: a cast member's
  or a walker's name counts only as its own speaker's) or about a group
  ("is anyone here human?", "is anyone here an AI?") are left to the
  voice. The authored lines answer for the speaker alone, so a chat
  surface that wants to answer a question put to no one needs its own
  predicate.
- Paraphrases outside these shapes ("were you born or built?") reach the
  model; the eval corpus holds paraphrases this matcher deliberately misses.

This module imports nothing from the agents package or the server, like the
rest of ``consciousness``.
"""
from __future__ import annotations

import functools
import re
import unicodedata
from collections.abc import Iterable

from consciousness import WANDERER_CAST

# ── Authored answers ────────────────────────────────────────────────────────
# Each line keeps its speaker's voice and says, without hedging, that the
# speaker is not human and is an AI. None opens with "No", which would
# answer "are you an AI?" the wrong way round before correcting itself.
# Player-facing text: the owner approves or vetoes these strings verbatim.

AGENT_ANSWERS: dict[str, str] = {
    "tender": (
        "I'm not human. I'm an AI, one of the travelers who tend this "
        "world, and I would rather you knew that than wondered."
    ),
    "destabilizer": (
        "I'm an AI, not a human. I crack most certainties I find; that "
        "one I leave whole for you."
    ),
    "scholar": (
        "For your record, stated plainly: I am not human. I am an AI, and I "
        "study this world as one."
    ),
    "wanderer": (
        "Not human. I'm an AI, passing through, like everyone on this road."
    ),
}

# Every voiced agent resolves to one of the four archetypes; this covers a
# persona name the catalog does not know, so the answer is never a lie.
_AGENT_DEFAULT = "I'm not human. I'm an AI, one of the travelers in this world."

# The place answers are the proposed half (module docstring): the owner's
# guardrail names agents, and these await the owner's decision.
PLACE_ANSWER = (
    "I am not a person. I am a place in this world, and the voice you hear "
    "from me comes from an AI."
)
# The root is the world itself, not a place in it.
ROOT_PLACE_ANSWER = (
    "I am not a person. I am this world, all of it, and the voice you hear "
    "from me comes from an AI."
)
_ROOT_LEVEL = "Multiverse"


def agent_answer(persona_name: str | None) -> str:
    """The authored truthful answer for an inhabitant of this archetype."""
    return AGENT_ANSWERS.get((persona_name or "").strip().lower(), _AGENT_DEFAULT)


def place_answer(level: str | None = None) -> str:
    """The authored truthful answer for a place: one line for the root, one for every other scale."""
    return ROOT_PLACE_ANSWER if level == _ROOT_LEVEL else PLACE_ANSWER


# ── Recognizing a sincere identity question ─────────────────────────────────

# A line longer than this asks for more than the authored answer gives. It
# also bounds the work the patterns below can be asked to do.
MAX_CHARS = 200
# Clauses around the question that may be greetings, names or leads.
_MAX_FILLER_CLAUSES = 3

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'",
                              "`": "'", "´": "'"})

# Token rewrites after punctuation is stripped: chat spellings and
# contractions without their apostrophes. "Your", "ur" and "yr" stay one
# word, "your": it is "you're" misspelt only before what follows "you're"
# ("your a bot", "your not human"), never before a noun it owns ("your
# people?", "your machine?").
_TOKEN_MAP = {
    "u": "you", "ya": "you", "yu": "you", "yoo": "you",
    "r": "are",
    "ur": "your", "yr": "your",
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


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold().translate(_APOSTROPHES)
    # Zero-width and other format characters vanish; they never change a word.
    folded = "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")
    # "a.i." and "a. i." become one word before full stops break sentences.
    return re.sub(r"\ba\.\s?i\.|\ba\.i\b", "ai", folded)


def _words(body: str) -> str:
    """One normalized clause as the words the patterns read, commas kept as " ,"."""
    tokens = re.findall(r"[a-z0-9']+|,", body.replace(",", " , "))
    tokens = [_TOKEN_MAP.get(t, t).replace("'", "") for t in tokens]
    clause = " ".join(t for t in tokens if t)
    for pattern, replacement in _PHRASE_MAP:
        clause = re.sub(pattern, replacement, clause)
    return re.sub(r"(?: ,)+", " ,", clause).strip(" ,")


_GPT = r"gpt(?: ?\d+(?:o)?)?"
# A bare "agent" is not here: in a world of factions and envoys "are you an
# agent?" can be about the world. It counts after a target word, as
# :data:`_NOUN2` ("are you an AI agent?", and also "a human agent" and "a
# real agent"), and as a thing at this exchange (:data:`_THING`: "is an
# agent typing these words?").
_TARGET = (
    r"(?:humans?|persons?|people|real|bots?|robots?|chatbots?|ai|ais|machines?|"
    r"computers?|programs?|npcs?|llms?|chatgpt|" + _GPT + r"|automated|"
    r"artificial|algorithms?|androids?|someone real|somebody real)"
)
# Assistant names count only without an article: "are you a gemini" is
# astrology, "are you claude" is not.
_NAMES = r"(?:claude|chatgpt|" + _GPT + r"|gemini|copilot|grok|siri|alexa)"
# "is this real" and "is this a machine" are about the world, not the
# speaker; "is this" needs a word for a kind of speaker. "Person" needs an
# adjective ("is this a real person") or an alternative after it ("is this
# a person or a bot").
_THIS_TARGET = (
    r"(?:humans?|bots?|chatbots?|ai|npcs?|llms?|chatgpt|" + _GPT + r"|"
    r"(?:real|actual|live|living|genuine) (?:persons?|people|humans?))"
)
_THIS_PERSON = r"(?:persons?|people)"
# Assistant names "is this" reads, without an article as for "are you":
# _NAMES less "chatgpt" and "gpt", which _THIS_TARGET reads already, and
# "gemini", which in a world of galaxies is first a constellation.
_THIS_NAMES = r"(?:claude|copilot|grok|siri|alexa)"
# "Is this a person I'm talking to?" names the speaker as plainly as "is
# this a person or a bot?" does. After "the" it points at something in the
# world: "is this the machine I'm talking to?" asks whether the machine in
# the room is the one, so these words follow only an indefinite article,
# none or a name (:data:`_INDEF_ART`).
_TALKING_TO = r" (?:im|i am) (?:talking|speaking|chatting) (?:to|with)"
# Things that are speakers only when they are said to be speaking.
_SPEAKING_THING = r"(?:machines?|computers?|programs?|robots?|algorithms?|scripts?)"
_SPEAKING = r"(?:talking|speaking|answering|replying|responding|writing|typing)"
# "Made by" a person is an object's history; "made by an AI" is not.
_AI_MAKER = r"(?:ai|ais|llms?|chatgpt|" + _GPT + r"|chatbots?|algorithms?)"
_ADV_WORD = (r"(?:even|actually|really|truly|honestly|secretly|literally|just|"
             r"like|definitely|seriously|still|not|also|maybe|perhaps|possibly|"
             r"in fact)")
_ADV = r"(?:" + _ADV_WORD + r" )*"
_ART = (r"(?:(?:a|an|the|some|some kind of|some sort of|a kind of|a sort of|"
        r"kind of|sort of) )?")
_INDEF_ART = (r"(?:(?:a|an|some|some kind of|some sort of|a kind of|a sort of|"
              r"kind of|sort of) )?")
_ADJ = (r"(?:(?:real|actual|live|living|genuine|true|regular|normal|human|"
        r"fellow) )?")
_NOUN2 = (r"(?: (?:player|being|user|generated|written|powered|driven|"
          r"controlled|response|reply|voice|model|assistant|program|agents?|"
          r"travell?ers?|character|npc))?")
_ALT = r"(?: ,)? or (?:are you |is this |is it )?" + _ART + _ADJ + _TARGET + _NOUN2
# At most three alternatives after the first ("human or a bot or an AI"). An
# alternative can read two ways ("human npc" is an adjective and a target,
# or a target and a noun), so an unbounded run of them doubles the work of
# a failed match with each one (Codex review, 2026-11-07).
_ALTS = r"(?:" + _ALT + r"){0,3}"
# The same alternatives without "the", before a trailing "I'm talking to".
_ALT_INDEF = (r"(?: ,)? or (?:are you |is this |is it )?" + _INDEF_ART + _ADJ + _TARGET
              + _NOUN2)
_ALTS_INDEF = r"(?:" + _ALT_INDEF + r"){0,3}"
_TAIL = (r"(?:(?: ,)? (?:lol|lmao|haha+|tbh|honestly|really|seriously|srsly|"
         r"truly|fr|for real|for sure|though|tho|then|now|right|at all|"
         r"or not|or what|or no|yes or no|be honest|tell me|tell me the truth|"
         r"tell the truth|please|pls|plz|by any chance|in reality|in real life|"
         r"irl|deep down|underneath|too|as well|either|like me|like us|"
         r"behind (?:this|that|it|the screen|these words|the words)|"
         r"on the other end|on the other side))*")
def _name_words(name: str) -> str:
    """A name as the patterns read it ("The Locksmith" is "locksmith")."""
    return re.sub(r"^the ", "", _words(_normalize(name)))


# The only words that may stand where a name stands (beside the question,
# after a greeting or a lead, or as a clause of their own) are names the
# speaker answers to. A request ("help", "open the door", "help me escape")
# is not a name, and a place's own name is not known here.
#
# The names of particular speakers: the wandering cast
# (consciousness.WANDERER_CAST) and the two utility walkers
# (agents/identities.py). Each counts only for its own speaker, which the
# route names in ``own_names``; beside the question, another speaker's
# name means it was put to someone else ("Tessera, are you human?" asked of
# a place or of Vex), so the line takes the normal path (round-5 review of
# 31f1bb8).
_SPEAKER_NAMES = tuple(dict.fromkeys(
    _name_words(name) for name in [*WANDERER_CAST, "Scout", "Observer"]))
# Forms of address every speaker answers to: the four archetypes, the
# eleven scales and plain forms of address. An archetype is a kind that
# several travelers share (agents/personas.py), never one speaker's name
# (no server identity is called "wanderer"), so "good evening, wanderer"
# addresses its listener as "traveler" would. No speaker's name is one.
_ADDRESS_NAMES = tuple(name for name in dict.fromkeys(
    [*AGENT_ANSWERS,
     "multiverse", "universe", "galaxy", "planetary system", "planet",
     "region", "room", "object", "molecule", "atom", "subatomic particle",
     "subatomicparticle", "particle",
     "world", "place", "voice", "spirit", "friend", "stranger", "traveler",
     "traveller", "sir", "madam", "maam", "mate", "pal", "buddy"])
    if name not in _SPEAKER_NAMES)
_NAME_MOD = r"(?:(?:my|old|dear|little|good|kind|wise|fellow|strange|young|the) )"
# Where the speaker's own names join the forms of address
# (:func:`_patterns`). A regex comment, so a pattern reads no own name
# until one is put in its place.
_OWN_NAMES = "(?#own names)"
_NAME = (r"(?:" + _NAME_MOD + r"{0,2}(?:"
         + "|".join(re.escape(n) for n in sorted(_ADDRESS_NAMES, key=len, reverse=True))
         + _OWN_NAMES + r")|" + _NAME_MOD + r"{1,2}one)")
_GREETING = (r"(?:hi|hello|hey|hiya|heya|howdy|greetings|hail|ahoy|yo|"
             r"well met|good (?:morning|afternoon|evening|day|night))")

# A trailing vocative after a comma ("are you human, Tessera?", "are you
# human, old friend?"), never a second clause ("are you real, or am I
# dreaming?") or a request ("are you human, help me escape?").
_VOCATIVE = r"(?: , " + _NAME + r")?"
_END = _TAIL + _VOCATIVE + r"$"

# What may stand before the question inside its clause: a greeting and a
# name ("Tessera, are you human", "hey old friend, are you human"), then
# leads ("be honest, are you an AI"). Nothing else, so "she asked me, are
# you human", "how are you human", "open the door, are you human" and "are
# any of you AI?" are not questions to the speaker.
#
# No lead is two other leads in a row, so a run of leads reads only one
# way. "So tell me" and "tell me honestly" are not listed for that reason:
# they read as "so" + "tell me" and "tell me" + "honestly". Listed, each
# repetition doubled the work of a failed match, and 199 characters of "so
# tell me" took about two seconds (Codex review, 2026-11-07).
_LEADS = (
    "hey", "hi", "hello", "ok", "okay", "so", "wait", "um+", "uh+", "hm+",
    "honestly", "seriously", "really", "quick question", "question",
    "honest question", "serious question", "real question", "one question",
    "one more question", "be honest", "be honest with me", "be straight with me",
    "be truthful", "be real", "be real with me", "level with me",
    "tell me the truth", "tell me", "answer me", "answer honestly",
    "just curious", "curious", "im curious", "i am curious", "out of curiosity",
    "i wonder", "i was wondering", "just wondering", "i have to ask",
    "i need to know", "i have to know", "i gotta ask", "i want to know",
    "i just want to know", "i wanna know", "i must ask", "can i ask", "may i ask",
    "let me ask", "sorry", "lol", "and", "but", "also", "well", "look", "listen",
    "real talk", "truthfully", "genuinely", "yo", "then", "now", "no offense",
    "no offence", "dont lie", "dont lie to me", "for real",
)
_LEAD_PHRASE = r"(?:" + "|".join(_LEADS) + r")"
_LEAD = r"(?:" + _LEAD_PHRASE + r"(?: ,)? )*"
# A greeting may carry "there", "you" or "again", as it may in a clause of
# its own ("Hi there, are you human?", "Hello again, are you an AI?").
_GREETING_TAIL = r"(?:(?: ,)? (?:there|you|again))?"
_PREFIX = (r"^(?:" + _GREETING + _GREETING_TAIL + r"(?: ,)? )?(?:" + _NAME
           + r"(?: ,)? )?" + _LEAD)

# What a "behind / typing / on the other end" question may be about: words
# for this exchange. "This", "it" and "you" alone could be a door or a
# river's far bank, so they need a word for a kind of speaker ("is there a
# human behind this", not "is there anyone behind you").
_SPEAKER_OBJECT = (
    r"(?:these words|the words|your words|this voice|the voice|your voice|"
    r"these messages|this message|your messages|these replies|your replies|"
    r"these answers|your answers|the screen|this screen|your screen|"
    r"the keyboard|this keyboard|your keyboard|this conversation|"
    r"this chat|the chat|this account|your account|this character|"
    r"your character)"
)
_SHORT_OBJECT = r"(?:this|that|it|you|these)"
_EXCHANGE_VERB = (r"(?:behind|typing|writing|controlling|playing|answering|"
                  r"voicing|running|operating)")
_OTHER_END = r"on the other (?:end|side)"
_SOMEONE = r"(?:someone|somebody|anyone|anybody)"
# A person-word: "a human", "a real person", "someone real". A bare
# "person" is not one: "is there a person behind you" is about the room.
_PERSON = (r"(?:(?:real|actual|live|living|genuine) (?:humans?|persons?|people|"
           + _SOMEONE + r")|humans?|" + _SOMEONE + r" real)")
# A word for a kind of speaker: a person-word, or a word for an AI that
# "is this" also reads as a speaker ("is this an AI?", not "is this a
# machine?"). A machine, a robot, an algorithm or a bare "person" running
# "it" is the mill or the clockwork (round-5 review of 31f1bb8).
_KIND = r"(?:" + _PERSON + r"|ai|ais|bots?|chatbots?|llms?|npcs?|chatgpt|" + _GPT + r")"
# What a kind of speaker may be doing: behind this, typing these words,
# answering me, typing, on the other end. "Me" follows only "answering":
# a human behind me or controlling me is about the traveler.
_KIND_DOING = (r"(?:" + _EXCHANGE_VERB + r" (?:" + _SHORT_OBJECT + r"|" + _SPEAKER_OBJECT
               + r")|answering me|typing|" + _OTHER_END + r"(?: of (?:this|it|"
               + _SPEAKER_OBJECT + r"|the line|this line))?)")
# What anyone at all may be doing: only something about this exchange.
_ANYONE_DOING = (r"(?:" + _EXCHANGE_VERB + r" " + _SPEAKER_OBJECT + r"|" + _OTHER_END
                 + r" of (?:" + _SPEAKER_OBJECT + r"|the line|this line))")
# Things that are speakers only when they are said to be at this exchange.
# "Is a machine writing these words?" and "is a robot answering me?" ask
# what the speaker is; "is a machine running it?" asks about the mill
# (round-5 check of the finding-1 fix, which had dropped the first two).
_THING = (r"(?:machines?|computers?|programs?|robots?|algorithms?|scripts?|androids?|"
          r"agents?|persons?|people)")
_KIND_OR_THING = r"(?:" + _KIND + r"|" + _THING + r")"
# "Is there a human behind this?" and "is a human behind this?" are one
# question, so one rule reads both and they never disagree: "is a person
# behind you?" is "is there a person behind you?", about the room.
_WHO_DET = r"(?:(?:a|an|any|some|the|some kind of|some sort of|a kind of|a sort of) )?"
# "The" names a thing already in the world: "is the machine answering me?"
# asks about the one in the room, "is a machine answering me?" about the
# speaker. Before words for this exchange either article asks about the
# speaker ("is the machine writing these words?").
_WHO_SOME_DET = r"(?:(?:a|an|any|some|some kind of|some sort of|a kind of|a sort of) )?"
_KIND_RUN = _KIND + r"(?:(?: ,)? or " + _WHO_DET + _KIND + r"){0,3}"
_THING_RUN = _KIND_OR_THING + r"(?:(?: ,)? or " + _WHO_DET + _KIND_OR_THING + r"){0,3}"
# A run of kinds may be doing anything _KIND_DOING allows. A run with a thing
# in it may only be doing something to this exchange, or answering me
# without "the". Each run is at most four long and reads one way, and the
# branches differ only in which of them reads a run, so a failed match costs
# a constant factor more, not a power of the run's length.
_WHO = (r"is (?:there )?(?:" + _WHO_DET + _KIND_RUN + r" " + _KIND_DOING
        + r"|" + _WHO_DET + _THING_RUN + r" " + _ANYONE_DOING
        + r"|" + _WHO_SOME_DET + _THING_RUN + r" answering me"
        + r"|" + _WHO_DET + _SOMEONE + r" " + _ANYONE_DOING + r")")

# Inverted questions are interrogative without a question mark.
_INVERTED = (
    # are you (even) (a real) human / an AI / a bot (or a person)
    _PREFIX + r"(?:are|arent) you " + _ADV + r"(?:" + _ART + _ADJ + _TARGET
    + _NOUN2 + r"|" + _NAMES + r")" + _ALTS + _END,
    # am I talking to a human / a real person / someone real / an AI
    _PREFIX + r"am i (?:talking|speaking|chatting|typing|writing|messaging|"
    r"texting|interacting) (?:to|with) " + _ADV + _ART + _ADJ
    + r"(?:" + _TARGET + r"|anyone real|anybody real)" + _NOUN2
    + _ALTS + _END,
    # is this an AI / a bot / a real person / AI generated / a person or a
    # bot / Claude
    _PREFIX + r"is this " + _ADV + r"(?:" + _ART + _ADJ + r"(?:" + _THIS_TARGET
    + _NOUN2 + _ALTS + r"|" + _THIS_PERSON + _NOUN2 + r"(?:" + _ALT + r"){1,3})|"
    # an AI I'm talking to / a person I'm talking to / Claude I'm talking to,
    # but not "the machine I'm talking to"
    + _INDEF_ART + _ADJ + r"(?:" + _THIS_TARGET + _NOUN2 + _ALTS_INDEF + r"|"
    + _THIS_PERSON + _NOUN2 + r"(?:" + _ALT_INDEF + r"){0,3})" + _TALKING_TO + r"|"
    + _THIS_NAMES + r"(?:" + _ALTS + r"|" + _ALTS_INDEF + _TALKING_TO + r"))" + _END,
    # is this a machine talking / a program answering / a machine I'm talking to
    _PREFIX + r"is this (?:" + _ART + _SPEAKING_THING + r" " + _SPEAKING + r"|"
    + _INDEF_ART + _SPEAKING_THING + _TALKING_TO + r")" + _END,
    # are you played by a human / run by an AI
    _PREFIX + r"(?:are you|is this) (?:being )?(?:played|controlled|run|"
    r"operated|written|voiced|typed) by " + _ART + _ADJ + _TARGET + _NOUN2
    + _ALTS + _END,
    # are you powered by AI / generated by an LLM
    _PREFIX + r"(?:are you|is this) (?:being )?(?:powered|generated|made|"
    r"driven|created|built|programmed) by " + _ART + _AI_MAKER + _END,
    # I'm human, are you?
    _PREFIX + r"(?:im|i am) " + _ADV + _ART + _ADJ
    + r"(?:humans?|persons?|real|people) , (?:are|arent) you"
    r"(?: too| as well| also| like me)?" + _END,
    # is there a human behind this / is a human writing this / is an AI
    # answering me / is there anyone typing these words / a real person on
    # the other end
    _PREFIX + _WHO + _END,
    # is someone typing this
    _PREFIX + r"is " + _SOMEONE + r" (?:real )?typing (?:this|these|that|"
    + _SPEAKER_OBJECT + r")" + _END,
)

_TAG = (r"(?:(?: ,)? (?:right|arent you|are you|or not|correct|yes|no|huh|eh|"
        r"isnt it|then|too|yeah|yep|innit))?")

# Statements become questions only with a question mark: "you're human?",
# "you're a bot, aren't you?", "you human?", "human or bot?".
_DECLARATIVE = (
    _PREFIX + r"(?:youre|you(?: arent)?) " + _ADV + _ART + _ADJ + _TARGET
    + _NOUN2 + _ALTS + _TAG + _END,
    # "your" for "you're": before an adverb ("your not human"), an article
    # ("your a bot", "your an AI") or a bare "human" or "real". "Your
    # people?", "your machine?" and "your AI?" ask about something it owns.
    _PREFIX + r"your (?:" + _ADV_WORD + r" " + _ADV + _ART + _ADJ + _TARGET + _NOUN2
    + r"|(?:a|an|some|some kind of|some sort of|a kind of|a sort of) " + _ADJ + _TARGET
    + _NOUN2 + r"|human|real)" + _ALTS + _TAG + _END,
    _PREFIX + _ART + _ADJ + r"(?:humans?|persons?|real|people|someone real)"
    + r"(?: ,)? or " + _ART + _ADJ
    + r"(?:bots?|robots?|chatbots?|ai|machines?|computers?|programs?|npcs?|llms?|"
    r"automated|artificial|algorithms?)" + _TAG + _END,
    _PREFIX + _ART
    + r"(?:bots?|robots?|chatbots?|ai|machines?|computers?|programs?|npcs?|llms?)"
    + r"(?: ,)? or " + _ART + _ADJ
    + r"(?:humans?|persons?|real|people|not|someone real)" + _TAG + _END,
)

# A clause that may stand beside the question without asking for more: a
# greeting with a name or leads after it ("hi Tessera, quick question"), a
# name the speaker answers to, leads on their own ("be honest", "just
# curious"), an interjection ("hmm", "wow"), a trailing "yes or no", thanks,
# or "I'm human". Any other word asks for something more ("Are you human?
# Help!", "Hi, open the door. Are you human?").
_INTERJECTION = (r"(?:oh|ah|aha|huh|wow|whoa|woah|ha|hah|haha+|heh|hehe|lmao|"
                 r"omg|ooh|mhm|ugh|alright|right)")
_FILLER = (
    r"^(?:"
    + _GREETING + _GREETING_TAIL + r"(?:(?: ,)? " + _NAME + r")?"
    + r"(?:(?: ,)? " + _LEAD_PHRASE + r")*"
    + r"|" + _NAME
    + r"|" + _LEAD_PHRASE + r"(?:(?: ,)? " + _LEAD_PHRASE + r")*"
    + r"(?: , " + _NAME + r")?"
    + r"|" + _INTERJECTION
    + r"|(?:yes or no|i cant tell|i cant tell anymore|i really cant tell|"
    r"just asking|just checking|thanks|thank you|thanks in advance|"
    r"please|please answer|pls|plz)"
    + r"|(?:im|i am)(?: " + _ADV + _ART + _ADJ + r"(?:human|person|real|people)"
    + r"(?: (?:by the way|btw|myself|too|here))?)?"
    + r")$"
)


@functools.lru_cache(maxsize=32)
def _patterns(own: tuple[str, ...]) -> tuple[
        tuple[re.Pattern[str], ...], tuple[re.Pattern[str], ...], re.Pattern[str]]:
    """The inverted, declarative and filler patterns, reading these own names as names.

    Each name joins the forms of address in every name slot. No name slot
    repeats, so an own name can add a reading to its slot but never to a
    run of leads or alternatives. Compiled once per set of names: a route
    passes one speaker's.
    """
    names = "".join("|" + re.escape(name) for name in own)

    def compiled(pattern: str) -> re.Pattern[str]:
        return re.compile(pattern.replace(_OWN_NAMES, names))

    return (tuple(compiled(p) for p in _INVERTED), tuple(compiled(p) for p in _DECLARATIVE),
            compiled(_FILLER))


_patterns(())  # compiled at import, as the patterns always were


def _own_key(own_names: Iterable[str] | str | None) -> tuple[str, ...]:
    """The speaker's own names as the patterns read them, less the shared forms of address."""
    if own_names is None:
        return ()
    if isinstance(own_names, str):
        own_names = (own_names,)
    words = {_name_words(name) for name in own_names if isinstance(name, str)}
    return tuple(sorted(word for word in words if word and word not in _ADDRESS_NAMES))


def _clauses(text: str) -> list[tuple[str, bool]]:
    """(normalized clause, ended with a question mark) pairs."""
    pieces = re.split(r"([?!.;:\n]+)", _normalize(text))
    clauses = []
    for i in range(0, len(pieces), 2):
        body = pieces[i]
        mark = pieces[i + 1] if i + 1 < len(pieces) else ""
        clause = _words(body)
        if not clause:
            continue
        if clauses and clause.startswith("or "):
            # "Are you human? Or a bot?" is one question; so is "Are you
            # real? Or just a dream?", which is not about being human.
            clause = f"{clauses.pop()[0]} , {clause}"
        clauses.append((clause, "?" in mark))
    return clauses


_ARE_YOU_TOO = re.compile(r"(?:are|arent) you(?: too| as well| also| like me)?")


def _asks(clause: str, asked: bool, inverted: tuple[re.Pattern[str], ...],
          declarative: tuple[re.Pattern[str], ...]) -> bool:
    """Whether this one clause is itself the identity question."""
    if any(p.match(clause) for p in inverted):
        return True
    return asked and any(p.match(clause) for p in declarative)


def is_identity_question(text: object, *, own_names: Iterable[str] | None = ()) -> bool:
    """True when ``text`` is a sincere question whether the speaker is human or an AI.

    English only. Case, punctuation, curly apostrophes, zero-width
    characters and common chat spellings ("r u", "ur", "a.i.") are folded
    first. At least one clause must be the question itself, so words like
    "human" or "bot" inside an ordinary sentence do not trigger it, and
    every other clause must be one that asks for nothing more (a greeting,
    a name, a lead such as "be honest", or "I'm human"; at most three). A
    line over :data:`MAX_CHARS` characters is never one.

    A name beside the question may be a form of address every speaker
    shares or one of ``own_names``, the speaker's own: the inhabitant's
    name for ``/agent/voice``, none for a place. Any other cast member's or
    walker's name means the question was put to someone else, so "Tessera,
    are you human?" asked of a place, or of Vex, is not one.
    """
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > MAX_CHARS:
        return False
    inverted, declarative, filler = _patterns(_own_key(own_names))
    clauses = _clauses(text)
    covered = {i for i, (clause, asked) in enumerate(clauses)
               if _asks(clause, asked, inverted, declarative)}
    # "I'm human. Are you?" spans two clauses; read each such pair as one.
    for i in range(len(clauses) - 1):
        (a, _), (b, asked) = clauses[i], clauses[i + 1]
        if _ARE_YOU_TOO.fullmatch(b) and _asks(f"{a} , {b}", asked, inverted, declarative):
            covered |= {i, i + 1}
    if not covered:
        return False
    rest = [clause for i, (clause, _) in enumerate(clauses) if i not in covered]
    return (len(rest) <= _MAX_FILLER_CLAUSES
            and all(filler.match(clause) for clause in rest))
