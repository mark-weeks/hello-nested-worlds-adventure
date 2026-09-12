import pytest
from scripts.pilot_report import report


def test_distinct_denominators_and_unknown_are_not_negative_observations():
    result = report([
        {'participant': 'A', 'curiosity': True, 'understood_choice': False,
         'unprompted_return': True, 'reminded': False, 'useful_return': True},
        {'participant': 'B', 'curiosity': True, 'unprompted_return': False},
        {'participant': 'C'},
    ])
    assert result['participants'] == 3
    assert result['metrics']['curiosity'] == {'yes': 2, 'observed': 2, 'unknown': 1}
    assert result['metrics']['unprompted_return'] == {'yes': 1, 'observed': 2, 'unknown': 1}
    assert result['metrics']['useful_return'] == {'yes': 1, 'observed': 1, 'unknown': 2}


def test_reminder_and_repeat_session_cannot_inflate_retention():
    with pytest.raises(ValueError):
        report([{'participant': 'A', 'unprompted_return': True, 'reminded': True}])
    with pytest.raises(ValueError):
        report([{'participant': 'A'}, {'participant': 'A'}])
