# puzzles/types.py

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional


class PuzzleKind(Enum):
    RIDDLE = auto()       # Answer a question correctly
    SEQUENCE = auto()     # Enter items in the right order
    CIPHER = auto()       # Decode an encoded message
    LOCK = auto()         # Supply the correct key/code


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
        used = min(self.attempts, len(self.hints))
        return self.hints[used - 1] if used > 0 and self.hints else None

    @property
    def solved(self) -> bool:
        return self.result == PuzzleResult.SOLVED

    @property
    def failed(self) -> bool:
        return self.result == PuzzleResult.FAILED
