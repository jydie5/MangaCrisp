# Project sustainability and reach

MangaCrisp is independent, free MIT-licensed software. This document explains
how the project makes optional support visible and how repository reach is
measured without adding analytics to the application.

## Principles

- MangaCrisp does not upload reading activity, library contents, capture images,
  or usage analytics.
- Payment does not unlock features or change the license.
- Financial and non-financial contributions are both useful.
- Funding links are authoritative only when they are published in this
  repository.

## Support paths

The English and Japanese READMEs place the optional support link near the
download section. `.github/FUNDING.yml` also enables GitHub's repository Sponsor
button and points it to the same Buy Me a Coffee account. The in-app Help dialog
keeps a secondary link for people who already use MangaCrisp.

Financial support is used for practical release costs such as code signing,
Windows and macOS hardware validation, build services, and development AI/API
usage. People can also help by starring or sharing the repository, reporting a
reproducible bug, testing releases on different hardware, and improving code or
documentation.

## What GitHub can show

Repository administrators can use **Insights > Traffic** for rolling 14-day
repository views, unique visitors, full clones, and unique cloners. A clone is
not the same as an installation or an active user; development machines and
automation can contribute to the count.

GitHub release assets expose a cumulative `download_count`. It counts downloads
of each specific asset, not unique people, successful launches, or continued
use. Repeated downloads and automation may be included.

Stars, forks, issues, and pull requests are useful engagement signals, but none
is an active-user count. MangaCrisp deliberately does not add product telemetry
just to obtain that number.

## Maintainer check

The following authenticated GitHub CLI commands provide a reproducible snapshot:

```bash
gh api repos/jydie5/MangaCrisp/traffic/views
gh api repos/jydie5/MangaCrisp/traffic/clones
gh api repos/jydie5/MangaCrisp/releases --paginate \
  --jq '.[] | .assets[] | [.name, .download_count] | @tsv'
gh repo view jydie5/MangaCrisp \
  --json stargazerCount,forkCount,watchers,issues
```

Review these signals monthly rather than putting volatile counters in the
README. Compare release-to-release asset downloads, useful issue reports, and
cross-hardware validation. Treat clone counts as repository activity—not as a
claim about the number of readers.
