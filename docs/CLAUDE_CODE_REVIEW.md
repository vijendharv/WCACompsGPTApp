# Claude Code Review

This repository runs an automated Claude review when a pull request is opened
or updated. The workflow lives in `.github/workflows/claude-review.yml`.

## Current Design

The review intentionally uses one `claude-haiku-4-5` agent instead of the
multi-agent code-review plugin. It:

1. Reads the pull request diff and root `CLAUDE.md`.
2. Reviews only changed files and minimal surrounding context.
3. Does not launch subagents, run tests or builds, or scan unrelated modules.
4. Reports only high-confidence bugs, regressions, security issues, and clear
   `CLAUDE.md` violations.
5. Posts exactly one pull request comment, including an explicit clean result
   when no issues are found.

The action has a `$0.10` maximum budget per run. Reaching that limit fails the
review instead of allowing unbounded spend. GitHub and Claude tool permissions
remain limited to reading the repository and pull request, reading the diff,
and posting a pull request comment.

`show_full_output: true` is currently enabled to diagnose tool use and cost.
Full output can include repository context in Actions logs and should be
disabled after the workflow has been validated.

## Iterations

### 1. Missing Checkout

The first workflow invoked `anthropics/claude-code-action@v1` without checking
out the repository. The action failed while running `git fetch` because its
working directory was not a Git repository. Adding `actions/checkout@v4`
resolved the failure.

### 2. Five-Turn Limit

The initial `--max-turns 5` limit stopped the review before completion. The run
needed a sixth turn and exited with `error_max_turns`. Removing the limit let
the plugin finish, but exposed a much larger cost problem.

### 3. Workflow Validation

The action protects pull requests from changing the review workflow they are
running. If `.github/workflows/claude-review.yml` differs from the default
branch, the action skips execution. Workflow changes therefore need a separate
pull request, must be merged first, and must then be synchronized into the pull
request used to test them.

### 4. No Visible Review

The code-review plugin defaults to terminal output. Without its `--comment`
argument, a successful run can publish no pull request feedback. Because the
action hides full model output by default, this looked like a successful review
with no result.

### 5. GitHub And Tool Permissions

GitHub workflow permissions and Claude tool permissions are separate:

- `pull-requests: write` and `issues: write` allow the workflow token to post.
- `--allowedTools` controls which commands Claude may run non-interactively.

Adding comment permissions and the plugin's declared `gh` tools made review
results visible. Broad permissions such as `Bash(*)`, repository content
writes, or permission bypasses were deliberately avoided.

### 6. Multi-Agent Cost

Setting the parent model to Haiku did not make the plugin Haiku-only. The
plugin launched Haiku, Sonnet, and Opus subagents for summarization, parallel
review, and finding validation. Observed runs used 18-30 turns, cost roughly
`$0.47-$0.64` according to the action, and one provider report showed about
1.8 million processed tokens.

The additional agents found a valid missing direct Starlette dependency, but
the cost was too high for this repository's pull requests.

### 7. Full Output Diagnostics

Enabling `show_full_output` revealed that remaining denials were optional
inspection commands such as `git log`, Python import probes, package inspection,
and test execution. Required pull request reads and comments succeeded. Those
commands were left denied because automated review should consume the existing
diff and validation summary rather than rerun tests or explore the environment.

### 8. Single-Pass Review

The workflow now uses a direct prompt instead of the multi-agent plugin. This
keeps the review on the changed diff, uses only Haiku, avoids duplicate agents,
and places an explicit dollar ceiling on each run.

## Lessons Learned

- A green action is not proof that a review was performed or published; inspect
  the result subtype and the pull request comments.
- Always include `actions/checkout` before tools that expect a Git repository.
- Merge workflow changes before testing them on another pull request.
- Configure GitHub token scopes and Claude tool permissions independently.
- Require an explicit clean-review comment so "no findings" is auditable.
- A parent `--model` option does not override models hardcoded by subagents.
- Prefer one narrowly scoped review before adopting a costly multi-agent pass.
- Keep permissions read-only except for the single required comment action.
- Use full output temporarily for diagnostics, then turn it off.

## Troubleshooting

When a review fails or produces no comment:

1. Confirm the workflow file matches the version on `master`.
2. Confirm `ANTHROPIC_API_KEY` is configured as a repository secret.
3. Check that checkout completed before the Claude action.
4. Inspect the final result subtype, cost, turns, and permission denials.
5. Verify that the prompt explicitly tells Claude to post a comment.
6. Grant only the specific denied tool that is necessary for reviewing the
   pull request diff or publishing the result.
