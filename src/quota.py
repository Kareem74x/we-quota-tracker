import re
from utils import tsConv
from config import START_GB

def calculate_quota(quota_body: dict) -> dict:
    """Parse raw quota API response and compute derived metrics."""
    offer_name = quota_body["offerName"]
    total_gb = START_GB  # quota_body["total"]
    used_gb = quota_body["used"]
    remain_gb = quota_body["remain"]
    usage_prc = used_gb / total_gb * 100

    renewed_date = tsConv(quota_body["effectiveTime"])[0]
    expiry = tsConv(quota_body["expireTime"], returnUntil=True)
    exp_date = expiry[0]
    days_until_exp = expiry[1]

    one_day_gb = total_gb / 30
    remaining_days = int(re.search(r'\d+', days_until_exp).group())
    current_day = 30 - remaining_days

    at_least_remain = remaining_days * one_day_gb
    overall_state = "Under" if remain_gb >= at_least_remain else "Over"
    overall_state_gbs = abs(remain_gb - at_least_remain)
    state_days = overall_state_gbs / one_day_gb

    return {
        "offer_name": offer_name,
        "total_gb": total_gb,
        "used_gb": used_gb,
        "remain_gb": remain_gb,
        "usage_prc": usage_prc,
        "renewed_date": renewed_date,
        "exp_date": exp_date,
        "days_until_exp": days_until_exp,
        "one_day_gb": one_day_gb,
        "remaining_days": remaining_days,
        "current_day": current_day,
        "overall_state": overall_state,
        "overall_state_gbs": overall_state_gbs,
        "state_days": state_days,
    }
