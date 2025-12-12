# GitHub Configuration

This directory contains GitHub-specific configuration files for the MealMind repository.

## Fork Synchronization

This repository is designed to be fork-friendly. The absence of GitHub Actions workflows in this directory ensures that:

1. **Fork sync is enabled**: Users can easily sync their forks using GitHub's "Sync fork" button
2. **No security concerns**: There are no workflows that could execute potentially malicious code when syncing
3. **Smooth collaboration**: Contributors can keep their forks up-to-date without manual intervention

## Why No Workflows?

We intentionally keep this repository free of GitHub Actions workflows to:
- Make forking and syncing as simple as possible
- Avoid the security implications of automated workflows in forks
- Keep the repository focused on the application code itself

## Future Additions

If GitHub Actions workflows are needed in the future, they will be:
- Carefully reviewed for security
- Documented in CONTRIBUTING.md
- Designed to work safely with forks

For contribution guidelines and sync instructions, see [CONTRIBUTING.md](../CONTRIBUTING.md).
