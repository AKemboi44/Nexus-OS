#!/bin/bash
# Create Pull Request from feature/federated-search-mesh to main

# Variables
OWNER="AKemboi44"
REPO="Nexus-OS"
HEAD_BRANCH="feature/federated-search-mesh"
BASE_BRANCH="main"
TITLE="Merge federated-search-mesh feature into main"
BODY="This pull request integrates the federated search mesh feature into the main branch.

## Overview
Merges all changes from the feature/federated-search-mesh branch, including new federated search capabilities and mesh networking enhancements.

## Changes
- Federated search mesh implementation
- Related updates and improvements

## Testing
Please review and test the changes thoroughly before merging."

# Create PR using GitHub CLI
gh pr create \
  --base "$BASE_BRANCH" \
  --head "$HEAD_BRANCH" \
  --title "$TITLE" \
  --body "$BODY"

echo "Pull request created successfully!"
