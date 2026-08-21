import logging
import requests
from playwright.sync_api import sync_playwright
from config import LND_NUMBER, LND_PASS, ACCT_ID


LOGIN_URL = "https://my.te.eg/echannel/#/"

captured = {}


def _build_headers(csrf_token):
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Origin": "https://my.te.eg",
        "Referer": "https://my.te.eg/echannel/",
        "channelId": "702",
        "csrftoken": csrf_token,
        "delegatorSubsId": "",
        "isCoporate": "false",
        "isMobile": "false",
        "isSelfcare": "true",
        "languageCode": "en-US",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    }


def _handle_response(response):
    if "userAuthenticate" not in response.url:
        return
    try:
        data = response.json()
    except Exception:
        return
    ret_code = data.get("header", {}).get("retCode")
    if ret_code == "0":
        captured["auth"] = data.get("body", {})
    else:
        captured["auth_error"] = data.get("header", {})
        logging.error("Auth failed: %s", captured["auth_error"])


def _select_service_type(page):
    try:
        selector = page.locator(".ant-select-selector").first
        selector.wait_for(state="visible", timeout=5000)
        selector.click()
        page.wait_for_timeout(800)

        for label in ["Internet", "FBB", "Landline Internet", "ADSL", "Fiber"]:
            option = page.locator(".ant-select-item-option").filter(has_text=label)
            if option.count() > 0 and option.first.is_visible():
                option.first.click()
                return

        options = page.locator(".ant-select-item-option")
        if options.count() > 0:
            options.first.click()
        else:
            logging.warning("No Service Type options found")
    except Exception as e:
        logging.warning("Service Type selection failed: %s", e)


def _do_auth_via_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.on("response", _handle_response)

        logging.info("Logging in...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)

        page.wait_for_selector(
            "input[placeholder='Service number']",
            state="visible",
            timeout=20000,
        )
        page.wait_for_timeout(1000)

        number_input = page.locator("input[placeholder='Service number']")
        number_input.click()
        number_input.fill(LND_NUMBER)

        page.wait_for_timeout(1200)
        _select_service_type(page)
        page.wait_for_timeout(500)

        page.wait_for_selector(
            "input[placeholder='Password']",
            state="visible",
            timeout=10000,
        )
        password_input = page.locator("input[placeholder='Password']")
        password_input.click()
        password_input.fill(LND_PASS)
        page.wait_for_timeout(500)

        login_button = page.get_by_role("button", name="Login")
        login_button.click()

        deadline = 20000
        interval = 300
        elapsed = 0
        while "auth" not in captured and "auth_error" not in captured and elapsed < deadline:
            page.wait_for_timeout(interval)
            elapsed += interval

        cookies_dict = {c["name"]: c["value"] for c in context.cookies()}

        browser.close()

    return cookies_dict


def get_offers(session, token):
    url = "https://my.te.eg/echannel/service/besapp/base/rest/busiservice/cz/v1/auth/getSubscribedOfferings"
    headers = _build_headers(token)
    payload = {
        "msisdn": ACCT_ID,
        "numberServiceType": "FBB",
        "groupId": "",
    }

    resp = session.post(url, headers=headers, json=payload)
    data = resp.json()

    if data["header"]["retCode"] != "0":
        return None

    return data["body"]["offeringList"][0]["mainOfferingId"]


def get_quota(session, token, subscriber_id, offer_id):
    url = "https://my.te.eg/echannel/service/besapp/base/rest/busiservice/cz/cbs/bb/queryFreeUnit"
    headers = _build_headers(token)
    payload = {
        "subscriberId": subscriber_id,
        "mainOfferId": offer_id,
    }

    resp = session.post(url, headers=headers, json=payload)
    data = resp.json()

    if data["header"]["retCode"] != "0" or len(data["body"]) == 0:
        return None

    logging.info("Quota data fetched successfully.")
    return data["body"][0]


def fetch_quota_data():
    global captured
    captured = {}

    cookies_dict = _do_auth_via_browser()

    if "auth_error" in captured:
        return None, "Authentication failed. Please check your credentials."

    if "auth" not in captured:
        return None, "No auth response captured within timeout."

    auth_body = captured["auth"]
    token = auth_body["token"]
    subscriber_id = auth_body["subscriber"]["subscriberId"]

    with requests.Session() as session:
        session.cookies.update(cookies_dict)

        offer_id = get_offers(session, token)
        if offer_id is None:
            return None, "Failed to get subscription offerings."

        quota = get_quota(session, token, subscriber_id, offer_id)
        if quota is None:
            return None, "Failed to retrieve quota details."

        return auth_body, quota
