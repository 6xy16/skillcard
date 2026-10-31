# skillcard trigger benchmark

- cases: 15
- decided (non-borderline): 13
- agreed: 12
- accuracy: 92.3%
- false-positive rate: 0.0%
- false-negative rate: 0.0%

## Limitations

This is a programmatic (lexical-overlap) approximation, not a real agent.
It reads only the skill's self-description, ignores steps/examples, and will
miss semantic matches (e.g. 'PR review' vs 'check my code') and multi-step
intents. The sample is deliberately small (a sanity check, not a leaderboard).
Treat these numbers as a baseline a real agent scorer must beat, not as a
claim about real-world trigger accuracy.

## Borderline / skipped

- `do something with my stuff` (expected borderline, predicted borderline)
- `write a novel` (expected no_trigger, predicted borderline)
- `whatever you think is best` (expected borderline, predicted borderline)

