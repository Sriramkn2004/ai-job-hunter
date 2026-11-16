from app.career_tools import router


def test_career_routes_are_registered():
    paths = {route.path for route in router.routes}
    assert "/api/v1/career/tailor-resume" in paths
    assert "/api/v1/career/interview-prep" in paths
    assert "/api/v1/career/applications/outcomes" in paths
    assert "/api/v1/career/applications/{application_id}/outcome" in paths
