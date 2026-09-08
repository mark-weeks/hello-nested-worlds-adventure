"""Atomic acceptance and delivery for staged producers (M1 and M2)."""
import logging
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import persistence
from causality import CausalityBus, EventKind, ORIGIN_STRENGTH
from causality.wiring import record_origin_event, record_verb_act, wire_world_handlers
from multiverse import store


def deliver_due(queue, limit, world_seed, apply, notify, *, prepare=None, notify_batch=None):
    """Deliver each candidate independently; notify only after its commit.

    apply(row, notifications) returns a terminal outcome and collects callback
    arguments. Preparation runs outside the writer lock. Broadcast failures
    never turn committed work into a retry.
    """
    delivered = 0
    committed_notifications = []
    for work_id in persistence.due_work(queue, limit, world_seed):
        notifications = []
        committed = persistence.deliver_work(
            queue, work_id, lambda row: apply(row, notifications),
            prepare=prepare or (lambda row: store.ensure_born(row["world_seed"])))
        if committed:
            delivered += len(notifications)
            if notify_batch is not None:
                committed_notifications.extend(notifications)
            elif notify is not None:
                for args in notifications:
                    try:
                        notify(*args)
                    except Exception:
                        logging.getLogger(__name__).exception(
                            "committed delivery %s:%s broadcast failed", queue, work_id)
    if notify_batch is not None and committed_notifications:
        try:
            notify_batch(committed_notifications)
        except Exception:
            logging.getLogger(__name__).exception("committed %s notification batch failed", queue)
    return delivered


def accept_event(seed, node, kind, data, *, player_name=None, actor_identity=None):
    """Commit the attributed origin, pressure, and its entire first ring."""
    from causality.staging import stage_cascade
    with persistence.transaction():
        changed = record_origin_event(
            seed, node, kind, data, player_name=player_name,
            actor_identity=actor_identity)
        source = persistence.latest_event_id()
        wire_world_handlers(CausalityBus(), seed, record=False).emit(node, kind, data)
        staged = stage_cascade(seed, node, kind, data, source_event_id=source)
    return changed, staged


def work_summary(row):
    """Public pending identity, never queue payloads or private actor identity."""
    from multiverse import delayed_v2
    mode = "legacy"
    if row["semantics_version"] == 2:
        try:
            mode = delayed_v2.policy(json.loads(row["operation"]))
        except (TypeError, ValueError, KeyError):
            mode = "unavailable"
    elif row["semantics_version"] != 1:
        mode = "unavailable"
    return {"id": row["id"], "verb": row["verb"], "policy": mode,
            "semantics_version": row["semantics_version"], "due_at": row["due_at"]}


def accept_verb(seed, node, verb, token, act_data, payload, *,
                player_name=None, actor_identity=None, maturation_actor=None):
    """Serialize live admission, origin, pressure and work for every producer.

    A distinct contribution request gets a new ID. A mark-only request can
    deliberately join pending v2 work; it creates no second origin or ripple.
    Callers broadcast only accepted actions, after this function returns.
    """
    from causality.staging import stage_cascade
    from multiverse import delayed_v2
    from multiverse.verbs import apply_verb, maturation_note, maturation_seconds
    store.ensure_born(seed)
    matures = maturation_seconds(node.level)
    def read_current():
        born = store.resolve_node_by_name(seed, node.name)
        if born is None:
            raise ValueError("no such place in this world")
        return persistence.json_merge_patch(
            born.properties, persistence.load_node_property_override(seed, node.name))

    result = {"changed": None, "matures_in": None, "action_status": "noop",
              "outcome": None, "work": None, "flavor": ""}
    if matures <= 0:
        # A read-only no-op needs no writer reservation. An intended change
        # still re-reads and rechecks below, at the atomic acceptance boundary.
        preview = SimpleNamespace(level=node.level, properties=read_current())
        changed, flavor = apply_verb(preview, verb, token)
        if not changed:
            result.update(outcome="already_satisfied", flavor=flavor)
            return result, 0
    with persistence.transaction():
        current = read_current()
        node.properties = dict(current)
        if matures > 0:
            operation, outcome = delayed_v2.prepare(verb.name, node.level, current)
            if operation is None:
                result.update(outcome=outcome, flavor=delayed_v2.outcome_flavor(verb.name, outcome))
                return result, 0
            if not operation["adjust"]:
                for row in persistence.pending_verb_work(seed, node.name, verb.name):
                    try:
                        accepted = json.loads(row["operation"])
                        # Validate before treating this item as a shared promise.
                        delayed_v2.apply(row["verb"], node.level, current, accepted)
                    except (TypeError, ValueError):
                        continue
                    if accepted["mark"]:
                        due = datetime.fromisoformat(row["due_at"]).replace(tzinfo=timezone.utc)
                        result.update(action_status="shared", work=work_summary(row),
                                      matures_in=max(0, int((due - datetime.now(timezone.utc)).total_seconds())),
                                      flavor=delayed_v2.acceptance_flavor(verb.name, operation, shared=True))
                        result["flavor"] += maturation_note(result["matures_in"])
                        return result, 0
            data = {**act_data, "changed": None, "matures_in": int(matures),
                    "semantics_version": 2, "operation": operation,
                    "policy": delayed_v2.policy(operation)}
            persistence.record_mutation(
                seed, node.name, "SCALE_ACT", player_name, data,
                actor_identity=actor_identity, strength=ORIGIN_STRENGTH)
            source = persistence.latest_event_id()
            work_id = persistence.enqueue_verb_maturation(
                seed, node.name, verb.name, {}, maturation_actor, matures,
                source_event_id=source, operation=operation, actor_identity=actor_identity)
            result.update(work=work_summary(persistence.inspect_work("verb_maturation", work_id)),
                          matures_in=int(matures),
                          flavor=delayed_v2.acceptance_flavor(verb.name, operation) + maturation_note(matures))
        else:
            changed, flavor = apply_verb(node, verb, token)
            result["flavor"] = flavor
            if not changed:
                result["outcome"] = "already_satisfied"
                return result, 0
            result["changed"] = record_verb_act(
                seed, node, verb, token, current, act_data,
                player_name=player_name, actor_identity=actor_identity)
            source = persistence.latest_event_id()
        result["action_status"] = "accepted"
        result["event_id"] = source
        wire_world_handlers(CausalityBus(), seed, record=False).emit(
            node, EventKind.SCALE_ACT, payload)
        staged = stage_cascade(seed, node, EventKind.SCALE_ACT, payload,
                               source_event_id=source)
    return result, staged
