#!/usr/bin/env python3
"""
Basic validation for generated ADK code.

Checks for common issues:
- Required imports
- Basic syntax validity
- Common ADK patterns
"""

import ast
import sys
from typing import List, Tuple


def validate_adk_code(code: str) -> Tuple[bool, List[str]]:
    """
    Validate ADK Python code for common issues.

    Args:
        code: Python code string to validate

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    # 1. Check syntax validity
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        issues.append(f"Syntax error at line {e.lineno}: {e.msg}")
        return False, issues

    # 2. Extract imports
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])

    # 3. Check for common ADK usage patterns
    code_lower = code.lower()

    # Check if using Agent/LlmAgent without google.adk import
    if ('agent(' in code_lower or 'llmagent(' in code_lower) and 'google' not in imports:
        issues.append("Warning: Using Agent/LlmAgent but 'google.adk' not imported")

    # Check if using Runner without import
    if 'runner(' in code_lower and 'google' not in imports:
        issues.append("Warning: Using Runner but 'google.adk' not imported")

    # Check if using tools without proper imports
    if '@tool' in code_lower or 'functiontool' in code_lower:
        if 'google' not in imports:
            issues.append("Warning: Using tools but 'google.adk' not imported")

    # Check for Session usage without service
    if 'session' in code_lower and 'sessionservice' not in code_lower:
        if 'get_session' not in code and 'session=' not in code:
            issues.append("Info: Using sessions - ensure SessionService is configured")

    # 4. Check for common mistakes
    if 'from adk import' in code:
        issues.append("Error: Use 'from google.adk import' not 'from adk import'")

    if '.run(' in code and 'runner' not in code_lower:
        issues.append("Warning: Using .run() - ensure Runner is instantiated")

    # 5. Check for required patterns
    has_agent_definition = any(
        'Agent(' in code,
        'LlmAgent(' in code,
        'SequentialAgent(' in code,
        'ParallelAgent(' in code,
        'LoopAgent(' in code,
        'BaseAgent' in code
    )

    if len(code) > 100 and not has_agent_definition:
        issues.append("Info: No agent definition found - is this intentional?")

    # If no issues found, code looks good
    is_valid = not any(issue.startswith("Error:") for issue in issues)

    return is_valid, issues


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: validate_adk_code.py <file.py>", file=sys.stderr)
        print("   or: validate_adk_code.py --stdin", file=sys.stderr)
        sys.exit(1)

    # Read code from file or stdin
    if sys.argv[1] == "--stdin":
        code = sys.stdin.read()
        filename = "<stdin>"
    else:
        filename = sys.argv[1]
        try:
            with open(filename, 'r') as f:
                code = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {filename}", file=sys.stderr)
            sys.exit(1)

    # Validate
    is_valid, issues = validate_adk_code(code)

    # Report results
    if issues:
        print(f"Validation results for {filename}:")
        print("-" * 50)
        for issue in issues:
            print(f"  {issue}")
        print("-" * 50)
    else:
        print(f"✓ {filename} looks good!")

    # Exit code: 0 if valid, 1 if errors found
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
