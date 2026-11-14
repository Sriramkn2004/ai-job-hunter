
import re

from app.schemas import Preferences, JobIn, Screening


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def extract_salary(description: str, country: str):
    """
    Return (salary_min, salary_max, currency, period).

    Values are normalized to annual INR or annual USD.
    Maximum-only salaries have salary_min=None.
    Ambiguous or conflicting salary mentions return None.
    """
    text = description or ""
    country = (country or "").strip().lower()
    matches = []

    # Maximum-only LPA formats:
    # Up to 10 LPA, Maximum 12 LPA, Not exceeding 15 LPA.
    max_lpa_pattern = re.compile(
        r"\b(?:up\s+to|maximum|max|not\s+exceeding)"
        r"\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lacs?)\b",
        re.I,
    )

    max_lpa_spans = []

    for match in max_lpa_pattern.finditer(text):
        max_value = _number(match.group(1)) * 100000
        matches.append((None, max_value, "INR"))
        max_lpa_spans.append(match.span())

    # Explicit LPA formats:
    # 15 LPA, 15-20 LPA, 15 to 20 LPA.
    lpa_pattern = re.compile(
        r"(?<![\w.])(\d+(?:\.\d+)?)\s*"
        r"(?:-|to)\s*(\d+(?:\.\d+)?)\s*"
        r"(?:lpa|lakhs?|lacs?)(?!\w)"
        r"|(?<![\w.])(\d+(?:\.\d+)?)\s*"
        r"(?:lpa|lakhs?|lacs?)(?!\w)",
        re.I,
    )

    for match in lpa_pattern.finditer(text):
        # Avoid extracting the same amount again as a fixed salary.
        if any(
            match.start() < end and match.end() > start
            for start, end in max_lpa_spans
        ):
            continue

        if match.group(1):
            low = _number(match.group(1))
            high = _number(match.group(2))
        else:
            low = high = _number(match.group(3))

        matches.append((low * 100000, high * 100000, "INR"))

    # Currency-based salary formats:
    # INR 150,000 per month
    # USD 50,000 per year
    # $40,000 annually
    money_pattern = re.compile(
        r"(?P<currency>₹|INR|USD|\$)\s*"
        r"(?P<low>\d[\d,]*(?:\.\d+)?)"
        r"(?:\s*(?:-|to)\s*(?:₹|INR|USD|\$)?\s*"
        r"(?P<high>\d[\d,]*(?:\.\d+)?))?"
        r"\s*(?P<period>per\s+month|/month|monthly|"
        r"per\s+annum|per\s+year|/year|annually|annual|yearly)",
        re.I,
    )

    for match in money_pattern.finditer(text):
        currency_token = match.group("currency").upper()
        currency = (
            "INR"
            if currency_token in {"₹", "INR"}
            else "USD"
        )

        low = _number(match.group("low"))
        high = (
            _number(match.group("high"))
            if match.group("high")
            else low
        )

        period = match.group("period").lower()

        if "month" in period:
            low *= 12
            high *= 12

        matches.append((low, high, currency))

    if not matches:
        return None

    # Conflicting currencies or salary values are ambiguous.
    currencies = {item[2] for item in matches}

    ranges = {
        (
            item[0],
            round(item[1], 2) if item[1] is not None else None,
        )
        for item in matches
    }

    if len(currencies) != 1 or len(ranges) != 1:
        return None

    low, high, currency = matches[0]

    # Reject salary currencies inconsistent with the job country.
    if country in {"india", "in"} and currency != "INR":
        return None

    if country in {
        "usa",
        "us",
        "united states",
        "united states of america",
    } and currency != "USD":
        return None

    return low, high, currency, "year"


def evaluate_job(job: JobIn, prefs: Preferences) -> Screening:
    title = (job.title or "").lower()
    description = (job.description or "").lower()

    # Role matching.
    role_match = any(
        role.lower() in title or role.lower() in description
        for role in prefs.roles
    )

    # Location matching.
    location_text = (
        f"{job.location or ''} {job.country or ''}"
    ).lower()

    location_match = (
        prefs.include_remote and "remote" in location_text
    ) or any(
        loc.lower() in location_text
        for loc in prefs.preferred_locations
    )

    reasons = []
    missing = []
    score = 0

    if role_match:
        score += 40
        reasons.append(
            "Role/skills align with configured target roles"
        )
    else:
        reasons.append("No clear target-role match")

    if location_match:
        score += 20
        reasons.append("Location matches preference")
    else:
        reasons.append("Location does not match preference")

    # Salary information.
    salary_min = job.salary_min
    salary_max = job.salary_max
    currency = (job.salary_currency or "").upper().strip()
    period = (job.salary_period or "").lower().strip()

    # Extract salary only when structured salary is absent.
    if salary_min is None and salary_max is None:
        extracted = extract_salary(
            job.description,
            job.country,
        )

        if extracted:
            (
                salary_min,
                salary_max,
                currency,
                period,
            ) = extracted

            reasons.append(
                "Salary extracted from job description"
            )

    salary_ok = False
    salary_uncertain = False

    country = (job.country or "").lower().strip()

    is_india = (
        country in {"india", "in"}
        and currency == "INR"
    )

    is_usa = (
        country in {
            "usa",
            "us",
            "united states",
            "united states of america",
        }
        and currency == "USD"
    )

    # Maximum-only salary:
    # We know the upper limit, but not the guaranteed minimum.
    if (
        salary_min is None
        and salary_max is not None
        and currency
    ):
        if is_india and period == "year":
            if (
                salary_max / 100000
                < prefs.india_min_ctc_lpa
            ):
                reasons.append(
                    "Maximum published salary is below India threshold"
                )
            else:
                salary_uncertain = True
                missing.append(
                    "Minimum salary is not disclosed"
                )
                reasons.append(
                    "Maximum-only salary requires manual review"
                )

        elif is_usa and period == "year":
            if (
                salary_max
                < prefs.usa_min_salary_usd_annual
            ):
                reasons.append(
                    "Maximum published salary is below USA threshold"
                )
            else:
                salary_uncertain = True
                missing.append(
                    "Minimum salary is not disclosed"
                )
                reasons.append(
                    "Maximum-only salary requires manual review"
                )

        else:
            salary_uncertain = True
            missing.append(
                "Maximum-only salary requires manual review"
            )

    # Completely missing or invalid salary.
    elif salary_min is None or not currency:
        missing.append(
            "Salary is undisclosed, ambiguous, or currency is missing"
        )
        reasons.append("Salary cannot be verified")
        salary_uncertain = True

    # India salary evaluation.
    elif is_india:
        if period == "year":
            salary_min = salary_min / 100000

            salary_max = (
                salary_max / 100000
                if salary_max is not None
                else salary_min
            )

        elif period == "lpa":
            salary_max = (
                salary_max
                if salary_max is not None
                else salary_min
            )

        else:
            salary_min = salary_max = 0
            missing.append(
                "India salary period is not normalized"
            )
            reasons.append("Salary cannot be verified")
            salary_uncertain = True

        if not salary_uncertain:
            threshold = prefs.india_min_ctc_lpa

            if salary_min >= threshold:
                salary_ok = True
                score += 30
                reasons.append(
                    "Minimum published salary meets India threshold"
                )

            elif salary_max < threshold:
                reasons.append(
                    "Maximum published salary is below India threshold"
                )

            else:
                salary_uncertain = True
                missing.append(
                    "Salary range crosses India minimum threshold"
                )
                reasons.append(
                    "Salary range requires manual review"
                )

    # USA salary evaluation.
    elif is_usa:
        if period != "year":
            missing.append(
                "USA salary must be normalized to annual USD"
            )
            reasons.append(
                "Salary period cannot be verified"
            )
            salary_uncertain = True

        else:
            salary_max = (
                salary_max
                if salary_max is not None
                else salary_min
            )

            threshold = prefs.usa_min_salary_usd_annual

            if salary_min >= threshold:
                salary_ok = True
                score += 30
                reasons.append(
                    "Minimum published salary meets USA threshold"
                )

            elif salary_max < threshold:
                reasons.append(
                    "Maximum published salary is below USA threshold"
                )

            else:
                salary_uncertain = True
                missing.append(
                    "Salary range crosses USA minimum threshold"
                )
                reasons.append(
                    "Salary range requires manual review"
                )

    # Other international markets.
    else:
        missing.append(
            "International salary threshold or currency is not configured"
        )
        reasons.append(
            "International salary requires manual review"
        )
        salary_uncertain = True

    # Description availability.
    if job.description:
        score += 10
    else:
        missing.append("Job description unavailable")

    # Final screening status.
    if not role_match or not location_match:
        status = "skipped"

    elif salary_uncertain:
        status = (
            "review"
            if prefs.salary_unknown_policy == "review"
            else "skipped"
        )

    elif not salary_ok:
        status = "skipped"

    elif score >= prefs.auto_apply_min_score:
        status = "matched"

    else:
        status = "review"

    return Screening(
        status=status,
        score=min(score, 100),
        reasons=reasons,
        missing_information=missing,
    )
