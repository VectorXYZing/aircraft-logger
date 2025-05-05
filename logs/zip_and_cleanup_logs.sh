#!/bin/bash

# Directories
LOG_DIR="/home/pi/aircraft_logs"
ZIP_DIR="$LOG_DIR/zipped"
mkdir -p "$ZIP_DIR"

# Date strings
YESTERDAY=$(date -u -d "yesterday" +%F)
CSV_FILE="$LOG_DIR/aircraft_log_${YESTERDAY}.csv"
ZIP_FILE="$ZIP_DIR/${YESTERDAY}.zip"

# Zip if file exists
if [ -f "$CSV_FILE" ]; then
    zip -j "$ZIP_FILE" "$CSV_FILE" && rm "$CSV_FILE"
    echo "Zipped and removed $CSV_FILE"
else
    echo "No CSV to archive for $YESTERDAY"
fi
