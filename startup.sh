#!/bin/bash

echo "▶️ Running startup.sh..."

# Activate Python virtual env if needed (optional)
python3 -m venv antenv
source antenv/bin/activate

echo "📦 Installing requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🚀 Starting uvicorn..."
exec uvicorn app.main:app --host=0.0.0.0 --port=8000
