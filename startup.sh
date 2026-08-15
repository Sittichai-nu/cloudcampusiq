#!/bin/bash
pip install -r requirements.txt
flask --app app.py rebuild-content
gunicorn --bind=0.0.0.0:8000 --timeout 600 app:app