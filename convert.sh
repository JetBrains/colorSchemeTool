#!/bin/sh

TM_OUTDIR=./tmThemes/
IJ_OUTDIR=./intellijThemes/

# Check for Node.js and Python dependencies
missing_reqs=0
if ! command -v node >/dev/null 2>&1; then
    echo "Node.js is not installed. Please install Node.js to continue."
    missing_reqs=1
fi

# Determine the correct Python command (in some systems, python is not available
# and python3 is used instead, e.g. Debian-based systems)
PYTHON_CMD=python
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=python3
elif ! command -v python >/dev/null 2>&1; then
    echo "Python is not installed. Please install Python to continue."
    missing_reqs=1
fi

# Requirements not met, exit the script
if [ $missing_reqs -eq 1 ]; then
    exit 1
fi

echo "Please note that converted color schemes may not look 100% precise because of the differences between the tools."
echo "Starting conversion process..."

VSC_FILES=./vscThemes/*.json
for FILE in $VSC_FILES; do
    if [ -f "$FILE" ]; then
        FN=$(basename "$FILE")
        BASE=${FN%.*}
        echo "Converting $FILE to $TM_OUTDIR$BASE.tmTheme..."
        node vscToTm.js "$FILE" "$TM_OUTDIR$BASE.tmTheme" >> ./colorSchemeTool.log
    fi
done

TM_FILES=./tmThemes/*.tmTheme
for FILE in $TM_FILES; do
    if [ -f "$FILE" ]; then
        FN=$(basename "$FILE")
        BASE=${FN%.*}
        echo "Converting $FILE to $IJ_OUTDIR$BASE.icls..."
        $PYTHON_CMD colorSchemeTool.py "$FILE" "$IJ_OUTDIR$BASE.icls" >> ./colorSchemeTool.log
    fi
done

echo "Conversion process complete."

