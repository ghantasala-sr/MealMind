# Fork Sync FAQ

## Why can't I sync my fork?

If you're having trouble syncing your fork of MealMind, here are common reasons and solutions:

### ✅ This Repository Should Allow Fork Syncing

Good news! This repository is designed to be fork-friendly:
- ✅ No GitHub Actions workflows that block syncing
- ✅ Standard repository structure
- ✅ Clear default branch (main)

### Common Issues and Solutions

#### Issue 1: "Sync fork" button is disabled or greyed out

**Possible Causes:**
- Your fork is already up-to-date
- You have uncommitted changes
- There are merge conflicts

**Solutions:**
1. Check if your fork is already up-to-date with upstream
2. Commit or stash any local changes
3. If there are conflicts, resolve them manually (see below)

#### Issue 2: Merge conflicts when syncing

**Solution:**
Use the command line to resolve conflicts:

```bash
# Add upstream remote (first time only)
git remote add upstream https://github.com/ghantasala-sr/MealMind.git

# Fetch upstream changes
git fetch upstream

# Checkout your main branch
git checkout main

# Merge upstream changes
git merge upstream/main

# Resolve conflicts in your editor, then:
git add .
git commit -m "Resolved merge conflicts"
git push origin main
```

#### Issue 3: Can't find the "Sync fork" button

**Solution:**
The "Sync fork" button appears on your fork's main page on GitHub, just above the file list. If you don't see it:
1. Make sure you're on your fork (not the original repo)
2. Make sure you're viewing the main branch
3. Refresh the page

#### Issue 4: Want to sync via command line

**Solution:**
```bash
# Fetch and merge upstream changes
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

Or use GitHub CLI:
```bash
gh repo sync YOUR-USERNAME/MealMind -b main
```

### Alternative Syncing Methods

#### Method 1: GitHub Web UI
1. Go to your fork on GitHub
2. Click "Sync fork" button
3. Click "Update branch"

#### Method 2: Git Command Line
```bash
# One-time setup
git remote add upstream https://github.com/ghantasala-sr/MealMind.git

# Regular sync
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

#### Method 3: GitHub CLI
```bash
gh repo sync YOUR-USERNAME/MealMind -b main
```

#### Method 4: Pull Request to Your Fork
1. Go to your fork on GitHub
2. Click "New pull request"
3. Click "compare across forks"
4. Set base to your fork, head to upstream
5. Create and merge the PR

### Still Having Issues?

If none of these solutions work:

1. **Check GitHub Status**: Visit [githubstatus.com](https://www.githubstatus.com/) to ensure GitHub services are operational

2. **Check Repository Settings**: Ensure your fork hasn't restricted syncing in settings

3. **Create an Issue**: Open an issue in the upstream repository describing your problem

4. **Fork Again**: As a last resort, you can:
   - Save your changes in a branch
   - Delete your fork
   - Create a fresh fork
   - Apply your changes to the new fork

## Best Practices

### Regular Syncing
Sync your fork regularly to:
- Avoid large merge conflicts
- Stay up-to-date with bug fixes
- Get new features quickly

### Before Making Changes
Always sync before starting new work:
```bash
git fetch upstream
git merge upstream/main
```

### Branch Strategy
- Keep your `main` branch clean (synced with upstream)
- Create feature branches for your changes
- Submit PRs from feature branches

## Additional Resources

- [GitHub Documentation: Syncing a Fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/syncing-a-fork)
- [CONTRIBUTING.md](CONTRIBUTING.md) - Full contribution guidelines
- [GitHub CLI Documentation](https://cli.github.com/manual/)

---

**Need more help?** Open an issue in the repository with:
- Your operating system
- Git version (`git --version`)
- Steps you've tried
- Error messages you're seeing
