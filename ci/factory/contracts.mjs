// Contract coverage: every declared contract file exists, and every consumes
// edge has a consumer contract test, kept in the consumer under
// contracts/<provider>/ (any depth), for example
// product/services/orders/contracts/catalog/catalog_contract_test.go.

// services: [{ name, root, service, files }] where files lists the project's
// paths relative to its root.
export function contractProblems(services) {
  const problems = [];
  for (const s of services) {
    for (const c of s.service.contract || []) {
      if (!s.files.includes(c)) problems.push(`${s.name} declares contract ${c}, which doesn't exist`);
    }
    for (const provider of s.service.consumes || []) {
      const covered = s.files.some((f) => new RegExp(`(^|/)contracts/${provider}/.+`).test(f));
      if (!covered) problems.push(`${s.name} consumes ${provider} but has no contract test under contracts/${provider}/`);
    }
  }
  return problems;
}
