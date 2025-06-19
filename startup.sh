#!/bin/bash

# Create venv if not exists
if [ ! -d "antenv" ]; then
  python3 -m venv antenv
fi

# Activate it
source antenv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Start your app
uvicorn app.main:app --host=0.0.0.0 --port=8000
