#!/bin/bash
set -euo pipefail

INPUT=$(cat)

# Guard against malformed JSON input
if ! echo "$INPUT" | jq -e . > /dev/null 2>&1; then
    exit 0
fi

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""')

# --- Edit/Write: check for blocked code patterns ---
if [[ "$TOOL_NAME" == "Edit" || "$TOOL_NAME" == "Write" ]]; then
    # Get the content to check
    CONTENT=""
    if [[ "$TOOL_NAME" == "Edit" ]]; then
        CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // ""')
    elif [[ "$TOOL_NAME" == "Write" ]]; then
        CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // ""')
    fi

    # Check for blocked code patterns (use .method( prefix to avoid false positives)
    BLOCKED_PATTERNS=(
        '.raw('
        '.extra('
        'RawSQL'
        'mark_safe('
        '@csrf_exempt'
        'eval('
        'exec('
        'pickle.loads('
        'yaml.load('
        '**request.POST.dict()'
        '**request.GET.dict()'
    )

    for pattern in "${BLOCKED_PATTERNS[@]}"; do
        if [[ "$CONTENT" == *"$pattern"* ]]; then
            echo "BLOCKED: Dangerous pattern '$pattern' detected. This pattern is not allowed per security policy."
            exit 2
        fi
    done

    # Check for modifications to .env files (but allow .env.example)
    FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // ""')
    BASENAME=$(basename "$FILE_PATH")
    if [[ "$BASENAME" == .env* && "$BASENAME" != ".env.example" ]]; then
        echo "BLOCKED: Modifications to environment files ($BASENAME) are not allowed."
        exit 2
    fi

    # Block modifications to existing migration files
    if [[ "$FILE_PATH" == */migrations/[0-9]* ]]; then
        echo "BLOCKED: Modifications to existing migration files are not allowed. Create new migrations instead."
        exit 2
    fi
fi

# --- Bash: check for dangerous commands ---
if [[ "$TOOL_NAME" == "Bash" ]]; then
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

    if [[ "$COMMAND" == *"rm -rf"* ]]; then
        echo "BLOCKED: 'rm -rf' is not allowed."
        exit 2
    fi

    if [[ "$COMMAND" == *".env"* && "$COMMAND" != *".env.example"* ]]; then
        echo "BLOCKED: Accessing .env files via bash is not allowed."
        exit 2
    fi

    if [[ "$COMMAND" == *"id_rsa"* ]]; then
        echo "BLOCKED: Accessing SSH private keys is not allowed."
        exit 2
    fi

    # Check for .pem and .key file access
    if echo "$COMMAND" | grep -qE '\.(pem|key)\b'; then
        echo "BLOCKED: Accessing .pem or .key files is not allowed."
        exit 2
    fi
fi

exit 0
