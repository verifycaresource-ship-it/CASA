#!/usr/bin/env bash
set -o errexit

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput
