// Time budget evidence: how long this PR's feedback took against its tier's
// budget. Hard limits are enforced as job and step timeouts in the workflow.
export function feedbackBudget(tier, startedAt, now, policy) {
  const limits = policy.feedback[tier];
  const minutes = Math.round(((now - new Date(startedAt)) / 60000) * 10) / 10;
  return { minutes, ...limits, ok: minutes <= limits.budget };
}
