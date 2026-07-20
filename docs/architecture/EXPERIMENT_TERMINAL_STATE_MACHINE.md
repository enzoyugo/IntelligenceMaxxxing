# Experiment Terminal State Machine (Stage 3.1)

States include: `REGISTERED`, `COLLECTING_BASELINE`, `PROSPECTIVE_COLLECTING`,
`TERMINAL_SUPPORTED`, `TERMINAL_WEAKENED`, `TERMINAL_INCONCLUSIVE`,
`EXPIRED_INCONCLUSIVE`, `RETIRED`, `DATA_QUALITY_BLOCKED`.

## Interim vs terminal

- **INTERIM_EVALUATION**: EvidenceSnapshot + non-terminal BeliefSnapshot + progress.
  No OutcomeEvaluation, LearningRecord, or experiment completion.
- **TERMINAL_EVALUATION**: only when target reached, window expired, human retire,
  or governed data-quality termination.

Prospective terminal support requires:

`prospective_total >= prospective_target` AND both groups ≥ `minimum_group_size`
AND no critical data-quality failure.

Belief state `PROSPECTIVE_COLLECTING` is used before closure. Strong effects cannot
bypass an incomplete target.
