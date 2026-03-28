#!/bin/bash
cd /root/RolePrep
git fetch --all
git reset --hard origin/main
cd backend
source venv/bin/activate
pip install -r ../requirements.txt
