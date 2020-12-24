import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import base64
import email
#from apiclient import errors
#from email.mime.text import MIMEText
import html2text
from datetime import datetime
from pytz import timezone
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import logging

#logging config
logging.basicConfig(format='%(asctime)s:%(levelname)s:%(name)s:%(message)s',filename='mail.log',level=logging.INFO)

#load env
from pathlib import Path  # Python 3.6+ only
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

#GMAIL API Connection Block
def main():
    creds = None
    logging.info('--------------------------------------------------------------------------------------------------------')
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)
    logging.info('Login successfully')
    return service

#Search Email ID BLock
def search_message(service, search_string):
    #Most reacent email ID to be selected 
    search_ids = service.users().messages().list(userId='me', includeSpamTrash=True, maxResults=1, q=search_string).execute()

    if search_ids['resultSizeEstimate'] == 0:
        logging.info('no mail found as per search criteria')
    else:        
        logging.info('filtered Mail Id: {}'.format(search_ids['id']))
        return search_ids['id']
    
#get Email content Block    
def get_message(service, msg):
    try:
        get_ids = service.users().messages().get(userId='me', id=msg, format='full').execute()
        #get email date and convert into date time object
        date_id = get_ids['payload']['headers'][1]['value']
        date_utc = date_id[5:25]
        date_utc = datetime.strptime(date_utc, '%d %b %Y %H:%M:%S')
        #get current time and date and convert into date time object
        now_utc = datetime.now(timezone('UTC'))
        now_utc =  now_utc.strftime("%Y-%m-%d %H:%M:%S")
        now_utc = datetime.strptime(now_utc,"%Y-%m-%d %H:%M:%S")
        #find difference in current and email timestamp and convert into minutes
        td = now_utc - date_utc
        td = td.total_seconds()/60
        #check if mail received within 15 min of the script run and send result to slack function
        if int(td) < 15: # if email received in 15 min from current run time
            message = get_ids['payload']['parts'][1]['body']['data']
            base64_msg = base64.urlsafe_b64decode(message.encode('ASCII'))
            mime_msg = email.message_from_bytes(base64_msg)
            p = mime_msg.get_payload()
            logging.info('mail body: {}'.format(html2text.html2text(p)))
            postslack(html2text.html2text(p))
        else:
            logging.info('Didnt received email Last checked at {}'.format(now_utc))
            postslack("Didnt received email \nLast checked at {}".format(now_utc))
    except Exception as e:
        logging.info('error message: {}'.format(e))

#slack notification block
def postslack(msg):
    client = WebClient(token=os.getenv("SLACK_TOKEN"))
    try:
        logging.info('{} posted in channel'.format(msg))
        response = client.chat_postMessage(channel='#random', text=msg)
        assert response["message"]["text"] == "ok"
    except SlackApiError as e:
        # You will get a SlackApiError if "ok" is False
        assert e.response["ok"] is False
        assert e.response["error"]  # str like 'invalid_auth', 'channel_not_found'
        logging.info("Got an error: {}".format({e.response['error']}))

if __name__ == '__main__':
    service = main()
    s = search_message(service, os.getenv("SEARCH_STRING"))
    get_message(service, s)
    logging.info('--------------------------------------------------------------------------------------------------------')