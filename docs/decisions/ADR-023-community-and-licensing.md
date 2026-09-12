# ADR-023: Community participation, contribution scope, and licensing

**Status:** Accepted by Mark Weeks, 2026-09-12. The owner explicitly adopted
this direction and authorized its implementation. Publication, merge, and
deployment remain separate actions under the existing repository policy.

## Context

Enfolded needs people who play, return, and shape its shared experience.
Community, accumulated world history, and the quality of the hosted experience
are the intended durable advantages. Coding agents already provide substantial
implementation capacity; additional code volume is not the community goal.

Licensing was deliberately deferred during development. The README nevertheless
contained an MIT label without a complete license file or package license
metadata. That inconsistent representation must be reconciled. Commit history
records the owner and coding-agent identities; it is not proof of ownership of
every line or asset. Vendored browser libraries retain their own licenses.

## Decision

1. Adopt Apache License 2.0 for Enfolded's own code and documentation. Preserve
   third-party notices and terms, including those of bundled browser libraries.
   Apply the decision to this revision and future contributions; make no claim
   to revoke rights that may have been granted for earlier revisions. Code
   licensing grants neither hosted-service access nor trademark rights beyond
   the license's terms, and does not publish the hosted world's database.
2. Lead community participation with playtesting, shared discoveries, helping
   newcomers, problem reports, and verification of improvements. Keep the
   feedback-to-decision-to-result connection visible and acknowledge this work.
3. Retain maintainer control of priorities, scope, review, and acceptance.
   Coding agents are the default implementation support. Outside PRs require
   prior agreement on scope; use the same quality standards for human and
   AI-assisted submissions. Agent use does not remove responsibility for
   understanding, testing, rights, or attribution.
4. Accept intentional contributions under the project's Apache-2.0 terms,
   with any exception agreed explicitly before incorporation. Require neither
   copyright assignment nor an additional contributor agreement by default.
5. Evaluate the first cohort through returns, interaction, useful reports,
   verified improvements, and sustained contributor interest, with explicit
   denominators and honest gaps. Expand contributor opportunities when actual
   interest and review capacity justify them.

The owner's preferred feedback surface is an in-game Ideas board with voting.
Its application/storage design is a separate implementation scope; this record
does not represent it as live or authorize automatic GitHub publication.

## Trade-offs accepted

- Apache-2.0 permits commercial reuse and forks subject to its terms; compliant
  recipients retain the granted rights. Enfolded's advantage must grow through
  adoption and the hosted experience rather than exclusive access to source.
- Prior agreement on PRs limits unsolicited work and protects contributor time,
  while requiring maintainers to communicate decisions and available scope.
- Some developers will prefer a more open contribution process. Keep a route
  for specialist fixes and sustained collaborators instead of a permanent ban.
- Feedback creates a responsibility to listen and explain decisions, without
  making every request a commitment or treating votes as automatic approval.

## Revisit when

- A recurring collaborator wants ownership of an area: define responsibility,
  review capacity, and permissions explicitly before expanding access.
- Review demand exceeds capacity: adjust available contribution scope and
  expectations using observed workload.
- A licensing conflict, ownership question, or different distribution model
  appears: assess the affected material and existing grants before changing terms.
- The first cohort shows weak return or participation: revise the experience
  and feedback process before optimizing for more PRs.

## Rejected alternatives

- Remaining indefinitely unlicensed to preserve flexibility: it leaves reuse
  unclear and outside contributions can complicate later rights decisions.
- Accepting all PRs by default: code volume does not establish player value or
  remove long-term maintenance costs.
- Permanently excluding outside code and rewriting every patch with agents:
  this can discard specialist evidence, duplicate work, and obscure attribution.
- Treating every idea or vote as an implementation instruction: priorities,
  architecture, and acceptance remain accountable maintainer decisions.

## References

- [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)
- [GitHub contribution terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#6-contributions-under-repository-license)
- [Copyright protects expression, not ideas](https://www.copyright.gov/help/faq/faq-protect.html)
