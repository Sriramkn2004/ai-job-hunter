from app.screening import extract_salary


def test_india_lpa():
    assert extract_salary("Salary: 15-20 LPA", "India") == (
        1500000, 2000000, "INR", "year"
    )


def test_india_monthly_salary():
    assert extract_salary("Salary: INR 150,000 per month", "India") == (
        1800000, 1800000, "INR", "year"
    )


def test_usa_annual_salary():
    assert extract_salary("Salary: USD 50,000 per year", "USA") == (
        50000, 50000, "USD", "year"
    )


def test_experience_range_is_not_salary():
    assert extract_salary("Requires 3-5 years of experience", "India") is None


def test_missing_salary():
    assert extract_salary("Python Developer, Bangalore", "India") is None
