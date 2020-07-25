import requests
from lxml import etree
import pandas as pd
from pandas import ExcelFile

def get_scot_gov_data(from_date, to_date):
    '''
        Takes the excel sheet of upcoming publications from gov.scot and standardises 
    '''
    
    page_url = get_scot_url()

    page = requests.get(page_url)

    # Page with list of data set links
    html = etree.HTML(page.content)

    excel_link = "https://www.gov.scot" + html.xpath("//h3[@class='document-info__title']/a")[0].attrib['href']

    scot_data = pd.read_excel(excel_link, skiprows=1)
    scot_data.rename(columns={"Publication Series": "release",
                              "Publication Date": "date",
                              "Synopsis": "synopsis",
                              "Publication Type": "official"}, inplace=True)
    
    scot_data = scot_data[["release", "date", "official", "synopsis"]]
    scot_data['official'] = scot_data['official'].str.replace(" Statistics", "").str.strip()

    # This coerces non specific dates like: Jul-20 to NaT so they are then 
    # filtered out on the next line
    scot_data['date'] = pd.to_datetime(scot_data['date'], errors='coerce')
    scot_data = scot_data[(scot_data['date'] >= from_date) & (scot_data['date'] < to_date)]

    # Add columns 
    scot_data.insert(2, 'day', scot_data['date'].dt.strftime("%a"))    
    scot_data.insert(3, "provider", "Scottish Government")

    # scot_data.insert(6, 'missing_date', scot_data['date'].isna())
    scot_data['link'] = excel_link
    return scot_data


def get_scot_url():
    return "https://www.gov.scot/publications/official-statistics-forthcoming-publications/"

# For testing just this file
# import datetime
# from_date = datetime.datetime.strptime("2020-02-01", "%Y-%m-%d")
# to_date = datetime.datetime.strptime("2020-02-08", "%Y-%m-%d")
# get_scot_gov_data(from_date, to_date)
