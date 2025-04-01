#!/bin/bash

# Create and activate virtual environment
echo "Creating a virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run the application
echo "Starting Flask application..."
export FLASK_APP=app.py
export FLASK_ENV=development
flask run --host=0.0.0.0 --port=8080 