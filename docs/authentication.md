# Authentication and publication flow

This repository hosts a public static archive. Site visitors do not sign in, and the repository contains no application login endpoint, session store, password database, or user refresh-token implementation. Authentication is used by the publishing infrastructure, not by readers.

## Components and credentials

| Component | Authentication | What it can do |
| --- | --- | --- |
| Public HTML/CSS and research filtering JavaScript | None | Read published archive pages; filter the already delivered article index in the browser |
| Notion publisher | `NOTION_API_KEY`, injected from GitHub Actions Secrets | Read the configured data source and page Markdown, subject to that credential's Notion permissions |
| Checkout and Git push | Job-scoped `GITHUB_TOKEN`, supplied by GitHub Actions and used by `actions/checkout@v4` | Read the repository and push generated changes with `contents: write` |
| GitHub Pages deployment | Job token plus GitHub OIDC identity | Upload/deploy the artifact using `pages: write`, `id-token: write`, and the `github-pages` environment |
| Connected assistant integrations | Their own user-authorized connections | Work with GitHub, Notion, or Gmail outside this repository; their credentials are not implemented or stored in this source tree |

Source: [publisher workflow](../.github/workflows/content-engine.yml), [deployment workflow](../.github/workflows/pages.yml), [publisher script](../scripts/sync_notion_to_github.py).

## Request flow

1. The publisher workflow is scheduled at UTC minutes 7, 22, 37, and 52 of every hour; it can also be started with `workflow_dispatch`. Scheduling is requested, not a guarantee that a run starts every 15 minutes.
2. The runner checks out the repository and receives `NOTION_API_KEY` through its environment. `NOTION_DATA_SOURCE_ID` and `SITE_URL` are configuration identifiers, not credentials.
3. The Python script constructs these headers once and uses them for its Notion API requests:

```python
TOKEN = os.environ["NOTION_API_KEY"]
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2026-03-11",
    "Content-Type": "application/json",
}
```

4. `query_all_pages()` posts to `/v1/data_sources/{id}/query`, following pagination. Only rows explicitly marked `Ready` or `Published` enter the public set. Draft, blank, and unrecognized statuses are skipped before downloading their bodies.
5. For new or edited public pages, `page_markdown()` gets `/v1/pages/{id}/markdown`. The script renders HTML and updates the public state file, research index, home-page selection, README statistics, and sitemap.
6. Cleanup removes generated dated article directories no longer present in the public state. Removing public URLs does not erase previously committed Git history; private material must never enter this repository.
7. The workflow stages generated files, commits only when the working tree differs, and pushes to `main`. Checkout's default credential persistence makes the job token available to the subsequent Git command. It cleans up its credentials after the job.
8. When the publisher commits a change, it deploys Pages in that same workflow. A push made with the job's `GITHUB_TOKEN` normally does not start another push-triggered workflow; deployment is therefore explicit here. The separate `pages.yml` handles other qualifying pushes to `main` and manual dispatches.
9. Readers receive static files from GitHub Pages. No Notion bearer token is sent to their browsers.

## Token lifecycle and failure handling

- The publisher does not implement a Notion OAuth callback, token issuance, refresh, or rotation. A repository administrator must maintain the injected secret and grant it access to the intended research data source. The source does not reveal whether that bearer credential is an internal integration token, PAT, or OAuth token.
- `NOTION_API_KEY` is required at process startup; an absent variable fails before publication. API errors raise an exception, so a failed Notion request stops the subsequent commit/deploy steps. Error messages currently include up to 1,000 characters of the API response; do not put confidential payloads in public workflow logs.
- `GITHUB_TOKEN` is issued per job, limited to this repository and declared workflow permissions, and expires when the job finishes or reaches its maximum lifetime. It is not a personal password.
- `id-token: write` permits requesting an OIDC identity token for deployment; it is distinct from the Notion bearer token and from a reader session.
- Source inspection verifies how credentials are referenced, not their live values, actual Notion sharing scope, repository/environment secret placement, rotation date, or Pages environment protections. Those settings require an authorized settings review.

## Public/private publishing boundary

The automatic publisher reads only the configured research data source. The active private knowledge ledger, editorial correspondence, opportunity CRM, unpublished submission manuscripts, signatures, and contact records are not automatic export sources. New material from those workspaces requires a deliberately prepared public version before inclusion in the public research data source or a reviewed public commit.

`research/_notion_state.json` is public metadata (page identifiers, titles, timestamps, and URLs), not a secret store. `Ready`/`Published` are editorial publication gates, not a substitute for Notion API authorization.

## Verification

Run the credential-free regression check with:

```sh
python -m unittest discover -s tests -v
```

It executes the real publisher and cleanup against stubbed API responses. It checks both allowed statuses, Draft, blank, missing and unknown statuses, prevents private body downloads, and confirms that a formerly public Draft is removed from generated output.

Operational evidence on 20 October 2026: [publisher run 39349442979](https://github.com/sqliukunsq-cmyk/liu-beihe-archive/actions/runs/39349442979) successfully read 61 Notion rows, retained 53 public entries, rendered 0 changed pages, and reported no changes to commit. This is a point-in-time audit, not a claim of a newly published research batch.

## Primary documentation

- [Notion API authentication](https://developers.notion.com/reference/authentication)
- [GitHub job-token lifecycle and event behavior](https://docs.github.com/en/actions/concepts/security/github_token)
- [Checkout v4 token handling](https://github.com/actions/checkout/blob/v4/README.md)
- [Custom GitHub Pages workflows and deployment permissions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
