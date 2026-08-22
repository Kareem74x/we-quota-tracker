import sys
import logging
from db import insert_record
from api_client import fetch_quota_data
from utils import check_internet_connection
from quota import calculate_quota
from notifier import send_telegram

logging.basicConfig(level=logging.INFO)


def main():
    check_internet_connection()

    auth, result = fetch_quota_data()

    if auth is None:
        logging.error(result)
        sys.exit(1)

    q = calculate_quota(result)

    # Write to DB after successful fetch
    db_success, dailyUsage = insert_record(
        q["current_day"],
        q["remain_gb"],
        q["overall_state"],
        q["overall_state_gbs"],
        q["state_days"],
        q["remaining_days"]
    )

    if db_success:
        telegram_sent = send_telegram(
            f"*Quota Report — Day {q['current_day']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*Usage Today:* {dailyUsage:.1f} GB\n"
            f"*Remaining:* {q['remain_gb']:.1f} / {q['total_gb']} GB\n"
            f"*Overall State:* {q['overall_state']} by {q['overall_state_gbs']:.1f} GB ({q['state_days']:.1f} days)\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        if not telegram_sent:
            logging.info("─── Quota Record Saved ───────────────────")
            logging.info("  Day            : %d", q["current_day"])
            logging.info("  Usage Today    : %.1f GB", dailyUsage)
            logging.info("  Remaining      : %.1f / %s GB", q["remain_gb"], q["total_gb"])
            logging.info("  Overall State  : %s by %.1f GB (%.1f days)", q["overall_state"], q["overall_state_gbs"], q["state_days"])
            logging.info("──────────────────────────────────────────")
    else:
        logging.error("Couldn't add record to database. Please check your DB connection and try again.")


if __name__ == "__main__":
    main()