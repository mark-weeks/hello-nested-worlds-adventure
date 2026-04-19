# agents/behaviors.py

from enum import Enum, auto


class State(Enum):
    IDLE = auto()
    EXPLORE = auto()
    INTERACT = auto()
    EXIT = auto()


def should_preserve(node, danger_threshold: int = 6) -> bool:
    return node.properties.get("danger_level", 0) > danger_threshold


def should_interact(node) -> bool:
    return node.properties.get("interactive", False) or node.properties.get("has_puzzle", False)


def should_exit(node) -> bool:
    return node.properties.get("locked", False) and not node.children


def transition(state: State, node) -> State:
    if state == State.IDLE:
        return State.EXPLORE

    if state == State.EXPLORE:
        if should_preserve(node):
            return State.EXIT
        if should_interact(node):
            return State.INTERACT
        if should_exit(node):
            return State.EXIT
        return State.EXPLORE

    if state == State.INTERACT:
        return State.EXPLORE

    return State.EXIT
