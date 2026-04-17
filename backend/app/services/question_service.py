def default_follow_up_questions() -> list[dict]:
    return [
        {
            'question_id': 'q1',
            'label': 'Nausea or vomiting',
            'input_type': 'boolean',
            'required': True,
        },
        {
            'question_id': 'q2',
            'label': 'Fever higher than 38°C (100.4°F)',
            'input_type': 'boolean',
            'required': True,
        },
        {
            'question_id': 'q3',
            'label': 'Heavy sweating / cold sweat',
            'input_type': 'boolean',
            'required': True,
        },
        {
            'question_id': 'q4',
            'label': 'Blurred or double vision',
            'input_type': 'boolean',
            'required': True,
        },
    ]
