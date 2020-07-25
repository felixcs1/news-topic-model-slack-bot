import re
import pandas as pd
import unicodedata
import emoji
import json
import datetime as dt
import os
import traceback

from persistence import *
from post_to_slack import *
from scraper import *

DBX_PATH = "/Visual Journalism/Data/2020/vjdata.stats.releases/"
DBX_RELEASES_TO_IGNORE = DBX_PATH + "ignore_releases/releases_to_ignore.csv"

### CREDENTIALS FOR SLACK AND DROPBOX ######
DBX_ACCCES_TOKEN = os.environ['STATS_RELEASES_DROPBOX_TOKEN']
SLACK_AUTH_TOKEN = os.environ['STATS_RELEASES_SLACK_AUTH_TOKEN']
SLACK_VER_TOKEN = os.environ['STATS_RELEASES_SLACK_VER_TOKEN']
DBX_PAPER_FOLDER_ID_SCHEDULE = os.environ['STATS_RELEASES_DROPBOX_PAPER_FOLDER_ID_SCHEDULE']
DBX_PAPER_FOLDER_ID_SLACK = os.environ['STATS_RELEASES_DROPBOX_PAPER_FOLDER_ID_SLACK']
DBX_PAPER_BASE_URL = "https://paper.dropbox.com/doc/"

DEFAULT_SLACK_CHANNEL = "#stats-releases"

# This is the entry point of the lambda 
def lambda_handler(event, context):

    # Determine how the lambda was triggered raise error if unrecognised
    trigger = get_event_source(event)
    
    try:
        # Intialise dropbox and slack clients
        dbx = initialise_dropbox_client(DBX_ACCCES_TOKEN)
        slack = initialise_slack_client(SLACK_AUTH_TOKEN)

        # Set the channel to post output to
        slack_channel = get_slack_channel_name(event, trigger)

        # Establish the source of event and get date range 
        validate_event_and_post_trigger_to_slack(event, slack, slack_channel, trigger)
        
        # Get date range
        FROM_DATE, TO_DATE = get_valid_dates(event, slack, slack_channel, trigger)
        
        # Perform scraping
        dropbox_file = read_from_dropbox(dbx, DBX_RELEASES_TO_IGNORE)
        releases_to_ignore = pd.read_csv(dropbox_file.raw) # pylint: ignore
        stats_releases, ignored_releases = scrape_releases(FROM_DATE, TO_DATE, releases_to_ignore, DBX_PATH, slack, slack_channel)

        # Write to dropbox 
        dbx_file_path = write_output_to_dropbox(stats_releases, ignored_releases, FROM_DATE, TO_DATE, dbx, trigger)

        # Write to dropbox paper doc
        paper_doc_url = write_output_to_dropbox_paper(stats_releases, FROM_DATE, TO_DATE, dbx, trigger)

        # Post data info to slack
        post_data_links_to_slack(FROM_DATE, TO_DATE, slack, slack_channel, dbx, dbx_file_path, paper_doc_url)

        print("\nSCRAPING COMPLETE!")
        return { "statusCode": 200, "body": "Lambda completed sucessfully" }
    except Exception as e:
        # Whatever exception is raised throughout the app it is caught and reported here
        # If the lmabda raises an exception it will retry with the same event 3 times, we 
        # don't want this so just print the stack trace to see in logs and on slack
        traceback.print_exc()
        post_error_to_slack(slack, slack_channel, e)
        print("ERROR CAUGHT: ", e)

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
            return f"#{channel_name}"
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

        # Certify the POST came from slack	  
        if event_params['token'] != SLACK_VER_TOKEN:	
            raise Exception("Lambda was triggered without correct slack token")

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

def get_valid_dates(event, slack_client, slack_channel, trigger):
    '''
        Get to and from dates 

        Either: Get default schedule dates
        From date: sunday after next, To date: the staurday after from date
        e.g if run on friday 10th Jan it will set: FROM: Sun 19th jan and TO: Sat 25th Jan 

        Or: Get dates from slack event body when triggered with slash comamnd
    '''

    if trigger == 'aws-trigger':
        now = dt.datetime.now()
        from_date = now + dt.timedelta(days=(13 - now.weekday()))
        to_date = from_date + dt.timedelta(days=6)
        return from_date, to_date

    elif trigger == 'slack-trigger':
        
        event_params = parse_slack_event_body(event)
        dates = event_params['text'].split("+")

        try:
            try:
                from_date = dt.datetime.strptime(dates[0], "%Y-%m-%d")
                to_date = dt.datetime.strptime(dates[1], "%Y-%m-%d")
            except:
                raise Exception("Must be YYYY-MM-DD")

            if (to_date < from_date):
                raise Exception("The from date must be before the to date!")
            if (to_date == from_date):
                raise Exception("The from date can't be the same as the to date!")
            if (from_date < dt.datetime.now()):
                raise Exception("The from date must be after todays date!")
            if (from_date > dt.datetime.now() + dt.timedelta(days=180) or (to_date > dt.datetime.now() + dt.timedelta(days=180))):
                raise Exception("Dates must be within 6 months of the current date")
        except Exception as e:
            raise Exception(f"Dates given are of the wrong format: {e}")

        return (from_date, to_date)
    else:
        return None


def get_nice_dates(from_date, to_date):
    '''
        Get nice date format for print out and naming paper docs
    '''
    nice_from_date = dt.datetime.strftime(from_date, "%a %d %b")
    nice_to_date = dt.datetime.strftime(to_date, "%a %d %b")
    return nice_from_date, nice_to_date

def write_output_to_dropbox(data, ignored_data, from_date, to_date, dbx, trigger):
    '''
        Takes data and writes to dropbox:
        In the slack_trigger_realeases folder if lambda triggered from slack
        In the scheduled_releases folder if lambda triggered on schedule

        Returns file path data written to
    '''

    print("Writing data to dropbox...")

    from_string = dt.datetime.strftime(from_date, "%Y-%m-%d")
    to_string = dt.datetime.strftime(to_date, "%Y-%m-%d")

    file_name = f"stats_releases_{from_string}_{to_string}.csv"

    if trigger == "slack-trigger":
        file_path = f"{DBX_PATH}slack_trigger_releases/{file_name}"
    else:
        file_path = f"{DBX_PATH}scheduled_releases/{file_name}"
       
    ignored_file_path = f"{DBX_PATH}ignored/ignored_{file_name}"

    write_dataframe_to_dropbox(dbx, ignored_data, ignored_file_path)
    write_dataframe_to_dropbox(dbx, data, file_path)
    
    return file_path

def write_output_to_dropbox_paper(data, from_date, to_date, dbx, trigger):
    '''
        Convert dataframe to markdown and write to a paper doc, depnenging on the
        trigger, write to either the slack or schedule folder. 
    '''

    print("Writing markdown table to dropbox paper...")

    nice_from_date, nice_to_date = get_nice_dates(from_date, to_date)

    # Nice formatting for output
    data['date'] = data['date'].dt.strftime("**%a** %d %b")
    # data['link'] = data['link'].apply(lambda link: f"[link]({link})")
    
    # First create a googlable link without dates in title 
    data.insert(1, 'google', data['release'].apply(lambda release: f"[{release.split(':')[0]}](https://www.google.com/search?q={release.split(':')[0]})"))

    # Then Hyper link the release title to the release page
    data['release'] = data['release'].apply(lambda title: f"[{title}]({data[data['release'] == title]['link'].values[0]})")
    data.drop(['link', 'day'], axis=1, inplace=True)

    # Convert df to a markdown table to write to paper
    dropbox_paper_title = f"Stats releases {nice_from_date} to {nice_to_date}"
    mark_down_header = pd.DataFrame([['---'] * len(data.columns)], columns=data.columns)

    stats_releases_md = pd.concat([mark_down_header, data])
    mark_down_data = stats_releases_md.to_csv(sep="|", index=False)


    if trigger == 'aws-trigger':
        file_id = write_to_dropbox_paper(dbx, dropbox_paper_title, mark_down_data, 'markdown', DBX_PAPER_FOLDER_ID_SCHEDULE)
    else:
        file_id = write_to_dropbox_paper(dbx, dropbox_paper_title, mark_down_data, 'markdown', DBX_PAPER_FOLDER_ID_SLACK)
        
    doc_url = f"{DBX_PAPER_BASE_URL}{dropbox_paper_title.replace(' ','-')}-{file_id}"

    return doc_url

def post_data_links_to_slack(from_date, to_date, slack_client, slack_channel, dbx, dbx_path, dbx_paper_url):
    '''
        Produce the slack output once scraping is completed
    '''

    dbx_url, dbx_download_url = get_urls_for_file(dbx, dbx_path)

    # Nice date strings to post to slack
    nice_from_date, nice_to_date = get_nice_dates(from_date, to_date)

    link_emoji = emoji.emojize(':link:')
    file_emoji = emoji.emojize(':open_file_folder:')
    message = f"Stats releases between *{nice_from_date}* and *{nice_to_date}*: \n"
    message += f"{link_emoji} <{dbx_url}|Link to dropbox> {link_emoji}"
    message += f"<{dbx_download_url}|Download csv> {link_emoji}"
    message += f"<{dbx_paper_url}|Paper Doc>"
    message += f"\n{file_emoji} `{dbx_path}` {file_emoji}"

    post_message_to_slack(slack_client, slack_channel, message)

# This is run when testing locally but not when deployed
# It simply sets the event from an example json file
# and context and runs lambda_handler function above
if __name__ == "__main__":

    import json
    import os

    base_dirname = os.path.realpath('')
    event_path = os.path.join(base_dirname, 'events/event_schedule.json')

    with open(event_path) as json_file:
        event = json.load(json_file)
        context = []
        lambda_handler(event, context)
