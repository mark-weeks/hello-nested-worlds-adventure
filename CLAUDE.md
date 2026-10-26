@AGENTS.md

## Claude Code: publishing code-review findings

Standing rule set by the repository owner (Mark Weeks) on 2026-10-26. When
Claude Code reviews a pull request in this repository, it posts the findings
to that pull request on GitHub without asking first. This is the owner's
durable authorization for that one category of outbound post; the usual
"show the payload and get a yes" rule still governs every other post, send,
or edit outside the conversation.

How to post:

- One review per review pass, submitted with event `COMMENT` on the head
  commit that was reviewed. Never `APPROVE` or `REQUEST_CHANGES`; never merge.
- One inline comment per finding, anchored to a line that is in the diff
  (`/code-review --comment` does this). A finding with no diff line to anchor
  to goes in the review body instead.
- The review body carries the takeaway, the finding counts by group, and
  whether the findings were traced by reading the code or by executing it.
- Every comment and the review body end with the Claude Code attribution
  footer.

The rule authorizes posting findings. It does not authorize applying fixes to
the reviewed branch, resolving threads, or any other change to the pull
request; those still follow AGENTS.md "Verification and completion".
