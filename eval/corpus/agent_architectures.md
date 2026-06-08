# The Planner–Critic Pattern in Multi-Agent Systems

Complex tasks are often handled by a team of specialized agents rather than a single
monolithic prompt. One common arrangement is the planner-critic pattern.

In a planner-critic architecture, a planner decomposes a task into steps and a critic
reviews intermediate results. The planner turns a broad goal into a set of focused
sub-tasks; downstream agents carry them out; and the critic then judges the work
against the original goal.

The critic is what makes the system self-correcting. The critic can send work back
for another pass when it finds gaps or unsupported claims, forming a bounded feedback
loop. The loop is bounded by a maximum number of iterations so the system always
terminates rather than revising forever.

The payoff is quality. The critic loop improves output quality by catching errors
before the final result is produced. This avoids returning a first draft that may be
incomplete or unsupported, mirroring how a human analyst drafts, reviews, and
revises before publishing.
