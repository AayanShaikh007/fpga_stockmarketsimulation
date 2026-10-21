# Agent work log

The user requires all agent work in this repository to be recorded in
`code_agent.md`. Read that log before starting work. Append a dated entry for
each task before finishing, covering the request, changes or actions, validation
results, and any unresolved issues or next steps. Include failed attempts and
their resolutions when material. Distinguish measured hardware results from
simulation and estimates. Preserve existing history; do not log secrets.

Keep the log current as work proceeds, including troubleshooting and tasks that
do not change source files. Do not claim actions were completed without evidence.

Use focused commits for meaningful completed changes, including during dashboard
development. The user prefers a detailed, reasonable history; do not inflate the
count with artificial splits, fabricated work, or backdated commits. Keep builds,
virtual environments, downloaded tools, and secrets out of version control.

Keep the dashboard introduction current whenever adding or changing user-facing
features. Update `frontend/src/onboardingContent.ts` with accurate workflows and
limits, and bump `GUIDE_VERSION` when users should see the revised introduction.
Preserve the close/skip controls, manual reopening, keyboard access, and reduced
motion support. The guide must never start runs or send hardware commands.
