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


def test_whitespace_aliases_cannot_inflate_participant_denominators():
    with pytest.raises(ValueError, match='one row per participant'):
        report([{'participant': 'P01', 'curiosity': True},
                {'participant': ' P01\t', 'curiosity': True}])


def test_current_protocol_separates_action_from_observed_consequence():
    result = report({'protocol_version': 2, 'participants': [
        {'participant': 'A', 'curiosity': True, 'acted': True,
         'understood_action': True, 'understood_consequence': False,
         'return_window_complete': True, 'unprompted_return': True,
         'reminded': False, 'observed_return': True, 'useful_return': True},
        {'participant': 'B', 'acted': False},
    ]})
    assert result['protocol_version'] == 2
    assert 'understood_choice' not in result['metrics']
    assert result['metrics']['understood_action'] == {'yes': 1, 'observed': 1, 'unknown': 1}
    assert result['metrics']['understood_consequence'] == {'yes': 0, 'observed': 1, 'unknown': 1}


@pytest.mark.parametrize('fields', [
    {'understood_choice': True},
    {'understood_action': False, 'acted': False},
    {'understood_consequence': True},
    {'unprompted_return': False, 'return_window_complete': False},
    {'useful_return': False, 'observed_return': False},
    {'unprompted_return': True, 'return_window_complete': True, 'reminded': True},
    {'acted': 'yes'},
])
def test_current_protocol_cannot_count_ineligible_or_legacy_observations(fields):
    with pytest.raises(ValueError):
        report({'protocol_version': 2, 'participants': [{'participant': 'P01', **fields}]})


def test_legacy_results_are_labeled_and_not_reinterpreted():
    result = report([{'participant': 'P01', 'understood_choice': True}])
    assert result['protocol_version'] == 1
    assert 'not comparable' in result['interpretation']
    assert 'understood_action' not in result['metrics']
