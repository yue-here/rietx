# One compact row per open PR from triage.graphql's slurped pages, plus the
# count GitHub reports, so a short listing shows as `rows < open` (WP-2312).
# File lists stay out of the rows: 84 PRs' paths are ~200 kB, the rows ~42 kB.
def data: test("^tests/data/|^src/rietx/data/");
# What the bench runs as build or test machinery: step 4 reads these first and
# the `all` mode batches them. The GUI and docs builds' rows are WP-2313's.
def execution: test("(^|/)conftest\\.py$|^pyproject\\.toml$|^setup\\.py$|^(hatch|uv)\\.toml$|^\\.?pytest\\.ini$|^\\.github/|^\\.claude/hooks/|^\\.claude/settings[^/]*\\.json$|^\\.mcp\\.json$|^gui/(package(-lock)?\\.json|\\.npmrc|\\.postcssrc[^/]*|[^/]*\\.config\\.[^/]+)$|^gui/scripts/|^docs/docs/conf\\.py$");
[.[].data.repository.pullRequests.nodes[]] as $prs
| ([$prs[] | [(.files.nodes // [])[].path] | unique[]] | group_by(.) | map({key: .[0], value: length}) | from_entries) as $owners
| {
  open: .[0].data.repository.pullRequests.totalCount,
  rows: [$prs[] | [(.files.nodes // [])[].path] as $paths | {
    number, title, author: .author.login, headRefOid, updatedAt, isDraft,
    mergeStateStatus, changedFiles, filesListed: ($paths | length),
    reviewable: ([(.files.nodes // [])[] | select(.path | data | not) | .additions + .deletions] | add // 0),
    degree: ([$paths[] | select($owners[.] > 1)] | length),
    governance: [$paths[] | select(test("^docs/ROADMAP\\.md$|^docs/wp/"))
                 | sub("^docs/wp/(?<n>[0-9]{4})-.*"; "WP-\(.n)") | sub("^docs/"; "")],
    execution: [$paths[] | select(execution)],
    latestReviews: [(.latestReviews.nodes // [])[] | {
      author: .author.login, authorAssociation, state, submittedAt, commit: .commit.oid
    }],
    ci: .statusCheckRollup.nodes[0].commit.statusCheckRollup.state,
    commitsTotal: .commits.totalCount,
    wpCommits: ([.commits.nodes[].commit.messageHeadline
                 | capture("^(?<wp>WP-[0-9]{4}):").wp] | unique)
  }]
}
