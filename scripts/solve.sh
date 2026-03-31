#!/bin/bash
set -e

MODULE_INPUT=$1

if [ -z "$MODULE_INPUT" ]; then
  read -p "Enter module prefix or name to load the solution for (e.g., 02): " MODULE_INPUT
fi

if [ -z "$MODULE_INPUT" ]; then
  echo "Error: Module prefix is required."
  exit 1
fi

# Find the target directory matching the prefix
target_dir=$(find modules -maxdepth 1 -type d -name "${MODULE_INPUT}*" | head -n 1)

if [ -z "$target_dir" ]; then
  echo "Error: Module matching '${MODULE_INPUT}' not found."
  exit 1
fi

if [ ! -d "$target_dir/solution" ]; then
  echo "Error: No 'solution' directory found in $target_dir."
  exit 1
fi

echo "Applying ${target_dir}/solution to workspace..."
rm -rf workspace/*
cp -R "${target_dir}/solution/"* workspace/ 2>/dev/null || echo "Solution was empty."
echo "✅ Workspace successfully overwritten with the solution for $(basename $target_dir)."
