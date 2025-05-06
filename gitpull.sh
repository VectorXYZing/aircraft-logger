#!/bin/bash

cd ~/aircraft-logger || exit 1

echo "Pulling latest changes from GitHub..."
git pull

echo "Restarting aircraft-logger service..."
sudo systemctl restart aircraft-logger.service

echo "Restarting aircraft-dashboard service..."
sudo systemctl restart aircraft-dashboard.service

echo "Done!" 