import requests
from lxml import etree
import pandas as pd
import math
import numpy as np
import re

def get_ons_url(from_date, to_date, page, entries=50):
    return "https://www.ons.gov.uk/releasecalendar?query=&fromDateDay=" + \
           str(from_date.day) + "&fromDateMonth=" + str(from_date.month) + \
           "&fromDateYear=" + str(from_date.year) + "&toDateDay=" + str(to_date.day) + \
           "&toDateMonth=" + str(to_date.month) + "&toDateYear=" + str(to_date.year) + \
           "&view=upcoming&size=" + str(entries) + "&page=" + str(page)


def get_ons_synopsis(page_url):
    '''
        Goes to an ons page and returns the synopsis of the data set 
    '''
    data_page = requests.get(page_url)
    html = etree.HTML(data_page.content)
    synopsis = html.xpath("//div[@class='col-wrap']/div/div/section/p/text()")[0]
    return synopsis

def scrape_ons_page(page_url):
    '''
        Goes to a page of a list of ons_df data realeases and gathers data for each upcoming release
        Returns: a list of tuples, one for each data set containing:  
            (title, date_time, org, official, synopsis, link)
    '''
    
    page = requests.get(page_url)
    html = etree.HTML(page.content)
    list_items = html.xpath("//div[@id='results']/div/ul/ul//li")
    
    # To hold list of tuples one for each dataset
    data_info = []

    for item in list_items:
        title = item.xpath("h3/a/text()")[0] 
        link = "https://www.ons.gov.uk" + item.xpath("h3/a")[0].attrib['href']
        
        date_string = item.xpath("p/text()")[0].strip()
        try:
            date = re.findall("^[0-9]{0,4} [A-Za-z]+ 20[0-9]{2}", date_string)[0]
        except:
            date = np.datetime64('NaT')
            
        org = "ONS"
        official = ">=Official"
        synopsis = get_ons_synopsis(link)

        data_info.append((title, date, org, official, synopsis, link))
    
    return data_info

def get_ons_data(from_date , to_date):
    url = get_ons_url(from_date, to_date, 1)

    # First check to see how many pages of results we have
    page = requests.get(url)
    html = etree.HTML(page.content)

    num_results_text = html.xpath("//span[@class='stand-out-text']/text()")
    if len(num_results_text) > 0:
        num_results = int(num_results_text[0])
        num_pages = math.ceil(num_results / 50)
    else:
        num_pages = 0

    all_ons_data = []

    for page_num in range(1, num_pages + 1):
        url = get_ons_url(from_date, to_date, page_num)

        page_info = scrape_ons_page(url)

        all_ons_data = all_ons_data + page_info

    ons_df = pd.DataFrame(all_ons_data, columns=["release", "date", "provider", "official", "synopsis", "link"])

    ons_df['date'] = pd.to_datetime(ons_df['date'], errors='ignore')

    # Remove rows with NaTs 
    ons_df = ons_df[~ons_df['date'].isnull()]

    # Add day column
    ons_df.insert(2, 'day', ons_df['date'].dt.strftime("%a"))
    # ons_df.insert(6, 'missing_date', ons_df['date'].isna())

    return ons_df

# For testing just this file
# import datetime
# from_date = datetime.datetime.strptime("2020-03-01", "%Y-%m-%d")
# to_date = datetime.datetime.strptime("2020-03-06", "%Y-%m-%d")
# get_ons_data(from_date, to_date)