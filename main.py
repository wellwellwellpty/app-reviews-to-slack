import os
import logging
from datetime import datetime, timedelta

import requests
import feedparser
from pytz import timezone

from googleapiclient import discovery
from google.oauth2 import service_account

# Environment (Required)
try:
    ANDROID_APP_PACKAGE_NAME = os.environ['ANDROID_APP_PACKAGE_NAME']
    APPLE_APP_ID = os.environ['APPLE_APP_ID']
    SLACK_WEBHOOK = os.environ['SLACK_WEBHOOK']
    CLOUD_FUNCTION_SECRET_KEY = os.environ['CLOUD_FUNCTION_SECRET_KEY']
except KeyError:
    logging.exception('Missing required environment variable(s)')
    raise

# Environment (Optional)
TIMEZONE = timezone(os.environ.get('TIMEZONE', 'Africa/Johannesburg'))
RUN_FREQUENCY_MINUTES = int(os.environ.get('RUN_FREQUENCY_MINUTES', 60))
CREDENTIAL_FILE = os.environ.get('CREDENTIAL_FILE', 'play_credentials.json')
PLAY_DEVELOPER_ID = os.environ.get('PLAY_DEVELOPER_ID', None)
PLAY_APPLICATION_ID = os.environ.get('PLAY_APPLICATION_ID', None)

APPLE_RSS = 'https://itunes.apple.com/za/rss/customerreviews/id={}/sortby=mostrecent/xml'.format(APPLE_APP_ID)

SCOPES = ['https://www.googleapis.com/auth/androidpublisher']
credentials = service_account.Credentials.from_service_account_file(CREDENTIAL_FILE, scopes=SCOPES)
service = discovery.build('androidpublisher', 'v3', credentials=credentials, cache_discovery=False)


# HTTP Functions Entrypoints
def http_apple_reviews(request):
    if request.args.get('key') != CLOUD_FUNCTION_SECRET_KEY:
        logging.warning('bad secret key, haxxors')
        return 'fail', 401
    
    apple_reviews()
    return 'success', 200

def http_android_reviews(request):
    if request.args.get('key') != CLOUD_FUNCTION_SECRET_KEY:
        logging.warning('bad secret key, haxxors')
        return 'fail', 401
    
    android_reviews()
    return 'success', 200


def _get_play_store_review_url(review_id):
    url = f"https://play.google.com/console/u/0/developers/{PLAY_DEVELOPER_ID}/app/{PLAY_APPLICATION_ID}/user-feedback/review-details?reviewId={review_id}&corpus=PUBLIC_REVIEWS"
    return url


def _send_to_slack(data, platform):
    url = SLACK_WEBHOOK

    try:
        message = "*{title}*\n{stars}\n{summary}\n\n_{author}_ *({version})*".format(
            stars=(int(data['rating']) * '★') + ((5 - int(data['rating'])) * '☆'),
            title=data['title'],
            summary=data['summary'],
            author=data['author'],
            version=data['version'],
        )

        date = "{} - {}".format(data['updated'].astimezone(TIMEZONE), platform)

        if platform == 'android' and PLAY_DEVELOPER_ID and PLAY_APPLICATION_ID:
            link = _get_play_store_review_url(data['id'])
            date += f" <{link}|:link:>"

        payload = {
            "text": "{} review: {}/5".format(platform, data['rating']),
            "blocks": [
                {
                    "type": "section",
                    "block_id": "section567",
                    "text": {
                        "type": "mrkdwn",
                        "text": message,
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": date,
                        }
                    ]
                }
            ]
        }
    except Exception:
        logging.exception('failed')
        payload = {
            "text": "{}; {}".format(platform, data),
        }

    result = requests.post(url, json=payload)
    # logging.debug(result.status_code)


def apple_reviews():
    platform = 'apple'

    rss_url = APPLE_RSS
    feed = feedparser.parse(rss_url) 

    if 'entries' not in feed:
        logging.error('bad data in feed; got the right URL?')
        return

    from_time = datetime.now(tz=TIMEZONE) - timedelta(minutes=RUN_FREQUENCY_MINUTES)

    for e in feed['entries']:
        # logging.debug(e)
        doc = {
            'id': e['id'].split('/')[-1:][0],  # Hacks
            'updated': datetime.fromisoformat(e['updated']),
            'author': e['author'].strip(),
            'title': e['title'].strip(),
            'summary': e['summary'].strip(),
            'version': e['im_version'],
            'rating': e['im_rating'],
        }
        
        if doc['updated'] < from_time:
            logging.info('last review not within time window: id={}; updated={}'.format(doc['id'], doc['updated'].astimezone(TIMEZONE)))
            break
        
        logging.info('Review: {}'.format(doc))
        _send_to_slack(doc, platform)
        # break


def android_reviews():
    platform = 'android'

    package_name = ANDROID_APP_PACKAGE_NAME
    result = service.reviews().list(packageName=package_name).execute()

    from_time = datetime.now(tz=TIMEZONE) - timedelta(minutes=RUN_FREQUENCY_MINUTES)

    for r in result['reviews']:
        # logging.debug(r)
        e = r['comments'][0]

        review_id = r['reviewId']
        last_modified = datetime.fromtimestamp(int(e['userComment']['lastModified']['seconds']))
        author = r['authorName']
        manufacturer = e['userComment']['deviceMetadata'].get('manufacturer', 'N/A')
        android_os_version = e['userComment'].get('androidOsVersion', 'N/A')
        summary = e['userComment']['text']
        app_version_name = e['userComment'].get('appVersionName', 'N/A')
        # app_version_code = e['userComment'].get('appVersionCode', 'N/A')
        rating = e['userComment']['starRating']

        doc = {
            'id': review_id,
            'updated': last_modified.astimezone(TIMEZONE),
            'author': author.strip(),
            'title': "{} (Android: {})".format(manufacturer, android_os_version),
            'summary': summary.strip(),
            'version': app_version_name,
            'rating': rating,
        }

        if doc['updated'] < from_time:
            logging.info('last review not within time window: id={}; updated={}'.format(doc['id'], doc['updated'].astimezone(TIMEZONE)))
            break
        
        logging.info('Review: {}'.format(doc))
        _send_to_slack(doc, platform)
        # break


if __name__ == "__main__":
    # apple_reviews()
    # android_reviews()
    logging.warning('nope')
