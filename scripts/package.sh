#!/bin/bash
# Arg $1 is the name of the deploy package zip file 
deploy_zip=$1
rm -f /app/$deploy_zip
rm -rf /app/dist
mkdir /app/dist

# Use upgrade here to overwrite previous installation if there are any
python3 -m pip install -r /app/requirements.txt -t /app/dist --upgrade
cp -r /app/src/* /app/dist
rm -rf /app/dist/*.dist-info
cd /app/dist
zip -rq /app/$deploy_zip .
