import requests
from lxml import etree
import pandas as pd
import numpy as np
import re

def scrape_gss_page(page_url):
    '''
        Takes url for a page of datasets on gov website and scrapes info for each data set
        
        Returns: a list of tuples, one for each data set containing:  
            (title, date_time, org, official, synopsis, link)
    '''
    
    page = requests.get(page_url)
    
    # Page with list of data set links
    html = etree.HTML(page.content)

    # Get list of divs containing the data information
    list_items = html.xpath("//div[@class='finder-results js-finder-results']//li[@class='gem-c-document-list__item  ']")

    # To hold list off tuples one for each dataset
    data_info = []
    
    for item in list_items:

        # Take first el which is the title
        title = item[0].text
        
        # Link to data 
        link = "https://www.gov.uk" + item[0].attrib['href']

        # Synopisis of data
        synopsis = item[1].text
        # Doc type: Official/national etc
        official =  org = item[2][0].text.replace("Document type:", "").strip()

        # Get organisation
        org = item[2][1].text.replace("Organisation:", "").strip()

        # Take the date convert to datetime
        date_string = item[2][2].text.replace("Release date:", "").strip()
        try:
            date = pd.to_datetime(re.findall("^[0-9]{0,4} [A-Za-z]+ 20[0-9]{2}", date_string)[0], errors='coerce')
        except:
            date = pd.NaT
        
        # Ignore Ons data on gov site, we scrape that directly from ons website
        if org.lower() != "office for national statistics":
            data_info.append((title, date, org, official, synopsis, link))
        
    return data_info


def get_gss_data(from_date, to_date):
    '''
        Go through each page of upcoming releases and scrape info for each release. Keep
        going until the to_date is exceeded (or 50 pages have been scraped). 
        Then filter on the from and to dates.
    '''
    all_gss_data = []

    for page_num in range(1, 50):
        url = get_gss_url(page_num)
        page_info = scrape_gss_page(url)
        all_gss_data = all_gss_data + page_info
        
        last_date_on_page = page_info[-1][1]
        # Loop until dates exceed the to_date then stop scraping
        if not pd.isnull(last_date_on_page):
            if last_date_on_page > to_date:
                break

    gss_df = pd.DataFrame(all_gss_data, columns=["release", "date", "provider", "official", "synopsis", "link"])

    # Only get between times specified dates
    gss_df = gss_df[(gss_df['date'] >= from_date) & (gss_df['date'] < to_date)]
    
    gss_df['official'] = gss_df['official'].str.replace(" Statistics", "").str.strip()
    # Add day column
    gss_df.insert(2, 'day', gss_df['date'].dt.strftime("%a"))
    # gss_df.insert(6, 'missing_date', gss_df['date'].isna())
    
    return gss_df


def get_gss_url(page_num):
    return "https://www.gov.uk/search/research-and-statistics?" + \
                            "content_store_document_type=upcoming_statistics&order=updated-newest" + \
                            "&page=" + str(page_num)

# For testing just this file
# import datetime
# from_date = datetime.datetime.strptime("2020-02-01", "%Y-%m-%d")
# to_date = datetime.datetime.strptime("2020-02-15", "%Y-%m-%d")
# get_gss_data(from_date, to_date, 8)
