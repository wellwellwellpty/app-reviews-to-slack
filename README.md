# Android and Apple Reviews to Slack
Run on a scheduler, get your latest Apple & Android reviews, and post to Slack. Cute!

# Notes
Android requires a little effort to set up (you need to be the Application Owner in the Play Store); Apple reviews are publicly available as a RSS feed.

**NOTE:** Apple RSS feeds return the most recent 50 reviews; and Android Reply to Reviews API returns most recent 100. So if you expect more than those in any time; then adjust your frequency shorter (also good luck reading all of those, you popular). 

**WARNING:** This is pretty naive just checking for reviews in the "last x minutes"; if a review is on the edge of a schedule or the scheduler takes longer to run than usual you might miss a review. You could be smarter and store the reviews in a DB/cache, and check for the last review you processed instead of the last time. 

# Setting up Android Service Account
You need be be the Owner of the Application in the Play Store to do this; and have a Google Cloud project linked to your application (you probably already have this). 

1. Log into the Play Console
1. Visit `Setup > API` access
1. Click `View Project` (takes you to GCP Console)
    * `Hamburger > IAM > Service Accounts`
    * Create Service Account
    * Grant access to `Basic > Viewer`
    * Click `Done`
    * Generate `json` key; download and save for later
1. Back to `Play Console > API access`
    * Click `Refresh service accounts`
    * Click `Grant access` on your new Service account
    * Grant the `Reply to reviews` permission and Save 
1. Back to `Play Console > API access`
    * Click `View access`
    * Under App permissions grant access to which ever apps you need
1. Done!


# Configuration
All configuration is done via environment variables. Use `env.yaml` or whatever floats your boat.

## Required
| Variable | Description | Example | 
| -- | -- | -- | 
| ANDROID_APP_PACKAGE_NAME | Android package name | `com.google.android.gm` |
| APPLE_APP_ID | Apple App ID; find in URL when browsing AppStore; [example](https://apps.apple.com/us/app/gmail-email-by-google/id422689480) | `422689480` | 
| SLACK_WEBHOOK | Slack webhook URL. Use a slack bot. | `https://hooks.slack.com/services/RANDOM/RANDOM/RANDOM` | 
| CLOUD_FUNCTION_SECRET_KEY | Some random garbage from your password manager | `somerandomgarbagefromyourpasswordmanager` |


## Optional
| Variable | Description | Default | 
| -- | -- | -- |
| TIMEZONE | Timezone to match something that makes sense to you | `Africa/Johannesburg` | 
| RUN_FREQUENCY_MINUTES | How frequent the cronjob is configured to run | `60` |
| CREDENTIAL_FILE | The Service Account key | `play_credentials.json` |

### Finding your timezone string
You know where you live, but if you don't:
```python
# pip install tzdata
import zoneinfo
print(zoneinfo.available_timezones())
```

# Production
This is how I run this in production. It's cheap (more than likely will be free). Make sure you've selected and configured the right project...

## Cloud Functions
[Google Cloud Functions](https://console.cloud.google.com/functions/list)

The first time you run these you'll get some errors; but the output will help you set up the right GCP APIs; Cloud Functions & Cloud Build API.

```bash
gcloud config set project acme-mobile

gcloud functions deploy http_apple_reviews \
    --runtime python37 \
    --trigger-http \
    --env-vars-file env.yaml

gcloud functions deploy http_android_reviews \
    --runtime python37 \
    --trigger-http \
    --env-vars-file env.yaml
```

On first deployment it'll warn you of "unauthenticated" requests; you'll want to allow those, you're 'protecting' the endpoint using a *secret* key. Take note of the `url` returned on the `gcloud functions deploy` command; you'll need that later.

## Cloud Scheduler
[Google Cloud Scheduler](https://console.cloud.google.com/cloudscheduler)

Create two jobs
* `http_android_reviews`
* `http_apple_reviews`

**Execution** Select `HTTP`. Take the output `url` from `gcloud function deploy`; but also append the `?key=<CLOUD_FUNCTION_SECRET_KEY>` parameter. Use `GET` HTTP method. 

The full url's will look something like:
```
https://<region>-<project>.cloudfunctions.net/http_android_review?key=<CLOUD_FUNCTION_SECRET_KEY>

https://<region>-<project>.cloudfunctions.net/http_apple_review?key=<CLOUD_FUNCTION_SECRET_KEY>
```

**Frequency** This *MUST* match what you configured in `RUN_FREQUENCY_MINUTES`. Use [crontab.guru](https://crontab.guru/) to work it out. Use the same time zone you configured above (not critical).

Examples below; probably doesn't need to be too often though (YMMV). 

| RUN_FREQUENCY_MINUTES | Schedule | Explainer | 
| -- | -- | -- | 
| 30 | `23,53 * * * *` | `“At minute 23 and 53.”` | 
| 60 | `23 * * * *` | `“At minute 23.”` | 
| 120 | `23 */2 * * *` | `“At minute 23 past every 2nd hour.”` | 


# Local dev
```bash
# Environment & requirements
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment variables
export ANDROID_APP_PACKAGE_NAME="com.google.android.gm"
export APPLE_APP_ID="422689480"
export SLACK_WEBHOOK="https://hooks.slack.com/services/RANDOM/RANDOM/RANDOM"
export CLOUD_FUNCTION_SECRET_KEY="somerandomgarbagefromyourpasswordmanager"

# Update the __main__ function to do whatever you want
python main.py
```
