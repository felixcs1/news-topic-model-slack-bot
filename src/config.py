import os

log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()

# Models
download_models = os.getenv('DOWNLOAD_MODELS', 'True') == 'True'
model_bucket = os.getenv('MODEL_BUCKET', 'topic-model-slack-bot-lambda-code-bucket')
model_zip_s3_key = os.getenv('MODEL_ZIP_S3_KEY', 'models.zip')
local_model_path = os.getenv('LOCAL_MODEL_PAT', '/tmp/models')
local_model_zip_path = os.path.join(local_model_path, 'models.zip')

# Topic labelling config

# topics below this score aren't added as tags
topic_score_threshold_low = 0.18 

# the number of topic scores to sum to this values
topic_score_threshold_high = 0.60 

# The label assigned when the model does not give a label
no_topic_label = "Other articles"