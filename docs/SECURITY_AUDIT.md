# Security Audit

Date: 2026-05-29

## Scope

This audit covered the current working tree, tracked files, local sensitive filenames, and Git history references visible from all local branches and remotes.

## Tools / Commands Used

```powershell
git ls-files
git log --all --name-only --pretty=format:
git log --all --oneline -- <sensitive paths>
git log --all --oneline -S'_RAPIDAPI_KEY' -- modulo1_download.py
Select-String based scans for secret-like filenames and token/key patterns
```

Dedicated tools such as `gitleaks`, `trufflehog`, and `detect-secrets` were not available in this environment.

## Current Working Tree Findings

| Finding | Status | Notes |
| --- | --- | --- |
| Hardcoded RapidAPI key in `modulo1_download.py` | Fixed | Replaced with `RAPIDAPI_KEY` from environment. The fallback now remains disabled when the variable is empty. |
| `.env` present locally | Not tracked | `.env` is ignored and was not committed. Values were not copied into documentation. |
| OAuth credential/token file patterns | Ignored | `.gitignore` now covers OAuth client files, generated tokens, credential folders, service accounts, private keys, and common key stores. |
| Runtime database and generated media | Ignored | `data/`, `downloads/`, logs, and generated media outputs are ignored. |
| Diagnostic output with local OAuth paths | Fixed | `test_autopublish.py` now redacts credential paths in its report. |

## Git History Findings

The current branch no longer tracks the sensitive OAuth files, but Git history contains references to previously committed sensitive paths, including:

- `.env`
- Google OAuth client files named `client_secret_*.json`
- Google OAuth token files named `*_token.json`
- Google OAuth pickle token files named `*_token.pickle`

History also contains a prior revision of `modulo1_download.py` where a RapidAPI key was hardcoded.

No secret values are reproduced in this report.

## Required Manual Action

Treat the exposed credentials as compromised:

1. Revoke and regenerate the RapidAPI key that was previously committed.
2. Revoke affected Google OAuth tokens from the Google account security page.
3. Rotate or recreate the affected Google OAuth client secrets in Google Cloud Console.
4. Remove generated token files from all developer machines.
5. Coordinate Git history cleanup before making the repository public or relying on it as sanitized.

## History Cleanup Strategy

Use a dedicated coordination window because rewriting history changes commit SHAs for every collaborator.

Recommended approach with `git-filter-repo`:

```powershell
python -m pip install git-filter-repo

git filter-repo --force `
  --path .env --invert-paths `
  --path-glob "client_secret_*.json" --invert-paths `
  --path-glob "*_token.json" --invert-paths `
  --path-glob "*_token.pickle" --invert-paths
```

Then remove any historical RapidAPI value from affected blobs using a replacement file:

```powershell
# replacements.txt must contain the exact compromised value locally.
git filter-repo --force --replace-text replacements.txt
```

After validation, force-push only with explicit team agreement:

```powershell
git push --force-with-lease --all origin
git push --force-with-lease --tags origin
```

Every collaborator should then reclone or carefully rebase onto the cleaned history.

## Ongoing Recommendations

- Add `gitleaks` or `detect-secrets` to CI.
- Add a pre-commit hook for secret scanning.
- Keep `.env.example` complete but value-free.
- Prefer environment variables or local secret managers for all provider credentials.
- Redact sensitive paths and token content from logs before production use.
