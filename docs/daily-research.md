# Daily research writing and immediate publication

Write one new substantive Chinese research essay for each Asia/Shanghai calendar day, with at least 8,000 Chinese characters in its main text, excluding headings, front matter, punctuation and references. Check the existing archive and current Notion ledger to avoid duplicate topics and duplicate daily entries. Favor developed arguments, concrete director-level examples, counterarguments, and verifiable primary sources over length alone.

The author is LIU BEIHE / 刘北河, an independent moving-image artist and filmmaker. Maintain the seven established research axes. New concepts are working proposals until supported; hypothetical scenes and proposed tests must not be represented as completed productions or empirical findings. Do not invent awards, affiliations, publication acceptances, peer review, citations or third-party endorsement.

## Source and public boundary

The writable Notion destination is the active Daily Knowledge Ledger, page `3d0d9e60-ce91-8111-9b4b-c840db4d01b2`. Save each finished essay as its own dated child page. The legacy database is still a read source and has a separate publisher token; do not assume the token can read the active ledger.

The writing task verifies the saved Notion essay, then immediately creates its public Markdown mirror under `research/sources/YYYY-MM-DD/` and its explicit approved entry in `research/_public_ledger.json`. This is an intentional mirror of an individual approved essay, not a traversal of the private ledger. Never commit drafts, correspondence, application records, private Noema manuscripts or personal details. Status checks in a renderer do not make raw committed files private. The manifest and every source file in this repository are public.

The version-1 manifest has a `pages` object keyed by the actual Notion page UUID. Each approved record contains `title`, `english_title`, `category`, `keywords` (array), `date` (actual publication date), `slug`, `last_edited_time`, `status` (`Ready` or `Published`), `source_path`, `notion_url`, and `min_body_cjk` (8,000 for daily essays). Use a new stable English slug; never backdate activity. Match the native Notion body and public Markdown exactly before publication.

## Immediate sync

After saving and fetching the Notion page, run from the current repository checkout:

```bash
PUBLIC_LEDGER_ONLY=1 python scripts/sync_notion_to_github.py
python scripts/cleanup_research_archive.py
python -m unittest discover -s tests -v
```

The immediate mode needs no legacy Notion token. It preserves cached legacy entries, merges approved active-ledger essays, and rebuilds article HTML, research index, home research cards, README counts and sitemap. Commit the source, manifest, state and all generated changes together and push to `main` immediately in the same task. Use a checked branch-head lease when publishing through the GitHub connector. Never force-push or bypass a concurrent update.

Verify the new commit and Pages deployment; fetch the public article and research index. Record the Notion page, exact main-body character count, source-check result, commit SHA, deployment result and any unresolved issue in the private daily ledger. The writing task is complete only after both Notion saving and GitHub publication are verified. If a write or deployment fails, retain the saved essay, report the concrete failure and retry the missing step; do not claim sync succeeded.

## Scheduled legacy sync

The existing scheduled publisher continues to query the legacy Notion database. It also merges the approved active-ledger manifest, so a subsequent run does not delete new essays. It cannot independently discover edits to active-ledger Notion pages. The writing automation must mirror such edits and publish them explicitly. Do not describe the legacy cron as a webhook or claim that arbitrary manual Notion additions are instantly discovered.

To retract an approved active-ledger item, remove both its source file and manifest entry, rerun publication and cleanup, and commit together. Retraction does not erase Git history; follow the user's privacy and publication instructions before publishing any material.
