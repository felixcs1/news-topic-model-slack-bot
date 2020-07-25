import emoji
import slack
import hmac
import hashlib

'''
    Functions for posting messages to slack
'''

def initialise_slack_client(slack_token):
    return slack.WebClient(slack_token)

def post_message_to_slack(slack_client, slack_channel, message, emoji=emoji.emojize(':chart_with_upwards_trend:')):
    slack_text = f"{emoji} {message}"

    try:
        res = slack_client.api_call(
            'chat.postMessage', json={
            'channel': slack_channel,
            'text': slack_text
            }
        )
        print(f"Wrote to {slack_channel}")
      
    except Exception as e:
        print(f"Error writing to slack, {e}")

def post_warning_to_slack(slack_client, slack_channel, error_message):
    slack_text = f"{emoji.emojize(':warning:')} {error_message}"

    try:
        slack_client.api_call(
            'chat.postMessage',json={
            'channel': slack_channel,
            'text': slack_text
            }
        )
        print(f"Wrote warning to {slack_channel}")

    except Exception as e:
        print(f"Error writing to slack, {e}")


def post_error_to_slack(slack_client, slack_channel, error_message):
    slack_text = f"{emoji.emojize(':bangbang:')} ERROR: {error_message}"

    try:
        slack_client.api_call(
            'chat.postMessage',json={
            'channel': slack_channel,
            'text': slack_text
            }
        )
        print(f"Wrote error to {slack_channel}")

    except Exception as e:
        print(f"Error writing to slack, {e}")



# We dont use signing secret as its a bit over kill and means you can't tweak example event 
# Instead we w=auth slack requests with verifcation token
# def validate_slack_request(event, signing_secret):

#     '''
#         Hash the body and timestamp of slack request  with HMAC SHA256
#         using the signing secret from th slack app
#         Compare hash to the header 'X-Slack-Signature' to authenticate, followed 
#         https://api.slack.com/docs/verifying-requests-from-slack
#     '''
#     body = event['body']
#     x_signature = event['headers']['X-Slack-Signature'].split("=")[1]
#     timestamp = event['headers']['X-Slack-Request-Timestamp']

#     unhashed = f"v0:{timestamp}:{body}".encode('utf-8')

#     trial_signature = hmac.new(
#         bytes(signing_secret, 'utf-8'),
#         msg=unhashed,
#         digestmod=hashlib.sha256
#     ).hexdigest()

#     if (trial_signature != x_signature):
#         raise Exception("Slack request authentication failed")
#     else:
#         print("Slack request authentication succeeded")


# import os 
# s = initialise_slack_client(os.environ['STATS_RELEASES_SLACK_AUTH_TOKEN'])
# post_message_to_slack(s, "DCPE887LK", emoji.emojize(':heart:'))