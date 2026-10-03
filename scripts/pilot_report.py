"""Summarize separately consented pilot observations; never reads/writes the world DB.

Input: a protocol-2 JSON object (or a legacy list), one pseudonymous participant
per row. Missing observations remain unknown. Return measurements distinguish an unprompted second visit from
an answer to a reminder. The operator chooses the evidence window before recruiting.
"""
import argparse
import json
from pathlib import Path

LEGACY_METRICS = ('curiosity', 'understood_choice', 'unprompted_return', 'useful_return')
METRICS = ('curiosity', 'understood_action', 'understood_consequence',
           'unprompted_return', 'useful_return')


def report(observations):
    # Preserve old research as old research, never reinterpret a scripted choice.
    legacy = isinstance(observations, list)
    if legacy:
        rows, metrics = observations, LEGACY_METRICS
    elif isinstance(observations, dict) and observations.get('protocol_version') == 2:
        if set(observations) - {'protocol_version', 'participants'}:
            raise ValueError('Unknown top-level field; keep evidence notes separately.')
        rows, metrics = observations.get('participants'), METRICS
    else:
        raise ValueError('Expected protocol_version=2 with participants, or a legacy list.')
    if not isinstance(rows, list):
        raise ValueError('Expected one list of participant observations.')
    seen = set()
    result = {metric: {'yes': 0, 'observed': 0, 'unknown': 0} for metric in metrics}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('participant'), str) or not row['participant'].strip():
            raise ValueError('Each observation needs a pseudonymous participant.')
        participant = row['participant'].strip()
        if participant in seen:
            raise ValueError('Use one row per participant, not one per session.')
        seen.add(participant)
        if not legacy:
            flags = ('acted', 'observed_return', 'return_window_complete', 'reminded')
            if set(row) - {'participant', *metrics, *flags}:
                raise ValueError('Unknown observation field; keep evidence notes separately.')
            for flag in flags:
                if row.get(flag) is not None and not isinstance(row[flag], bool):
                    raise ValueError(f'{flag} must be true, false, or null.')
            for metric in ('understood_action', 'understood_consequence'):
                if row.get(metric) is not None and row.get('acted') is not True:
                    raise ValueError(f'{metric} requires acted=true; observers remain unknown.')
            if row.get('useful_return') is not None and row.get('observed_return') is not True:
                raise ValueError('useful_return requires observed_return=true.')
            if row.get('unprompted_return') is not None and row.get('return_window_complete') is not True:
                raise ValueError('Score unprompted_return only after the complete return window.')
        for metric in metrics:
            value = row.get(metric)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f'{metric} must be true, false, or null.')
            if metric == 'unprompted_return' and value and row.get('reminded') is not False:
                raise ValueError('An unprompted return requires reminded=false evidence.')
            bucket = result[metric]
            bucket['unknown' if value is None else 'observed'] += 1
            if value is True:
                bucket['yes'] += 1
    return {'protocol_version': 1 if legacy else 2,
            'participants': len(seen), 'metrics': result,
            'interpretation': ('Legacy scripted-choice observations; not comparable to protocol 2. '
                               if legacy else '') +
            'Observation counts; no causal attribution or retention claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observations', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(report(json.loads(args.observations.read_text())), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
