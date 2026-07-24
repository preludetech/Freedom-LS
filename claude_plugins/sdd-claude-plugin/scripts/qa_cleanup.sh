#!/bin/sh
# qa_cleanup.sh — remove artifacts from the previous QA run in the current dir.
# Usage: ./qa_cleanup.sh

if [ -f qa_report.md ]; then
    rm -f qa_report.md
    echo "Removed qa_report.md"
fi

if [ -d screenshots ]; then
    rm -rf screenshots
    echo "Removed screenshots/ directory"
fi
