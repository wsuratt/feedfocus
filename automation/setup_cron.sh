#!/bin/bash
#
# Setup cron job for daily refresh
# Run this script once to install the cron job
#

# Get absolute path to project
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
PYTHON_PATH="$PROJECT_DIR/.venv/bin/python"
SCRIPT_PATH="$PROJECT_DIR/automation/daily_refresh_queue.py"

# Verify files exist
if [ ! -f "$PYTHON_PATH" ]; then
    echo "Error: Python venv not found at $PYTHON_PATH"
    echo "Please run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Error: Script not found at $SCRIPT_PATH"
    exit 1
fi

# Create cron job (runs at 2:00 AM daily)
CRON_JOB="0 2 * * * $PYTHON_PATH $SCRIPT_PATH >> $PROJECT_DIR/logs/daily_refresh.log 2>&1"

# Check if cron job already exists
(crontab -l 2>/dev/null | grep -F "$SCRIPT_PATH") && {
    echo "Cron job already exists. Remove it first with:"
    echo "  crontab -e"
    echo "Or run: crontab -l | grep -v 'daily_refresh_queue.py' | crontab -"
    exit 1
}

# Add cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✓ Cron job installed successfully!"
echo ""
echo "Schedule: Daily at 2:00 AM"
echo "Command: $PYTHON_PATH $SCRIPT_PATH"
echo "Log: $PROJECT_DIR/logs/daily_refresh.log"
echo ""
echo "To view cron jobs: crontab -l"
echo "To remove: crontab -e (and delete the line)"
echo ""
echo "To test manually:"
echo "  cd $PROJECT_DIR"
echo "  $PYTHON_PATH automation/daily_refresh_queue.py --dry-run"
echo "  $PYTHON_PATH automation/daily_refresh_queue.py"
