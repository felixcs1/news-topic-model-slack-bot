import re
import unicodedata
import emoji
import json
import datetime as dt
import os
import traceback
import boto3
import requests
import zipfile
import time
import logging


import config
from post_to_slack import *
from topic_labelling import assign_topic_labels

logger = logging.getLogger(__name__)
logger.setLevel(config.log_level)

### CREDENTIALS FOR SLACK AND DROPBOX ######
SLACK_AUTH_TOKEN = os.environ['TOPIC_MODEL_SLACK_AUTH_TOKEN']
CPS_API_KEY = os.environ['CPS_API_KEY']

DEFAULT_SLACK_CHANNEL = "#topic-model"

# This is the entry point of the lambda 
def lambda_handler(event, context):
    download_models()

    slack = initialise_slack_client(SLACK_AUTH_TOKEN)

    trigger = get_event_source(event)

    # Set the channel to post output to
    slack_channel = get_slack_channel_name(event, trigger)
    try:
        event_body=parse_slack_event_body(event)
        
        article_id = event_body['text']
        title, article_content = get_article_content(article_id)

        # Post title 
        logger.debug(f"Writing to slack channel {slack_channel}")
        post_message_to_slack(slack, slack_channel, f"Getting labels for article:\n*{title}*", emoji=':bbcnews:')

        # apply model
        article_labels = assign_topic_labels(article_content)
        print(article_labels)

        # Prepare lables for posting to slack 
        labels_string = ', '.join([f"{topic['name']} ({round(topic['score'],2)})" for topic in article_labels])
        topics_message = f"Labels: *{labels_string}*"
        post_message_to_slack(slack, slack_channel, topics_message, emoji=emoji.emojize(':tick:'))

        return { "statusCode": 200, "body": "Lambda completed sucessfully" }
    except Exception as e:
        # Whatever exception is raised throughout the app it is caught and reported here
        # If the lmabda raises an exception it will retry with the same event 3 times, we 
        # don't want this so just print the stack trace to see in logs and on slack
        traceback.print_exc()
        post_error_to_slack(slack, slack_channel, e)
        print("ERROR CAUGHT: ", e)



def get_article_content(article_id):

    query_string = f"http://content-api-a127.api.bbci.co.uk/cms/cps/asset/{article_id}?api_key={CPS_API_KEY}"

    headers = {
        "X-Candy-Platform": "desktop",
        "x-candy-audience": "domestic",
        "Accept": "application/json"
    }
    response = requests.get(query_string, headers=headers)

    if response.status_code != 200:
        raise Exception("Invalid id given, article could not be found")
    
    response_json = response.json()
    
    title = response_json["results"][0]["title"]
    summary = response_json["results"][0]["summary"]
    body_with_html = response_json["results"][0]["body"]

    body_cleaned = re.sub('<[^<]+?>', '', body_with_html)

    return title, f"{title} {summary} {body_cleaned}"


def download_models():
    """Download models to local cache from S3 if they're not already there."""
    
    print("pre download")
    for item in os.walk('/tmp'):
        print(item)

    print("Download models" , config.download_models)
    print("Download models" , os.path.exists(config.local_model_path), config.local_model_path)

    if config.download_models and not os.path.exists(config.local_model_path):
        logger.debug(
            f'Fetching models from bucket: {config.model_bucket} '
            f'and key: {config.model_zip_s3_key} '
            f'to local path: {config.local_model_zip_path}'
            )
        os.mkdir(config.local_model_path)
        s3_client = boto3.client('s3')
        s3_client.download_file(
            config.model_bucket, config.model_zip_s3_key,
            config.local_model_zip_path
            )
        logger.debug(
            f'Downloaded models to {config.local_model_zip_path}. Unzipping...'
            )
        with zipfile.ZipFile(config.local_model_zip_path, 'r') as zip_ref:
            zip_ref.extractall(config.local_model_path)

    print("after download")
    for item in os.walk('/tmp'):
        print(item)


def get_event_source(event):
    '''
        Check for field unique to the given type of event and return a string
        indicating the type of trigger
    '''
 
    if "slack-body" in event.keys():
        return "slack-trigger"
    elif "region" in event.keys() and "resources" in event.keys():
        return "aws-trigger"
    else:
        raise Exception("Lambda trigger failed, no recognised event")


def get_slack_channel_name(event, trigger):
    '''
        Get channel name for the purposes of notifying users which channel the lambda was called from
        If private or direct message we need the channel id in order to post to the channel

        Returns: channel name or channel id if channel is direct or private message
    '''

    if trigger == "slack-trigger":
        event_params = parse_slack_event_body(event)
        channel_name = event_params['channel_name']

        if channel_name == 'privatemessage' or channel_name == 'directmessage' or channel_name == 'privategroup':
            return event_params['channel_id']
        else:
            return channel_name
    elif trigger == "aws-trigger":
        return DEFAULT_SLACK_CHANNEL


def validate_event_and_post_trigger_to_slack(event, slack_client, slack_channel, trigger):
    '''
        Posts a triggered message to #stats-releases to say either:
        The person and channel the bot has been triggered from.
        Or to say it has been triggered on a schedule.
        Raises and exception if slack token not verified
    '''

    # Establish where the trigger came from and set to and from dates accordingly
    if trigger == "slack-trigger":
        event_params = parse_slack_event_body(event)

        if slack_channel == DEFAULT_SLACK_CHANNEL:
            trigger_message = f"Lambda Triggered from slack command by {event_params['user_name']} in this channel"
        else:
            post_message_to_slack(slack_client, slack_channel, "Stats releases lambda triggered")
            trigger_message = f"{event_params['user_name']} triggered lambda from slack command" + \
                              f" in channel {slack_channel if '#' in slack_channel else '#directmessage'}"
        
        emoji_ = emoji.emojize(':raising_hand:')
    elif trigger == "aws-trigger":
        trigger_message = f"Lambda triggered on schedule"
        emoji_ = emoji.emojize(':calendar:')

    post_message_to_slack(slack_client, DEFAULT_SLACK_CHANNEL, trigger_message, emoji_)

def parse_slack_event_body(event):
    '''
        Takes slack event body and returns a dict of key value pairs 
    '''
    body = event["slack-body"]
    return dict([k_v_pair.split("=") for k_v_pair in body.split("&")])



# This is run when testing locally but not when deployed
# It simply sets the event from an example json file
# and context and runs lambda_handler function above
if __name__ == "__main__":

    import json
    import os
    
    dir_path = os.path.dirname(os.path.realpath(__file__))

    config.local_model_path = os.path.join(dir_path, "../models")

    base_dirname = os.path.realpath('')
    event_path = os.path.join(base_dirname, 'events/event_slack_body.json')

    with open(event_path) as json_file:
        event = json.load(json_file)
        context = []
        lambda_handler(event, context)
