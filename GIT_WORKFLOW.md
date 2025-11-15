# Git Workflow for QuizMarker

## Branch Strategy

```
main (production)
  ↑
staging (pre-production testing)
  ↑
development (active development)
  ↑
feature/* (individual features)
```

## Branches

### `main` - Production Branch
- **Protected**: Requires PR review
- **Auto-deploy**: To production (after Phase 6)
- **Only accepts**: Merges from `staging`
- **Never commit directly** to this branch

### `staging` - Pre-production Branch
- **For**: Final testing before production
- **Accepts**: Merges from `development`
- **Deploy**: To staging environment
- **Test here**: Before merging to main

### `development` - Active Development
- **Default branch** for development work
- **Accepts**: Merges from feature branches
- **Most active**: Day-to-day commits happen here
- **Can deploy**: To development environment

### `feature/*` - Feature Branches
- **Pattern**: `feature/description-of-feature`
- **Examples**:
  - `feature/jwt-authentication`
  - `feature/s3-file-upload`
  - `feature/next-js-frontend`
- **Merge into**: `development` via PR
- **Delete**: After merge

## Workflow

### 1. Starting New Work

```bash
# Make sure you're on development and up to date
git checkout development
git pull origin development

# Create a new feature branch
git checkout -b feature/your-feature-name
```

### 2. Making Changes

```bash
# Make your changes, then stage them
git add .

# Or stage specific files
git add app.py models.py

# Commit with clear message
git commit -m "Add JWT authentication to API endpoints"

# Push to remote
git push origin feature/your-feature-name
```

### 3. Merging to Development

```bash
# Option A: Merge directly (for solo development)
git checkout development
git merge feature/your-feature-name
git push origin development

# Option B: Create Pull Request (recommended)
# Push feature branch and create PR on GitHub
git push origin feature/your-feature-name
# Then create PR on GitHub: feature/your-feature-name → development
```

### 4. Merging to Staging (Before Production)

```bash
# Only when ready for testing
git checkout staging
git merge development
git push origin staging

# Test thoroughly on staging environment
# If bugs found, fix on development and merge again
```

### 5. Deploying to Production

```bash
# Only when staging is fully tested
git checkout main
git merge staging
git push origin main

# This triggers production deployment
```

## Commit Message Guidelines

### Format
```
<type>: <subject>

<body (optional)>

<footer (optional)>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

Good commit messages:
```
feat: Add JWT authentication to API endpoints
fix: Resolve file upload timeout for large files
docs: Update MIGRATION_PLAN.md with Phase 2 details
refactor: Extract S3 upload logic to separate service
chore: Update dependencies to latest versions
```

Bad commit messages:
```
update stuff
fix
changes
wip
.
```

## Working with .env Files

### Setup

```bash
# Copy example file
cp .env.example .env

# Edit .env with your actual values
# NEVER commit .env to git!
```

### Different Environments

```bash
# Development
.env

# Staging
.env.staging

# Production
# Set environment variables directly in Railway/Render dashboard
```

## Handling Conflicts

```bash
# If you get merge conflicts
git checkout development
git pull origin development

# Checkout your feature branch
git checkout feature/your-feature

# Rebase on development
git rebase development

# Resolve conflicts in your editor
# After resolving:
git add .
git rebase --continue

# Push (may need force push after rebase)
git push origin feature/your-feature --force
```

## Useful Commands

### Check Status
```bash
git status                    # See what's changed
git log --oneline -10        # Last 10 commits
git diff                     # See unstaged changes
git diff --staged            # See staged changes
```

### Undo Changes
```bash
git checkout -- file.py      # Discard changes to file
git reset HEAD file.py       # Unstage file
git reset --soft HEAD~1      # Undo last commit (keep changes)
git reset --hard HEAD~1      # Undo last commit (discard changes)
```

### Stash Changes
```bash
git stash                    # Temporarily save changes
git stash list              # List stashed changes
git stash pop               # Restore stashed changes
git stash drop              # Delete stashed changes
```

### Branch Management
```bash
git branch                   # List local branches
git branch -r               # List remote branches
git branch -d feature/name  # Delete local branch
git push origin --delete feature/name  # Delete remote branch
```

## Pre-commit Checklist

Before committing, make sure:
- [ ] Code runs without errors
- [ ] No debugging code (print statements, debugger, etc.)
- [ ] No sensitive data (API keys, passwords)
- [ ] Code is formatted consistently
- [ ] Commit message is clear and descriptive
- [ ] Only committing relevant files (not temporary files)

## Emergency: Reverting Production

If you need to quickly revert production:

```bash
# Find the last good commit
git log --oneline

# Revert to that commit
git checkout main
git revert <bad-commit-hash>
git push origin main

# Or hard reset (destructive, use with caution)
git reset --hard <last-good-commit>
git push origin main --force
```

## Tags for Releases

When deploying to production:

```bash
# Create a tag for the release
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# List all tags
git tag -l

# Checkout a specific version
git checkout v1.0.0
```

## Tips

1. **Commit often**: Small, focused commits are better than large ones
2. **Pull before push**: Always pull latest changes before pushing
3. **Branch names**: Use descriptive names (feature/add-jwt-auth not feature/fix)
4. **Test before merge**: Always test on development before merging to staging
5. **Never force push** to main, staging, or development (only to feature branches)
6. **.env files**: Never commit them, always use .env.example as template
7. **Clean up**: Delete feature branches after merging

## Current Status

- [x] Git repository initialized
- [x] .gitignore configured
- [x] .gitattributes configured
- [x] .env.example created
- [ ] Development branch created
- [ ] Staging branch created
- [ ] First commit made
- [ ] Remote repository set up (GitHub, GitLab, etc.)
