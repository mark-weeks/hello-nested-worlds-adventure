# puzzles/types.py

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class PuzzleKind(Enum):
    RIDDLE = auto()       # Answer a question correctly
    SEQUENCE = auto()     # Enter items in the right order
    CIPHER = auto()       # Decode an encoded message
    LOCK = auto()         # Supply the correct key/code
    PATTERN = auto()      # Identify or complete a numeric/symbolic pattern
    LOGIC = auto()        # Deductive or lateral thinking puzzle
    ANAGRAM = auto()      # Unscramble letters to form a word or phrase
    NAVIGATION = auto()   # Follow spatial instructions and determine a result


class PuzzleResult(Enum):
    UNSOLVED = auto()
    SOLVED = auto()
    FAILED = auto()


@dataclass
class Puzzle:
    name: str
    kind: PuzzleKind
    prompt: str
    answer: str                          # canonical correct answer (lowercased)
    hints: List[str] = field(default_factory=list)
    max_attempts: int = 3
    attempts: int = 0
    result: PuzzleResult = PuzzleResult.UNSOLVED

    def attempt(self, guess: str) -> PuzzleResult:
        if self.result != PuzzleResult.UNSOLVED:
            return self.result

        self.attempts += 1
        if guess.strip().lower() == self.answer.lower():
            self.result = PuzzleResult.SOLVED
        elif self.attempts >= self.max_attempts:
            self.result = PuzzleResult.FAILED

        return self.result

    def hint(self) -> Optional[str]:
        if not self.hints or self.attempts < 1:
            return None
        idx = min(self.attempts, len(self.hints)) - 1
        return self.hints[idx]

    @property
    def solved(self) -> bool:
        return self.result == PuzzleResult.SOLVED

    @property
    def failed(self) -> bool:
        return self.result == PuzzleResult.FAILED
