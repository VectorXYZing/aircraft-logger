#!/bin/bash

# Check for a commit message
if [ -z "$1" ]; then
  echo "Usage: ./git_update.sh \"Your commit message here\""
  exit 1
fi

cd "$(dirname "$0")" || exit

echo "Staging changes..."
git add .

echo "Committing..."
git commit -m "$1"

echo "Pushing to GitHub..."
git push
