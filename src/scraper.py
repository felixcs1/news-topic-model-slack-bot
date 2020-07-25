from ons import *
from scot import *
from gss import *
from post_to_slack import *

import unicodedata

def scrape_releases(from_date, to_date, releases_to_ignore, dbx_path, slack_client, slack_channel):
    '''
        Scrape gov ons and gov.scot
    '''
    orgs = ["ONS", "GSS", "gov.scot"]
    all_org_data = []
    for org in orgs:
        try: 
            org_data = scrape_data_from_org(org, from_date, to_date)
            if len(org_data) == 0:
                url = get_website_url(org, from_date, to_date)
                post_no_data_warning(slack_client, slack_channel, org, url)
            else:
                post_message_to_slack(slack_client, slack_channel, f"Got data for {org}", emoji.emojize(":white_check_mark:"))
            all_org_data.append(org_data)
        except Exception as e:
            post_scraping_error(slack_client, slack_channel, org, e)

    # Combine and clean
    print("\nCombining and cleaning...")
    all_data = pd.concat(all_org_data, sort=False, ignore_index=True)

    if len(all_data) == 0:
        raise Exception("No data gathered on any websites in date range")

    all_data = all_data.sort_values(by=['date']).reset_index(drop=True)

    # Sanitise text entries
    all_data['synopsis'] = all_data['synopsis'].apply(lambda x: unicodedata.normalize('NFKC', x).replace('\n','').replace('\t', '').replace('\r', '').strip())
    all_data['release'] = all_data['release'].apply(lambda x: unicodedata.normalize('NFKC', x).replace('\n','').replace('\t', '').replace('\r', '').strip())
        
    print("Before ignoring, there are", all_data.shape[0], "releases")
    ignored_data = pd.DataFrame()
    for phrase in releases_to_ignore['keyword']:
        ignored_rows = all_data[all_data['release'].str.contains(phrase, case=False, regex=False)]
        ignored_data = pd.concat([ignored_data, ignored_rows])
        all_data = all_data[~all_data['release'].str.contains(phrase, case=False, regex=False)]
    print("After ignoring entries in releases_to_ignore.csv there are", all_data.shape[0], "releases")

    print("Done Cleaning\n")

    return all_data, ignored_data

def scrape_data_from_org(website, from_date, to_date):
    print(f"Scraping {website}...")
    if website == 'ONS':
        return get_ons_data(from_date, to_date)
    elif website == 'GSS':
        return get_gss_data(from_date, to_date)
    elif website == 'gov.scot':
        return get_scot_gov_data(from_date, to_date)

def get_website_url(website, from_date, to_date):
    '''
        Given a site get the url used for scraping
    '''
    if website == 'ONS':
        return get_ons_url(from_date, to_date, 1)
    elif website == 'GSS':
        return get_gss_url(1)
    elif website == 'gov.scot':
        return get_scot_url()

def post_scraping_error(slack_client, slack_channel, website, e):
    post_error_to_slack(slack_client, slack_channel, f"{website} scraping failed: {e}")

def post_no_data_warning(slack_client, slack_channel, website, url):
    '''
        Post an appropriate error message to slack with a link to scraped website to verify
    '''
    message = f"No data for {website} in date range."
    message += f" <{url}|Go to {website}> to verify this"
    post_warning_to_slack(slack_client, slack_channel, message)