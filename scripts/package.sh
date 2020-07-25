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
rm -rf /app/dist/*.dist-info /app/dist/bin /app/dist/botocore /app/dist/boto3 /app/dist/docutils /app/dist/jmespath /app/dist/dateutil /app/dist/s3transfer /app/dist/six.py \
		/app/dist/gensim/test /app/dist/spacy/tests /app/dist/scipy/special/tests /app/dist/scipy/linalg/tests /app/dist/scipy/spatial/tests /app/dist/scipy/stats/tests \
		/app/dist/scipy/sparse/tests  /app/dist/scipy/optimize/tests /app/dist/scipy/signal/tests /app/dist/scipy/interpolate/tests /app/dist/scipy/io/matlab/tests \
		/app/dist/scipy/ndimage/tests /app/dist/scipy/fftpack/tests \
		/app/dist/numpy/core/tests /app/dist/numpy/random/tests /app/dist/numpy/lib/tests /app/dist/numpy/ma/tests /app/dist/numpy/polynomial/tests \
		/app/dist/bs4/tests /app/dist/smart_open/tests \
		/app/dist/spacy/lang/fr /app/dist/spacy/lang/pl /app/dist/spacy/lang/pt /app/dist/spacy/lang/lt /app/dist/spacy/lang/fa \
        /app/dist/spacy/lang/sk /app/dist/spacy/lang/ru /app/dist/spacy/lang/el /app/dist/spacy/lang/nl 

cd /app/dist
zip -rq /app/$deploy_zip .
