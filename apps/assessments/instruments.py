"""
Validated screening instruments. PHQ-9 and GAD-7 are in the public domain (Pfizer, Spitzer et al.);
WHO-5 is free to use (WHO Regional Office for Europe). Scoring is done server-side only.
These are screening tools, NOT diagnoses: copy shown to the student says so.
"""

FREQ = [
    {'value': 0, 'label': 'Not at all'},
    {'value': 1, 'label': 'Several days'},
    {'value': 2, 'label': 'More than half the days'},
    {'value': 3, 'label': 'Nearly every day'},
]

WHO5_OPTIONS = [
    {'value': 0, 'label': 'At no time'},
    {'value': 1, 'label': 'Some of the time'},
    {'value': 2, 'label': 'Less than half the time'},
    {'value': 3, 'label': 'More than half the time'},
    {'value': 4, 'label': 'Most of the time'},
    {'value': 5, 'label': 'All of the time'},
]

INSTRUMENTS = {
    'phq9': {
        'key': 'phq9',
        'title': 'Mood check (PHQ-9)',
        'blurb': 'Nine quick questions about low mood. About 2 minutes.',
        'prompt': 'Over the last 2 weeks, how often have you been bothered by:',
        'options': FREQ,
        'higher_is_better': False,
        'max_score': 27,
        'questions': [
            'Little interest or pleasure in doing things',
            'Feeling down, depressed, or hopeless',
            'Trouble falling or staying asleep, or sleeping too much',
            'Feeling tired or having little energy',
            'Poor appetite or overeating',
            'Feeling bad about yourself, or that you are a failure or have let yourself or your family down',
            'Trouble concentrating on things, such as reading or watching TV',
            'Moving or speaking so slowly that others noticed, or being so restless you move around a lot more than usual',
            'Thoughts that you would be better off dead, or of hurting yourself in some way',
        ],
        'risk_item': 8,  # zero-based index of the self-harm question
        'bands': [(4, 'minimal', 'Minimal'), (9, 'mild', 'Mild'), (14, 'moderate', 'Moderate'),
                  (19, 'moderately_severe', 'Moderately severe'), (27, 'severe', 'Severe')],
    },
    'gad7': {
        'key': 'gad7',
        'title': 'Anxiety check (GAD-7)',
        'blurb': 'Seven quick questions about worry and anxiety. About 1 minute.',
        'prompt': 'Over the last 2 weeks, how often have you been bothered by:',
        'options': FREQ,
        'higher_is_better': False,
        'max_score': 21,
        'questions': [
            'Feeling nervous, anxious, or on edge',
            'Not being able to stop or control worrying',
            'Worrying too much about different things',
            'Trouble relaxing',
            'Being so restless that it is hard to sit still',
            'Becoming easily annoyed or irritable',
            'Feeling afraid, as if something awful might happen',
        ],
        'risk_item': None,
        'bands': [(4, 'minimal', 'Minimal'), (9, 'mild', 'Mild'), (14, 'moderate', 'Moderate'),
                  (21, 'severe', 'Severe')],
    },
    'who5': {
        'key': 'who5',
        'title': 'Wellbeing check (WHO-5)',
        'blurb': 'Five questions about how you have been feeling. Under a minute.',
        'prompt': 'Over the last 2 weeks:',
        'options': WHO5_OPTIONS,
        'higher_is_better': True,
        'max_score': 100,
        'questions': [
            'I have felt cheerful and in good spirits',
            'I have felt calm and relaxed',
            'I have felt active and vigorous',
            'I woke up feeling fresh and rested',
            'My daily life has been filled with things that interest me',
        ],
        'risk_item': None,
        'multiplier': 4,  # raw 0-25 -> percentage 0-100
        'bands': [(27, 'very_low', 'Very low wellbeing'), (49, 'low', 'Low wellbeing'),
                  (100, 'good', 'Good wellbeing')],
    },
}

ADVICE = {
    'minimal': 'Your answers suggest you are doing okay right now. Keep up what is working for you.',
    'mild': 'You may be having a tough time. Small steps help: sleep, movement, and talking to someone you trust.',
    'moderate': 'This looks like a lot to carry. Talking to a counsellor would help. You can book one here.',
    'moderately_severe': 'You are carrying a lot. Please talk to a counsellor soon. You can book one here or chat anonymously now.',
    'severe': 'Your answers suggest you need support. Please talk to a counsellor today. You can chat anonymously right now.',
    'very_low': 'Your wellbeing looks very low. Please talk to a counsellor. You can chat anonymously right now.',
    'low': 'Your wellbeing looks low. A conversation with a counsellor could help. You can book one here.',
    'good': 'Your wellbeing looks good. Keep doing what is working for you.',
}

# severities that should nudge towards a human right away
ELEVATED = {'moderately_severe', 'severe', 'very_low'}


def public_view(inst):
    """Instrument definition safe to send to the client (no scoring internals)."""
    return {k: inst[k] for k in ('key', 'title', 'blurb', 'prompt', 'options', 'questions', 'higher_is_better', 'max_score')}


def score(key, answers):
    inst = INSTRUMENTS[key]
    values = [a for a in answers]
    raw = sum(values)
    total = raw * inst.get('multiplier', 1)
    band = next((b for b in inst['bands'] if total <= b[0]), inst['bands'][-1])
    risk = False
    if inst['risk_item'] is not None:
        risk = values[inst['risk_item']] > 0
    return {
        'score': total, 'severity': band[1], 'severity_label': band[2],
        'risk_flag': risk, 'advice': ADVICE[band[1]],
        'elevated': band[1] in ELEVATED or risk,
    }
