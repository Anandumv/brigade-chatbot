#!/usr/bin/env bash
# Build script for Render

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Download spacy model for pixeltable
python -m spacy download en_core_web_sm
