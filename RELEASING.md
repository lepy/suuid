# Releasing `suuid` to PyPI

Releases are published automatically via **PyPI Trusted Publishing** (OIDC) when a
GitHub Release is published — no API tokens are stored anywhere.

## One-time PyPI setup (do this once, before the first release)

The project doesn't exist on PyPI yet, so register a **pending publisher**:

1. Go to <https://pypi.org/manage/account/publishing/>.
2. Under *"Add a new pending publisher"* fill in:
   - **PyPI Project Name:** `suuid`
   - **Owner:** `lepy`
   - **Repository name:** `suuid`
   - **Workflow name:** `release.yml`
   - **Environment name:** `pypi`
3. Save. PyPI now trusts this repo's `release.yml` to publish `suuid`.

Optional but recommended — add a matching GitHub environment named `pypi`
(*Settings → Environments → New environment*) and protect it with a required
reviewer, so a publish needs an explicit approval click.

## Cutting a release

1. Bump the version in **both** places (they must match):
   - `pyproject.toml` → `[project] version`
   - `src/suuid/__init__.py` → `__version__`
2. Commit: `git commit -am "release: vX.Y.Z"` and push to `main`.
3. Tag and create the GitHub Release:
   ```bash
   gh release create vX.Y.Z --title vX.Y.Z --generate-notes
   ```
4. The **Release** workflow builds, runs `twine check`, and publishes to PyPI.
   Watch it: `gh run watch`.

## Rehearsing on TestPyPI (manual trigger)

The **Release (TestPyPI)** workflow (`release-testpypi.yml`) publishes to TestPyPI
via Trusted Publishing on demand — run it from the *Actions* tab ("Run workflow")
or `gh workflow run release-testpypi.yml`.

One-time pending-publisher setup on TestPyPI (separate from PyPI):

1. <https://test.pypi.org/manage/account/publishing/> → *Add a pending publisher*:
   - **Project Name:** `suuid` · **Owner:** `lepy` · **Repository:** `suuid`
   - **Workflow:** `release-testpypi.yml` · **Environment:** `testpypi`
2. The `testpypi` GitHub environment already exists (required reviewer: `lepy`).

Install from TestPyPI to verify:

```bash
uv run --isolated --no-project --index https://test.pypi.org/simple/ \
  --with suuid python -c "import suuid; print(suuid.__version__)"
```

> TestPyPI versions are also immutable. Either bump the version for each rehearsal
> or delete the test release on TestPyPI before re-running.

## Manual publish (fallback, without CI)

```bash
uv build
uvx twine check dist/*
# Token from https://pypi.org/manage/account/token/
UV_PUBLISH_TOKEN=pypi-... uv publish
```

Use [TestPyPI](https://test.pypi.org/) first to rehearse:

```bash
uv publish --publish-url https://test.pypi.org/legacy/
```

> PyPI versions are immutable — a given `X.Y.Z` can be uploaded only once and
> cannot be re-uploaded after a fix. Bump the version instead.
