from app.career_tools import router


def test_career_routes_are_registered():
    paths = {route.path for route in router.routes}
    assert "/tailor-resume" in paths
    assert "/interview-prep" in paths
    assert "/applications/outcomes" in paths
    assert "/applications/{application_id}/outcome" in paths
