#!/bin/bash
set -e

MODULE_INPUT=$1
MAGIC_MODE=${2:-true}

if [ -z "$MODULE_INPUT" ]; then
  read -p "Enter module prefix or name (e.g., 01 or 01-foundation): " MODULE_INPUT
fi

if [ -z "$MODULE_INPUT" ]; then
  echo "Error: Module name is required."
  exit 1
fi

# Find the actual module directory based on the prefix
ACTUAL_MODULE_DIR=$(find modules -maxdepth 1 -type d -name "${MODULE_INPUT}*" | head -n 1)

if [ -z "$ACTUAL_MODULE_DIR" ]; then
  echo "Error: Could not find any module matching prefix '${MODULE_INPUT}'."
  exit 1
fi

# Extract just the basename
MODULE_NAME=$(basename "$ACTUAL_MODULE_DIR")
DEST_DIR_SOLUTION="${ACTUAL_MODULE_DIR}/solution"

echo "Snapshotting workspace to ${DEST_DIR_SOLUTION}..."
mkdir -p "$DEST_DIR_SOLUTION"

# Rsync workspace to modules/MODULE_NAME/solution, excluding known heavy/ephemeral dirs
rsync -a --delete \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.git' \
  --exclude='.pytest_cache' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  workspace/ "$DEST_DIR_SOLUTION/"
echo "✅ Workspace snapshot saved to ${DEST_DIR_SOLUTION}"

if [ "$MAGIC_MODE" = "true" ]; then
  # Extract the numeric prefix (e.g., "01" from "01-foundation")
  CURRENT_NUM=$(echo "$MODULE_NAME" | grep -o '^[0-9]\+')
  
  if [ -n "$CURRENT_NUM" ]; then
    # Calculate next module number, padded to 2 digits
    NEXT_NUM=$(printf "%02d" $((10#$CURRENT_NUM + 1)))
    
    # Try to find the next module directory
    NEXT_MODULE_DIR=$(find modules -maxdepth 1 -type d -name "${NEXT_NUM}*" | head -n 1)
    
    if [ -n "$NEXT_MODULE_DIR" ]; then
      DEST_DIR_NEXT_START="${NEXT_MODULE_DIR}/start"
      echo "✨ Magic mode: Automatically cascading snapshot to ${DEST_DIR_NEXT_START}..."
      mkdir -p "$DEST_DIR_NEXT_START"
      rsync -a --delete \
        --exclude='.venv' \
        --exclude='__pycache__' \
        --exclude='.git' \
        --exclude='.pytest_cache' \
        --exclude='*.pyc' \
        --exclude='.DS_Store' \
        workspace/ "$DEST_DIR_NEXT_START/"
      echo "✅ Magic snapshot completed. You are ready for Module ${NEXT_NUM}"
    else
      echo "ℹ️ Magic mode: No next module found starting with '${NEXT_NUM}'. Skipping forward setup."
    fi
  else
    echo "ℹ️ Magic mode: Could not extract numeric prefix from '${MODULE_NAME}'. Skipping forward setup."
  fi
fi
