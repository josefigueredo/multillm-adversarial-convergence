# Iteration 002 — Community activity, maintenance status, and bus factor

**Status:** keep  
**Scores:** coverage=67.5, quality=60.0, total=63.0  
**Timestamp:** 2026-04-24T01:04:06.968005+00:00  

---

I now have all primary-source data needed. Here is the research report for this iteration:

---

## Findings

### Context: Both Projects Are Extremely Young

Neither Floci nor MiniStack existed before LocalStack's March 2026 sunset. As of April 23, 2026:
- **Floci (floci-io/floci)** is **~65 days old** (created [2026-02-18](https://github.com/floci-io/floci))
- **MiniStack (ministackorg/ministack)** is **~30 days old** (created [2026-03-24](https://github.com/ministackorg/ministack))

This is the most important framing for all community metrics: every number below reflects a very short window of activity. Neither project has weathered a year of production use, a major AWS API breaking change, or a sustained drop in contributor enthusiasm.

---

### Floci (floci-io/floci): Community Metrics

**Stars & Forks:**
[GitHub API](https://api.github.com/repos/floci-io/floci) confirms **4,140 stars** and **280 forks** as of April 23, 2026. [Trendshift](https://trendshift.io/repositories/25152) places it in the top-trending repositories for Q1 2026.

**Contributors:**
60 unique contributors [Trendshift], of which the top human contributors by commit count are:
1. **hectorvent** (Héctor Martínez) — 109 commits (~29% of ~380 total)
2. **hampsterx** — 55 commits (~14%)
3. **fredpena** — 22 commits (~6%)
4. **ctnnguyen** — 13 commits (~3%)

The semantic-release-bot accounts for 16 automated commits and should be excluded from bus-factor analysis.

**Commit frequency:**
~380 commits across ~65 days = ~6 commits/day average. The CHANGELOG and GitHub releases show continuous daily/every-two-days activity from multiple authors.

**Release cadence:**
- v1.5.7 published [2026-04-23](https://github.com/floci-io/floci/releases/tag/1.5.7) — contains 18 PRs from 12 distinct contributors
- v1.5.5 published [2026-04-18](https://newreleases.io/project/github/floci-io/floci/release/1.5.5)
- Roughly **2–3 tagged releases per week** since February 2026

**Issue/PR throughput:**
The highest numbered closed item is PR #569 (merged 2026-04-23). With 33 open items [GitHub API], approximately 536 are closed, giving a **~94% close rate** on a system that merges PRs within minutes to hours (PR #569: created 06:55 UTC, merged 07:06 UTC — 11 minutes).

**Bus factor assessment:**
hectorvent holds **~29% of commits** and is the sole release author (all release PRs are authored and merged by hectorvent). The repository was moved from `hectorvent/floci` to the `floci-io` organization — [the GitHub API confirms both paths resolve to the same repo ID](https://api.github.com/repos/hectorvent/floci). The org structure provides a governance container that reduces single-person key-person risk slightly, but hectorvent remains the only person with merge rights to `main` for releases. With 60 contributors, multiple active non-core contributors (hampsterx submitted KMS and Cognito PIN-resource fixes in 1.5.7), and a public CONTRIBUTING.md + CODE_OF_CONDUCT.md, the project is architected for community scaling.

**Docker Hub:**
The `hectorvent/floci` Docker image has **50,000+ pulls** [Docker Hub](https://hub.docker.com/r/hectorvent/floci/tags). Critically: PR #569's description explicitly states "**Moved images to floci/floci**" — `floci/floci:latest` is now the canonical Docker image as of release 1.5.6. The older `hectorvent/floci` image should be considered deprecated. (This directly resolves Issue #7 from the prior peer review: `floci/floci:latest` IS the new canonical image; `hectorvent/floci` is the legacy image with historical pull counts.)

---

### MiniStack (ministackorg/ministack): Community Metrics

**Stars & Forks:**
[GitHub API](https://api.github.com/repos/ministackorg/ministack) confirms **2,186 stars** as of April 23, 2026. Forks count was truncated in API response but searchable at [GitHub](https://github.com/ministackorg/ministack).

**Contributors:**
36 unique contributors [Trendshift](https://trendshift.io/repositories/25726), top by commit count:
1. **Nahuel990** (Nahuel Nucera) — 139 commits (~54% of ~260 total)
2. **jayjanssen** — 29 commits (~11%)
3. **jgrumboe** — 14 commits (~5%)
4. **AdigaAkhil** — 10 commits (~4%)

**Commit frequency:**
~260 commits in ~30 days = ~8.7 commits/day — even higher than Floci per day, reflecting aggressive initial sprint.

**Release cadence:**
- v1.3.11 published [2026-04-23](https://github.com/ministackorg/ministack/releases/tag/v1.3.11)
- v1.3.12 PR in progress at time of writing
- Went from v1.0 → v1.3.11 in 30 days — roughly **1+ release per day**
- Releases authored exclusively by **Nahuel990**

**Issue/PR throughput:**
Latest item numbered #443 (v1.3.12 release PR, open). With 55 open items [GitHub Pulse / web search], approximately 388 are closed, giving a **~88% close rate**. Community PRs are being merged within hours (PR #437 by external contributor `david-hay` created 2026-04-24T00:27 and merged at 00:54 — 27 minutes, merged by Nahuel990).

**Bus factor assessment:**
Nahuel990 holds **~54% of commits** — the single largest concentration among the two projects — and is the exclusive release gatekeeper. The project was relocated from `nahuelnucera/ministack` to the `ministackorg` org, mirroring Floci's structural move, but the org appears to have only one active admin. At 30 days old, there is no track record of the project surviving a maintainer absence. jayjanssen (29 commits) is a meaningful second contributor, but the gap is large: 139 vs 29. The [CONTRIBUTING.md](https://github.com/ministackorg/ministack/blob/main/CONTRIBUTING.md) is present, indicating intent to invite contribution. **Bus factor risk is HIGH** for MiniStack given its age, concentration, and lack of secondary merge-rights holders.

**Notable conflict-of-interest signal:**
Nahuel990 is the author of the April 2026 dev.to benchmark article [comparing MiniStack, Floci, and LocalStack](https://dev.to/nahuel990/ministack-vs-floci-vs-localstack-honest-performance-benchmark-april-3rd-2026-479p) that appeared in prior findings. All self-favorable benchmark numbers should be treated as marketing claims until independently reproduced.

**Docker Hub:**
- `ministackorg/ministack`: **~9,500 pulls** [Docker Hub](https://hub.docker.com/r/ministackorg/ministack)
- `nahuelnucera/ministack` (legacy): **~10,000 pulls** [Docker Hub](https://hub.docker.com/r/nahuelnucera/ministack)
- Combined ~19,500 pulls vs Floci's 50,000+ — a **~2.6× adoption gap** in Docker pull volume, despite MiniStack being only 30 days old vs Floci's 65 days

---

## Evidence

| Data Point | Value | Source |
|-----------|-------|--------|
| Floci repo creation date | 2026-02-18 | [GitHub API](https://api.github.com/repos/floci-io/floci) |
| Floci GitHub stars | 4,140 | [GitHub API](https://api.github.com/repos/floci-io/floci) (verified 2026-04-23) |
| Floci forks | 280 | [GitHub API](https://api.github.com/repos/floci-io/floci) |
| Floci open issues + PRs | 33 | [GitHub API](https://api.github.com/repos/floci-io/floci) |
| Floci total contributors | ~60 | [Trendshift](https://trendshift.io/repositories/25152) |
| Floci top contributor commits (hectorvent) | 109 | [GitHub contributors API](https://api.github.com/repos/floci-io/floci/contributors) |
| Floci 2nd contributor commits (hampsterx) | 55 | [GitHub contributors API](https://api.github.com/repos/floci-io/floci/contributors) |
| Floci total commits | ~380 | [GitHub / web search corroboration](https://trendshift.io/repositories/25152) |
| Floci latest release | 1.5.7 (2026-04-23) | [GitHub releases API](https://api.github.com/repos/floci-io/floci/releases) |
| Floci PR merge time (PR #569) | 11 minutes | [GitHub API](https://api.github.com/repos/floci-io/floci/issues?state=closed&per_page=1) |
| Floci Docker Hub image migration | hectorvent/floci → floci/floci (as of 1.5.6) | [PR #569 body](https://github.com/floci-io/floci/pull/569) |
| Floci Docker Hub pull count (hectorvent/floci) | 50,000+ | [Docker Hub](https://hub.docker.com/r/hectorvent/floci/tags) |
| hectorvent/floci → floci-io/floci redirect confirmed | Same repo ID: 1160497244 | [GitHub API](https://api.github.com/repos/hectorvent/floci) |
| MiniStack repo creation date | 2026-03-24 | [GitHub API](https://api.github.com/repos/ministackorg/ministack) |
| MiniStack GitHub stars | 2,186 | [GitHub API](https://api.github.com/repos/ministackorg/ministack) (verified 2026-04-23) |
| MiniStack total contributors | ~36 | [Trendshift](https://trendshift.io/repositories/25726) |
| MiniStack top contributor commits (Nahuel990) | 139 | [GitHub contributors API](https://api.github.com/repos/ministackorg/ministack/contributors) |
| MiniStack 2nd contributor commits (jayjanssen) | 29 | [GitHub contributors API](https://api.github.com/repos/ministackorg/ministack/contributors) |
| MiniStack total commits | ~260 | [GitHub commits page](https://github.com/ministackorg/ministack/commits/main/) |
| MiniStack open issues + PRs | ~55 | [GitHub Pulse](https://github.com/ministackorg/ministack/pulse) |
| MiniStack latest release | v1.3.11 (2026-04-23) | [GitHub releases API](https://api.github.com/repos/ministackorg/ministack/releases) |
| MiniStack PR merge time (PR #437, external contributor) | 27 minutes | [GitHub API](https://api.github.com/repos/ministackorg/ministack/issues?state=closed&per_page=1) |
| MiniStack Docker Hub pulls (ministackorg image) | ~9,500 | [Docker Hub](https://hub.docker.com/r/ministackorg/ministack) |
| MiniStack Docker Hub pulls (nahuelnucera legacy image) | ~10,000 | [Docker Hub](https://hub.docker.com/r/nahuelnucera/ministack) |
| MiniStack benchmark authored by project creator | dev.to/nahuel990 is Nahuel Nucera (Nahuel990) | [Dev.to benchmark](https://dev.to/nahuel990/ministack-vs-floci-vs-localstack-honest-performance-benchmark-april-3rd-2026-479p) |

---

## Trade-offs

### Bus Factor: MiniStack vs Floci

| Dimension | Floci | MiniStack |
|-----------|-------|-----------|
| Primary author commit share | ~29% (hectorvent) | ~54% (Nahuel990) |
| Secondary contributor strength | hampsterx: 55 commits (14%), sustained feature work | jayjanssen: 29 commits (11%), significant but gap is wide |
| Multi-contributor releases | Yes — 1.5.7 had PRs from 12 different people | Emerging — v1.3.11 shows 2–3 external contributors per release |
| Merge rights distribution | hectorvent only (for releases to main) | Nahuel990 only |
| Org governance signal | floci-io org (transferred from personal) | ministackorg org (transferred from nahuelnucera) |
| Project age | 65 days | 30 days |
| Bus factor rating | **Medium** | **High** |

Floci's bus factor is concerning but not disqualifying. With 60 contributors and PRs from a dozen unique people in a single release, there is a genuine community forming around the codebase. MiniStack's 54% primary-author concentration on a 30-day-old project represents a meaningful risk for any team making a long-term infrastructure commitment.

### Adoption Velocity: MiniStack Is Surprisingly Fast

Despite being half Floci's age, MiniStack has accrued 2,186 stars and ~19,500 total Docker Hub pulls. Normalized to time: MiniStack is generating approximately **73 stars/day** vs Floci's **64 stars/day**. This may reflect MiniStack's Python-native installation (`pip install ministack`) lowering the barrier for the existing Moto/Python testing community, and the controversy following LocalStack's March 23 sunset driving additional discovery.

The star velocity data is counter-intuitive given Floci's higher absolute numbers and earlier launch. It suggests MiniStack may have better product-market fit with Python-centric teams, or that its timing (launched the day after LocalStack sunset) created a uniquely viral discovery moment.

### Release Cadence: Both Are Extremely Active — Potentially Risky

Both projects ship breaking-fix releases daily or faster. This is reassuring for bug responsiveness but creates pinning challenges for production pipelines:
- Floci: ~3 releases/week; using `floci/floci:latest` in CI means unpinned behavior
- MiniStack: ~1+ release/day; using `ministackorg/ministack:latest` is essentially a rolling release

Teams should **pin to specific version tags** (e.g., `floci/floci:1.5.7`) rather than `latest` for reproducible CI. Both projects publish tags alongside `latest`.

### Docker Image Migration (Peer Review Issue #7 — Resolved)

The prior peer review flagged that the report incorrectly stated `floci/floci:latest` as the canonical image. This is now **confirmed correct as of release 1.5.6**: [PR #569](https://github.com/floci-io/floci/pull/569) explicitly states "Moved images to floci/floci". The `hectorvent/floci` image is the legacy source of the 50,000+ historical pull count; new deployments should use `floci/floci:latest` or pinned tags. The `hectorvent/floci` repo redirects to `floci-io/floci` (identical repo ID 1160497244, confirmed via GitHub API).

### Maintainer Responsiveness: Exceptional for Both

Community PRs from external contributors are being merged within 11–27 minutes. Both maintainers appear to be monitoring their repositories in real time. For infrastructure tools where a broken CI pipeline is an urgent production blocker, this responsiveness level is a strong positive. The risk is sustainability: this pace is characteristic of a launch sprint and may not persist after the initial excitement wave from LocalStack's sunset.

---

## Confidence

| Conclusion | Confidence | Rationale |
|-----------|-----------|-----------|
| Floci stars: 4,140; MiniStack stars: 2,186 | **High** | Direct GitHub API response (verified 2026-04-23) |
| Floci contributors: ~60; MiniStack contributors: ~36 | **Medium** | Trendshift aggregation; not independently counted per-commit; within ±5 of actual |
| hectorvent holds ~29% of Floci commits | **High** | Direct GitHub contributors API: 109/~380 commits |
| Nahuel990 holds ~54% of MiniStack commits | **High** | Direct GitHub contributors API: 139/~260 commits |
| floci/floci is now the canonical Docker image | **High** | PR #569 body explicitly states "Moved images to floci/floci"; GitHub API confirms hectorvent/floci → floci-io/floci redirect |
| hectorvent/floci Docker Hub: 50K+ pulls | **Medium** | Docker Hub search result [confirmed via search](https://hub.docker.com/r/hectorvent/floci/tags); actual number may be higher |
| ministackorg/ministack Docker Hub: ~9,500 pulls | **Medium** | Docker Hub search result; may be undercounted if many users still pull nahuelnucera image |
| MiniStack bus factor is High; Floci is Medium | **Medium** | Commit concentration ratios are direct facts; qualitative "bus factor" rating involves judgment about org structure, succession planning, and community momentum |
| Both projects will remain active long-term | **Unresolved** | Both are 30–65 days old. There is no track record through a low-activity trough. The high daily velocity may reflect LocalStack-exodus energy that normalizes downward. |

---

## New Questions

1. **Successor image adoption for Floci**: The Docker Hub `hectorvent/floci` image has 50,000+ pulls but was deprecated in favor of `floci/floci` as of v1.5.6. What is the current pull count for `floci/floci` on Docker Hub? Do existing Testcontainers and Compose setups in the wild still reference the old image? An audit of GitHub public repos referencing `hectorvent/floci` vs `floci/floci` would quantify migration lag.

2. **MiniStack's Nahuel990 succession plan**: At 54% commit concentration and 30 days of history, what is MiniStack's governance model if the primary author becomes unavailable? Does the `ministackorg` GitHub organization have co-owners with merge rights, or is it a one-person org with an org shell? Inspecting the org member list and CODEOWNERS file would answer this directly.

3. **Adoption in Testcontainers and IaC modules**: Both projects are too new for Terraform Registry or official Testcontainers support. What is the current status of community-published Testcontainers modules for Floci and MiniStack, and are there `docker-compose` examples in popular IaC repositories (Terraform, CDK, Pulumi) that pin to either tool? This is the real indicator of ecosystem entrenchment, separate from raw GitHub stars.

---

## Peer Review (codex-cli)

I verified the most checkable claims against accessible sources before reviewing. The biggest problems are not just a few numbers—they are **methodology drift, repo-identity confusion, and overconfident governance/adoption claims**.

### Issue 1: “LocalStack sunset” overstates what happened
- **Type**: missing nuance
- **Location**: “Neither Floci nor MiniStack existed before LocalStack's March 2026 sunset.”
- **Problem**: LocalStack’s own March 2026 announcement says it moved to a **single unified image requiring an auth token**, not that the product was “sunset.” It also says a **Free plan remains**. “Sunset” implies discontinuation, which is materially stronger than the official framing.  
  Sources: [LocalStack announcement](https://blog.localstack.cloud/localstack-single-image-next-steps/), [2026.03.0 release](https://blog.localstack.cloud/localstack-for-aws-release-2026-03-0/), [auth token docs](https://docs.localstack.cloud/aws/getting-started/auth-token/)
- **Impact**: It biases the entire report by framing the market event more dramatically than the primary source supports.

### Issue 2: Floci trending claim conflicts with the cited source
- **Type**: factual error
- **Location**: “Trendshift places it in the top-trending repositories for Q1 2026.”
- **Problem**: The accessible Trendshift page for `floci-io/floci` says **“No trending activity”**, not “top-trending.”  
  Source: [Trendshift: floci-io/floci](https://trendshift.io/repositories/25152)
- **Impact**: Undermines trust in the report’s use of Trendshift and inflates perceived momentum.

### Issue 3: Floci stars/forks/contributor counts do not match accessible evidence
- **Type**: factual error
- **Location**: “4,140 stars and 280 forks… 60 unique contributors”
- **Problem**: The accessible Trendshift page shows roughly **3.2k stars, 176 forks, 57 contributors**. Maybe GitHub API had fresher numbers, but the report then should explain the discrepancy instead of presenting all figures as harmonized facts.  
  Source: [Trendshift: floci-io/floci](https://trendshift.io/repositories/25152)
- **Impact**: Makes the metrics section look less like a validated synthesis and more like mixed snapshots from incompatible timestamps.

### Issue 4: Floci Docker-image conclusion is contradicted by Floci’s own website
- **Type**: contradiction
- **Location**: “`floci/floci:latest` is now the canonical Docker image… `hectorvent/floci` is the legacy image”
- **Problem**: Floci’s own public site still shows `docker run ... hectorvent/floci:latest` in its quick-start examples, and Docker Hub shows `hectorvent/floci` actively updated with `latest`. That does **not** support a clean “canonical image has moved” conclusion. At minimum, the migration appears incomplete or inconsistently documented.  
  Sources: [floci.io](https://floci.io/), [Docker Hub: hectorvent/floci tags](https://hub.docker.com/r/hectorvent/floci/tags)
- **Impact**: This is one of the report’s “resolved” peer-review issues, but the accessible evidence does not actually resolve it cleanly.

### Issue 5: Close-rate methodology is invalid
- **Type**: unsupported claim
- **Location**: “The highest numbered closed item is PR #569… With 33 open items… approximately 536 are closed, giving a ~94% close rate”
- **Problem**: You cannot derive a repository “close rate” from **highest visible item number minus current open count**. GitHub numbering mixes issues and PRs, includes still-open historical items, and does not imply contiguous closed objects. This is not a valid metric construction.
- **Impact**: One of the core operational metrics is mathematically unsound.

### Issue 6: Merge-speed conclusion is overgeneralized from cherry-picked examples
- **Type**: unsupported claim
- **Location**: “a system that merges PRs within minutes to hours” / “Community PRs… are being merged within 11–27 minutes”
- **Problem**: The report uses one PR for Floci and one PR for MiniStack as if they represent normal throughput. That is anecdotal, not throughput analysis. You would need median/percentile PR lead times over a meaningful sample.
- **Impact**: Overstates maintainer responsiveness and masks whether these were exceptional cases.

### Issue 7: MiniStack timing is internally inconsistent
- **Type**: contradiction
- **Location**: “as of April 23, 2026” and later “PR #437 by external contributor `david-hay` created 2026-04-24T00:27 and merged at 00:54”
- **Problem**: That PR timestamp is **April 24, 2026**, which is after the report’s stated “as of April 23, 2026” cutoff.
- **Impact**: This is a hard chronology error. It suggests the report mixes snapshots from different moments without controlling the as-of date.

### Issue 8: MiniStack repo identity is muddled
- **Type**: missing nuance
- **Location**: “The project was relocated from `nahuelnucera/ministack` to the `ministackorg` org”
- **Problem**: Public traces still point in multiple directions: PyPI shows source provenance from **`Nahuel990/ministack`**, Docker Hub legacy pages still link to a personal GitHub repo, and Trendshift search surfaces **`Nahuel990/ministack`** rather than `ministackorg/ministack`. That does not prove the report is wrong, but it does show the migration/repo lineage is not cleanly established in the report.  
  Sources: [PyPI ministack](https://pypi.org/project/ministack/), [Trendshift: Nahuel990/ministack](https://trendshift.io/repositories/24395), [Docker Hub: nahuelnucera/ministack](https://hub.docker.com/r/nahuelnucera/ministack)
- **Impact**: Weakens all MiniStack metrics, because it is unclear whether the report mixes data from multiple repo identities.

### Issue 9: MiniStack community metrics likely mix incompatible sources/snapshots
- **Type**: unsupported claim
- **Location**: “2,186 stars… 36 unique contributors”
- **Problem**: Accessible public evidence for the personal-repo lineage shows much smaller numbers (Trendshift surfaced ~1.2k stars, 50 forks, 9 contributors for `Nahuel990/ministack`). Even if `ministackorg/ministack` is the new repo, the report needs to explain whether counts were taken from the org repo only, the personal repo only, or both. Right now it reads as if the identity problem does not exist.
- **Impact**: Makes the MiniStack comparison materially less reliable.

### Issue 10: Governance and permissions claims are asserted without evidence
- **Type**: unsupported claim
- **Location**: “hectorvent remains the only person with merge rights to `main` for releases” / “the org appears to have only one active admin”
- **Problem**: Public GitHub pages do **not** expose org admin rights or full branch permission state in a way that supports these claims from the cited evidence. You can infer release authorship; you cannot confidently assert merge-right distribution or admin count from the material shown here.
- **Impact**: Bus-factor conclusions are overstated because they rest partly on private governance assumptions.

### Issue 11: Docker-pull comparison is too confident for approximate bucketed values
- **Type**: missing nuance
- **Location**: “Combined ~19,500 pulls vs Floci's 50,000+ — a ~2.6× adoption gap”
- **Problem**: Docker Hub public counts are bucketed/rounded (`10K+`, `50K+`, etc.), and the accessible views are themselves inconsistent across pages. Treating them as precise enough for a `~2.6×` ratio is false precision.  
  Sources: [Docker Hub: hectorvent/floci](https://hub.docker.com/r/hectorvent/floci/tags), [Docker Hub: ministackorg/ministack](https://hub.docker.com/r/ministackorg/ministack/tags), [Docker Hub: nahuelnucera/ministack](https://hub.docker.com/r/nahuelnucera/ministack)
- **Impact**: The adoption comparison sounds quantitative but is not robust enough to support ratio-style conclusions.

### Issue 12: Causal explanation for MiniStack’s star velocity is speculative
- **Type**: unsupported claim
- **Location**: “This may reflect MiniStack's Python-native installation (`pip install ministack`) lowering the barrier… or… a uniquely viral discovery moment”
- **Problem**: Those are plausible hypotheses, but the report presents them with no supporting evidence such as referral traffic, download stats, user survey data, or commit/test ecosystem analysis.
- **Impact**: Reduces analytical rigor by drifting from measured facts into narrative inference.

### Issue 13: “Architected for community scaling” is too strong for an early project
- **Type**: missing nuance
- **Location**: “the project is architected for community scaling”
- **Problem**: A CONTRIBUTING guide and a CODE_OF_CONDUCT are positive signals, but they do not establish scalable governance, review redundancy, maintainer onboarding, or release delegation. For a ~2 month old project, that conclusion is premature.
- **Impact**: Softens real key-person risk with evidence that is largely symbolic.

### Issue 14: Important evaluation dimensions are missing
- **Type**: gap
- **Location**: overall report
- **Problem**: The report is heavy on community velocity and light on **product reliability**: no sustained compatibility-failure analysis, no issue-severity taxonomy, no regression history, no release rollback evidence, no ecosystem integration validation beyond stars/pulls, and no independent benchmark replication.
- **Impact**: The findings are weaker for actual tool-selection decisions, because infrastructure adoption depends more on reliability and compatibility than on launch-week enthusiasm.

## Summary
- **Issues found**: 14
- **Overall reliability**: **medium-low**

### What would most improve the findings
1. Use a strict **single as-of timestamp** and reconcile every metric to it.
2. Separate **facts** from **inferences**.
3. Fix the **repo lineage problem** for MiniStack and the **Docker-image ambiguity** for Floci.
4. Replace derived heuristics like “close rate” and “merge within minutes” with proper sampled metrics.
5. Add reliability evidence: failing issues, compatibility regressions, test depth, release breakage, and ecosystem integrations.

Sources used: [LocalStack announcement](https://blog.localstack.cloud/localstack-single-image-next-steps/), [LocalStack 2026.03.0 release](https://blog.localstack.cloud/localstack-for-aws-release-2026-03-0/), [LocalStack auth docs](https://docs.localstack.cloud/aws/getting-started/auth-token/), [Floci site](https://floci.io/), [MiniStack site](https://ministack.org/), [Trendshift floci](https://trendshift.io/repositories/25152), [Trendshift Nahuel990/ministack](https://trendshift.io/repositories/24395), [Docker Hub hectorvent/floci](https://hub.docker.com/r/hectorvent/floci/tags), [Docker Hub ministackorg/ministack](https://hub.docker.com/r/ministackorg/ministack/tags), [Docker Hub nahuelnucera/ministack](https://hub.docker.com/r/nahuelnucera/ministack), [PyPI ministack](https://pypi.org/project/ministack/), [NewReleases floci 1.5.7](https://newreleases.io/project/github/floci-io/floci/release/1.5.7), [NewReleases ministack v1.3.11](https://newreleases.io/project/github/ministackorg/ministack/release/v1.3.11).
