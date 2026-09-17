"""Small, game-agnostic Duck prompt treatment for state-dependent controls."""

AFFORDANCE_ADDENDUM = """

State-dependent action rule:
- A click that changes nothing only shows that the action did not work in the
  current board configuration. Do not conclude that a salient button, lever,
  switch, or submit/confirm control is decorative in every configuration.
- If you have changed a candidate puzzle state meaningfully, test a plausible
  confirm/submit control once before rejecting the candidate goal. Re-test
  previously inert controls only after relevant state changes, never repeatedly
  on the unchanged board. Treat a level transition or reward as the evidence.
- Preserve the distinction between an action's immediate board effect and its
  conditional role in completing a level; do not assert a global no-op rule
  from one failed click.
"""


def add_affordance_instruction(agent: object) -> None:
    """Append once to this session's system prompt, leaving control agents alone."""
    if AFFORDANCE_ADDENDUM not in agent._system_prompt:
        agent._system_prompt += AFFORDANCE_ADDENDUM
