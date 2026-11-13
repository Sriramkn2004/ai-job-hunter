from app.schemas import Preferences, JobIn, Screening

def evaluate_job(job: JobIn, prefs: Preferences) -> Screening:
    title = job.title.lower()
    description = job.description.lower()
    role_match = any(
        role.lower() in title or role.lower() in description
        for role in prefs.roles
    )
    location_text = f"{job.location} {job.country}".lower()
    location_match = (
        prefs.include_remote and "remote" in location_text
    ) or any(loc.lower() in location_text for loc in prefs.preferred_locations)

    reasons, missing = [], []
    score = 0

    if role_match:
        score += 40
        reasons.append("Role/skills align with configured target roles")
    else:
        reasons.append("No clear target-role match")

    if location_match:
        score += 20
        reasons.append("Location matches preference")
    else:
        reasons.append("Location does not match preference")

    if job.salary_min is None or not job.salary_currency:
        missing.append("Salary is undisclosed or currency is missing")
        reasons.append("Salary cannot be verified")
        salary_ok = False
    elif job.country.lower() == "india" or job.salary_currency.upper() == "INR":
        if job.salary_period == "year":
            salary_lpa = job.salary_min / 100000
        elif job.salary_period == "lpa":
            salary_lpa = job.salary_min
        else:
            missing.append("Salary period is not normalized to annual")
            salary_lpa = 0
        salary_ok = salary_lpa >= prefs.india_min_ctc_lpa
        if salary_ok:
            score += 30
            reasons.append("Published salary meets India minimum")
        else:
            reasons.append("Published salary is below or cannot be verified against India minimum")
    else:
        missing.append("International salary threshold needs country/currency configuration")
        salary_ok = False

    if job.description:
        score += 10
    else:
        missing.append("Job description unavailable")

    if not role_match or not location_match:
        status = "skipped"
    elif not salary_ok:
        status = "review" if prefs.salary_unknown_policy == "review" and job.salary_min is None else "skipped"
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
