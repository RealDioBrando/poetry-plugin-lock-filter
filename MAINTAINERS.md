# Maintainer notes

## Publishing

Releases are published automatically by GitHub Actions when a GitHub release is published.

The workflow uses PyPI trusted publishing and does not store a PyPI token in GitHub.

The trusted-publisher configuration is:

```text
Owner: RealDioBrando
Repository: poetry-plugin-lock-filter
Workflow: publish.yml
Environment: pypi
```

## Release checklist

1. Bump the version in:
   - `pyproject.toml`
   - `src/poetry_plugin_lock_filter/__init__.py`
2. Run the tests:
   ```bash
   python -m unittest discover -s tests -v
   ```
3. Commit and push the version bump.
4. Create the GitHub release:
   ```bash
   gh release create vX.Y.Z \
     --title "poetry-plugin-lock-filter X.Y.Z" \
     --notes "Release notes here"
   ```
5. Confirm the `Publish to PyPI` workflow succeeds.
