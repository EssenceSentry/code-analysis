#!/bin/bash

# analyze_python_code.sh
# Description: Runs multiple complexity metrics on a Python file or repository
#              and generates a summary of the results.
#              Excludes .venv and other common non-project directories.
#              Summarizes Flake8 complexity findings.
#              Attempts to influence Complexipy table width via COLUMNS variable.
# Author: EssenceSentry

# --- Configuration ---
# Cyclomatic Complexity threshold for Flake8 to report functions
# Functions with CC > this value will be counted.
# Common values are 10, 12, or 15.
FLAKE8_MAX_COMPLEXITY=12

# Common directories/patterns to exclude for most tools
# Radon uses glob patterns, others use simple names or paths.
RADON_EXCLUDE_PATTERNS="*/.venv/*,*/.git/*,*/__pycache__/*,*/build/*,*/dist/*,*.egg-info/*"
STANDARD_EXCLUDE_DIRS=".venv,.git,__pycache__,build,dist,*.egg-info"


# --- Helper Functions ---
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo "[ERROR] Tool '$1' not found. Please install it first (e.g., using install_complexity_tools.sh)."
        exit 1
    fi
}

print_header() {
    echo ""
    echo "================================================================="
    echo "$1"
    echo "================================================================="
}

# --- Main Script ---

# Check if a target path is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_python_file_or_directory>"
    exit 1
fi

TARGET_PATH="$1"
# TARGET_BASENAME is not used in this version of the script from the user, so omitting its definition.

# Check if the target path exists
if [ ! -e "$TARGET_PATH" ]; then
    echo "[ERROR] Path '$TARGET_PATH' does not exist."
    exit 1
fi

echo "Analyzing code complexity for: $TARGET_PATH"
echo "Analysis Date: $(date)"
echo "Excluding directories like: $STANDARD_EXCLUDE_DIRS"
echo "-----------------------------------------------------------------"

# 0. Verify necessary tools are installed
check_tool "cloc"
check_tool "radon"
check_tool "flake8"
check_tool "complexipy"

# 1. Lines of Code (cloc)
print_header "Lines of Code (cloc)"
# --exclude-dir can be used multiple times or take a comma-separated list
CLOC_EXCLUDES=""
for dir_to_exclude in $(echo $STANDARD_EXCLUDE_DIRS | tr ',' ' '); do
    CLOC_EXCLUDES="$CLOC_EXCLUDES --exclude-dir=$dir_to_exclude"
done

if [ -d "$TARGET_PATH" ]; then
    # shellcheck disable=SC2086
    cloc --include-lang=Python $CLOC_EXCLUDES "$TARGET_PATH"
else
    # For a single file, --exclude-dir is not relevant unless it's within an excluded path,
    # but cloc on a single file is usually fine.
    cloc "$TARGET_PATH"
fi


# 2. Radon - Raw Metrics (LOC, SLOC, Comments, Blank lines)
print_header "Radon - Raw Metrics (Source Lines of Code, Comments etc.)"
if [ -d "$TARGET_PATH" ]; then
    echo "[INFO] Calculating sum for directory (SLOC, Comments, Blank, Total LOC)..."
    radon raw --exclude "$RADON_EXCLUDE_PATTERNS" "$TARGET_PATH" -s
else
    radon raw "$TARGET_PATH" # Exclude not typically needed for single file analysis unless path matches
fi

# 3. Radon - Cyclomatic Complexity (CC)
print_header "Radon - Cyclomatic Complexity (CC)"
echo "[INFO] Average CC and per-function/method blocks (A=low, F=high risk)."
radon cc --exclude "$RADON_EXCLUDE_PATTERNS" "$TARGET_PATH" -s -a -nb

# 4. Radon - Maintainability Index (MI)
print_header "Radon - Maintainability Index (MI)"
echo "[INFO] Higher is better (0-100). Grades: A (high), B (medium), C (low)."
radon mi --exclude "$RADON_EXCLUDE_PATTERNS" "$TARGET_PATH" -s

# 5. Flake8 - Count of Functions with High Cyclomatic Complexity
print_header "Flake8 - Count of Functions with Cyclomatic Complexity > $FLAKE8_MAX_COMPLEXITY"
# This will count functions that are too complex according to Flake8's mccabe plugin.
# Flake8's default exclude includes .venv, .git, __pycache__, but we add it explicitly.
FLAKE8_COMPLEX_FUNCTION_COUNT=$(flake8 --max-complexity="$FLAKE8_MAX_COMPLEXITY" --exclude="$STANDARD_EXCLUDE_DIRS" "$TARGET_PATH" | wc -l)
if [ "$FLAKE8_COMPLEX_FUNCTION_COUNT" -gt 0 ]; then
    echo "[WARNING] Flake8 found $FLAKE8_COMPLEX_FUNCTION_COUNT function(s) with CC > $FLAKE8_MAX_COMPLEXITY."
    echo "[INFO] To see the list of these functions, run manually: flake8 --max-complexity=$FLAKE8_MAX_COMPLEXITY --exclude=$STANDARD_EXCLUDE_DIRS \"$TARGET_PATH\""
else
    echo "[INFO] Flake8 found no functions with CC > $FLAKE8_MAX_COMPLEXITY."
fi

# 6. Complexipy - Cognitive Complexity
print_header "Complexipy - Cognitive Complexity"
echo "[INFO] Measures how difficult code is to understand. Lower is better."
echo "[INFO] Complexipy typically respects .gitignore. Ensure .venv is in your .gitignore if issues arise."
echo "[INFO] Attempting to set a wider terminal width (COLUMNS=200) for Complexipy's table output..."

# Store original COLUMNS value if it's set
ORIGINAL_COLUMNS=""
IS_COLUMNS_SET=false
if [ -n "$COLUMNS" ]; then
    ORIGINAL_COLUMNS="$COLUMNS"
    IS_COLUMNS_SET=true
fi

# Set a large width for complexipy's rich table
export COLUMNS=200

# Run complexipy
complexipy "$TARGET_PATH" --sort name

# Restore original COLUMNS value
if [ "$IS_COLUMNS_SET" = true ]; then
    export COLUMNS="$ORIGINAL_COLUMNS"
    echo "[INFO] Restored original COLUMNS value to '$ORIGINAL_COLUMNS'."
else
    unset COLUMNS # If it wasn't set before, unset it
    echo "[INFO] Unset COLUMNS as it was not originally set."
fi


echo ""
echo "-----------------------------------------------------------------"
echo "Complexity Analysis Summary Finished for: $TARGET_PATH"
echo "-----------------------------------------------------------------"

exit 0
