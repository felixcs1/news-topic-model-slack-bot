import dropbox
from dropbox.exceptions import ApiError
from dropbox.paper import ImportFormat, PaperDocCreateError
import pandas as pd

'''
    Functions for reading and writing to dropbox
'''

def initialise_dropbox_client(dropbox_access_token):
    dbx = dropbox.Dropbox(dropbox_access_token)
    return dbx

def write_dataframe_to_dropbox(dbx, df, path):
    try:
        data_string = df.to_csv(index=False)
        data_bytes = bytes(data_string, 'utf8')
        dbx.files_upload(
            f=data_bytes,
            path=path,
            mode=dropbox.files.WriteMode("overwrite")
        )
    except Exception as e:
        raise Exception(f"Failed to write to dropbox! {e}")
        
def read_from_dropbox(dbx, path):
    try:    
        meta, file = dbx.files_download(path)
        return file
    except Exception as e:
        raise Exception(f"Failed to read from dropbox! {e}")

def get_urls_for_file(dbx, path):
    '''
        Get a sharing link and download link for given file
    '''
    links = dbx.sharing_create_shared_link(path, short_url=False)
    share_link = links.url 
    download_link = share_link.replace("dl=0", "dl=1")
    return share_link, download_link

def write_to_dropbox_paper(dbx, title, content, content_format, folder_id):
    '''
        paper is weird, you cant specify a doc name or path, instead the doc title is just the first line of the doc.
        The 'path' is just the parent folder id which is determined by looking at the url 
        in the folder in paper and taking everything from e.1gg... onwards.

        Return the paper doc id, used to create a link to the file.
    '''
    try:
        data_bytes = bytes(f"{title}\n{content}", 'utf8')
        r = dbx.paper_docs_create(
            f=data_bytes,
            parent_folder_id=folder_id,
            import_format=ImportFormat(content_format))
        return r.doc_id
    except PaperDocCreateError as e:
        print("PaperDocCreateError ERROR %s" % e)
    except ApiError as e:
        print("API ERROR %s" % e)


def get_dropbox_file_meta_data(dbx, path):
    try:
        return dbx.files_get_metadata(path)
    except Exception as e:
        raise Exception(f"Failed to get file/folder metadata from dropbox! {e}")