#!/bin/bash
#python3 -m venv myenv
source /home/art3m1sf0wl/program/botyt/myenv/bin/activate
# Activate the virtual environment
#source myenv/bin/activate
pip install google-api-python-client google-auth-oauthlib google-auth
# Install librosa in the virtual environment
python3 /home/art3m1sf0wl/program/botyt/youtubeupload.py
