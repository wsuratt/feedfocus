#!/bin/bash
#
# Setup systemd timer for daily refresh
# Run this script once on production server
#

set -e

echo "Setting up FeedFocus Daily Refresh systemd timer..."

# Copy service and timer files
sudo cp feedfocus-daily-refresh.service /etc/systemd/system/
sudo cp feedfocus-daily-refresh.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start timer
sudo systemctl enable feedfocus-daily-refresh.timer
sudo systemctl start feedfocus-daily-refresh.timer

echo "✓ Systemd timer installed successfully!"
echo ""
echo "Status commands:"
echo "  sudo systemctl status feedfocus-daily-refresh.timer"
echo "  sudo systemctl status feedfocus-daily-refresh.service"
echo ""
echo "List all timers:"
echo "  systemctl list-timers"
echo ""
echo "View logs:"
echo "  sudo journalctl -u feedfocus-daily-refresh.service"
echo "  tail -f /home/ubuntu/feedfocus/logs/daily_refresh.log"
echo ""
echo "Run manually:"
echo "  sudo systemctl start feedfocus-daily-refresh.service"
echo ""
echo "Disable:"
echo "  sudo systemctl stop feedfocus-daily-refresh.timer"
echo "  sudo systemctl disable feedfocus-daily-refresh.timer"
