import json
import sys
from datetime import datetime, timedelta, timezone
import os
import requests
from dotenv import load_dotenv
import re
import psycopg2
import psycopg2.extras
import logging



load_dotenv()
logging.basicConfig(level=logging.INFO)

start_gb = int(os.getenv("START_GB"))


def get_db_connection():
    logging.info("Connecting to database...")

    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        logging.info("Connected successfully")
        return conn

    except Exception as e:
        logging.error("Database connection failed. Please check your network and DATABASE_URL in .env")
        return None

def ensure_table_exists(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quota_log (
            id            SERIAL PRIMARY KEY,
            date_time     TIMESTAMP       NOT NULL,
            day           INT,
            usage_gbs     NUMERIC(10, 1),
            remaining_gbs NUMERIC(10, 1),
            overall_state VARCHAR(50),
            state_gbs     NUMERIC(10, 1),
            state_days    NUMERIC(10, 1),
            remaining_days INT
        )
    """)

def write_to_db(now_datetime, currentDay, remainGB, overAllState, overAllStateGbs, stateDays, remainingDays):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # TODO: replace this temporary solution with a more robust method for handling the start of a new cycle
        if currentDay == 1:
            logging.info("First day of the cycle — clearing quota_log table for a fresh start.")
            cursor.execute("DELETE FROM quota_log")
            conn.commit()

        ensure_table_exists(cursor)

        # Get previous remaining GBs to calculate usage
        cursor.execute("SELECT remaining_gbs FROM quota_log ORDER BY id DESC LIMIT 1")
        last_row = cursor.fetchone()
        prev_remain = last_row["remaining_gbs"] if last_row else start_gb
        usage = round(float(prev_remain) - remainGB, 1)
        
        insertion_query = """
            INSERT INTO quota_log
                (date_time, day, usage_gbs, remaining_gbs, overall_state, state_gbs, state_days, remaining_days)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        insertion_values = (
            now_datetime,
            currentDay,
            usage,
            round(remainGB, 1),
            overAllState,
            round(overAllStateGbs, 1),
            round(stateDays, 1),
            remainingDays
        )

        cursor.execute(insertion_query, insertion_values)

        conn.commit()
        cursor.close()
        conn.close()
        return True, usage
    
    except Exception as e:
        logging.error("Failed to write quota record to database.")
        return False, 0 

# Your credentials
lnd_number = os.getenv("LND_NUMBER")
lnd_pass = os.getenv("LND_PASS")

acctId = "FBB" + lnd_number[1:]  # The account ID is the same as the landline number but with "FBB" at the beginning

def tsConv(unix_timestamp, returnUntil=False):
    # Convert UNIX timestamp to timezone-aware datetime object in UTC
    dt_utc = datetime.fromtimestamp(unix_timestamp / 1000.0, tz=timezone.utc)
    
    # Get the local timezone
    local_tz = datetime.now().astimezone().tzinfo
    
    # Convert UTC datetime to local datetime
    dt_local = dt_utc.astimezone(local_tz)
    
    # Format the local datetime in "DD/MM/YYYY at HH:MM AM/PM" format
    formatted_date = dt_local.strftime("%d/%m/%Y at %I:%M %p")

    dates = [formatted_date]
    
    if returnUntil:
        # Calculate the time difference between now and the timestamp date
        now_local = datetime.now().astimezone(local_tz)
        time_difference = dt_local - now_local
        
        if time_difference <= timedelta(days=1):
            hours_left = int(time_difference.total_seconds() // 3600)
            dates.append(f"in {hours_left} hours")
        else:
            days_left = time_difference.days
            dates.append(f"in {days_left} days")
    
    return dates

def check_internet_connection():
    try:
        # Try to make a GET request to a known server
        response = requests.get("https://google.com/", timeout=5)
        if response.status_code == 200:
            print("Internet connection is available.")
    except requests.RequestException as e:
        logging.error("Internet Connection Error — No internet connection available. Exiting...")
        sys.exit(1)

check_internet_connection()



with requests.Session() as session:
    # Step 1: Make an initial request to obtain the cookies
    initial_url = "https://api-my.te.eg/echannel/service/besapp/base/rest/busiservice/v1/common/querySysParams"
    initial_headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Host": "api-my.te.eg",
        "Origin": "https://api-my.te.eg",
        "Pragma": "no-cache",
        "Referer": "https://api-my.te.eg/echannel/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "channelId": "702",
        "csrftoken": "",
        "delegatorSubsId": "",
        "isCoporate": "false",
        "isMobile": "false",
        "isSelfcare": "true",
        "languageCode": "en-US",
        "sec-ch-ua": "\"Google Chrome\";v=\"125\", \"Chromium\";v=\"125\", \"Not.A/Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }

    initial_payload = {}

    # Make the initial request
    initial_response = session.post(initial_url, headers=initial_headers, json=initial_payload)
    initial_response.raise_for_status()  # Ensure the request was successful

    # Step 2: Use the obtained cookies to make the authentication request
    auth_url = "https://api-my.te.eg/echannel/service/besapp/base/rest/busiservice/v1/auth/userAuthenticate"
    auth_headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Host": "api-my.te.eg",
        "Origin": "https://api-my.te.eg",
        "Referer": "https://api-my.te.eg/echannel/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "channelId": "702",
        "csrftoken": "",
        "delegatorSubsId": "",
        "isCoporate": "false",
        "isMobile": "false",
        "isSelfcare": "true",
        "languageCode": "en-US",
        "sec-ch-ua": "\"Google Chrome\";v=\"125\", \"Chromium\";v=\"125\", \"Not.A/Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }

    auth_payload = {
        "acctId": acctId,
        "appLocale": "en-US",
        "password": lnd_pass,
    }

    # Make the authentication request using the same session (which includes the cookies)
    auth_response = session.post(auth_url, headers=auth_headers, json=auth_payload)
    auth_response.raise_for_status()  # Ensure the request was successful
    auth_data = auth_response.json()
    
    if auth_data['header']['retCode'] == "0":
        body = auth_data['body']
        name = body['customer']['custName']
        subID = body['subscriber']['subscriberId']

        get_offers_url = "https://api-my.te.eg/echannel/service/besapp/base/rest/busiservice/cz/v1/auth/getSubscribedOfferings"
        get_offers_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Origin": "https://api-my.te.eg",
            "Referer": "https://api-my.te.eg/echannel/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "channelId": "702",
            "csrftoken": body["token"],
            "delegatorSubsId": "",
            "isCoporate": "false",
            "isMobile": "false",
            "isSelfcare": "true",
            "languageCode": "en-US",
            "sec-ch-ua": "\"Google Chrome\";v=\"125\", \"Chromium\";v=\"125\", \"Not.A/Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\""
        }

        get_offers_payload = {
            "msisdn": acctId,
            "numberServiceType": "FBB",
            "groupId": ""
        }

        # Make the request to get subscribed offerings
        get_offers_response = session.post(get_offers_url, headers=get_offers_headers, json=get_offers_payload)
        get_offers_data = get_offers_response.json()

        if get_offers_data['header']['retCode'] == "0":
            offerID = get_offers_data["body"]["offeringList"][0]["mainOfferingId"]

            quota_details_url = "https://api-my.te.eg/echannel/service/besapp/base/rest/busiservice/cz/cbs/bb/queryFreeUnit"

            quota_details_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Origin": "https://api-my.te.eg",
            "Referer": "https://api-my.te.eg/echannel/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "channelId": "702",
            "csrftoken": body["token"],
            "delegatorSubsId": "",
            "isCoporate": "false",
            "isMobile": "false",
            "isSelfcare": "true",
            "languageCode": "en-US",
            "sec-ch-ua": "\"Google Chrome\";v=\"125\", \"Chromium\";v=\"125\", \"Not.A/Brand\";v=\"24\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\""
        }
            quota_details_payload = {"subscriberId":subID,"mainOfferId":offerID}

            quota_details_response = session.post(quota_details_url, headers=quota_details_headers, json=quota_details_payload)
            quota_details_data = quota_details_response.json()

            if quota_details_data['header']['retCode'] == "0" and len(quota_details_data['body']) > 0:
                qoutaBody = quota_details_data['body'][0]

                offerName = qoutaBody["offerName"]
                totalGB = qoutaBody["total"]
                usedGB = qoutaBody["used"]
                remainGB = qoutaBody["remain"]
                usagePrc = usedGB/totalGB*100
                renewedDate = tsConv(qoutaBody["effectiveTime"])[0]
                expiryDate = tsConv(qoutaBody["expireTime"], returnUntil=True)
                expDate = expiryDate[0]
                daysUntilExp = expiryDate[1]



                oneDayGB = totalGB / 30
                remainingDays = int(re.search(r'\d+', daysUntilExp).group())
                currentDay = 30 - remainingDays

                atLeastRemain = remainingDays * oneDayGB     
                overAllState = "Under" if remainGB >= atLeastRemain else "Over"
                overAllStateGbs = abs(remainGB - atLeastRemain)
                stateDays = overAllStateGbs / oneDayGB


            
                # Write to DB after successful fetch
                now_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_success, dailyUsage = write_to_db(
                    now_datetime, 
                    currentDay, 
                    remainGB, 
                    overAllState, 
                    overAllStateGbs, 
                    stateDays, 
                    remainingDays
                )


                if db_success:
                
                    message = (
                        "Record added successfully!\n"

                        f"Day{currentDay} Usage: {dailyUsage:.1f} GBs \n"

                        f"Remaining Days: {remainingDays}\n"
                        f"{remainGB} / {totalGB} GBs Remaining ({usagePrc:.1f}% Used)\n"
                        f"Overall State: {overAllState} ({overAllStateGbs:.1f} GBs => {stateDays:.1f} Days)\n"
                    )

                    print(message)
                    
                else:
                    logging.error("Couldn't add record to database. Please check your DB connection and try again.")

            else:
                logging.error("Couldn't add record - failed to retrieve quota details.")
        else:
            logging.error("Couldn't add record - failed to get subscription offerings.")
    else:
        logging.error("Authentication Error: Couldn't add record - authentication failed. Please check your credentials.")