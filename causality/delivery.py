"""Atomic acceptance for the existing staged producers (M1, legacy rules)."""
import persistence
from causality import CausalityBus, EventKind, ORIGIN_STRENGTH
from causality.staging import stage_cascade
from causality.wiring import record_origin_event, record_verb_act, wire_world_handlers


def accept_event(seed, node, kind, data, *, player_name=None, actor_identity=None):
    """Commit the attributed origin, pressure, and its entire first ring."""
    with persistence.transaction():
        changed = record_origin_event(
            seed, node, kind, data, player_name=player_name,
            actor_identity=actor_identity)
        source = persistence.latest_event_id()
        wire_world_handlers(CausalityBus(), seed, record=False).emit(node, kind, data)
        staged = stage_cascade(seed, node, kind, data, source_event_id=source)
    return changed, staged


def accept_verb(seed, node, verb, token, base_props, changed, matures,
                act_data, payload, *, player_name=None, actor_identity=None,
                maturation_actor=None):
    """One acceptance boundary for HTTP, CLI and cast scale actions.

    v1 keeps delayed ABSOLUTE patches, even overlapping ones. M2 must choose
    prospective contribution/coalescing policies; equal patches aren't retries.
    The caller computes flavor before this function and broadcasts afterwards.
    """
    with persistence.transaction():
        if matures > 0:
            persistence.record_mutation(
                seed, node.name, "SCALE_ACT", player_name,
                {**act_data, "changed": changed, "matures_in": int(matures)},
                actor_identity=actor_identity, strength=ORIGIN_STRENGTH)
            source = persistence.latest_event_id()
            persistence.enqueue_verb_maturation(
                seed, node.name, verb.name, changed, maturation_actor, matures,
                source_event_id=source)
        else:
            changed = record_verb_act(
                seed, node, verb, token, base_props, act_data,
                player_name=player_name, actor_identity=actor_identity)
            source = persistence.latest_event_id()
        wire_world_handlers(CausalityBus(), seed, record=False).emit(
            node, EventKind.SCALE_ACT, payload)
        staged = stage_cascade(seed, node, EventKind.SCALE_ACT, payload,
                               source_event_id=source)
    return changed, staged
