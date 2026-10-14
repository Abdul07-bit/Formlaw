"""
Every request's database transaction must commit *before* the response is sent. Since FastAPI 0.118, a yield dependency
with the default ("request") scope is torn down after the response, so a client could receive "201 Created" for a write
that later failed to commit, or read stale data on its next request. get_db must therefore be function-scoped everywhere.
"""
from __future__ import annotations

from fastapi.routing import APIRoute

from app.db.session import get_db
from app.main import create_app


def _api_routes(routes):
    """Flatten included routers (newer FastAPI wraps them instead of copying their routes)."""
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
            continue
        target = getattr(r, "original_router", r)
        yield from _api_routes(getattr(target, "routes", None) or [])


def _db_dependants(dependant):
    for d in dependant.dependencies:
        if d.call is get_db:
            yield d
        yield from _db_dependants(d)


def test_every_route_commits_before_responding():
    routes = list(_api_routes(create_app().routes))
    found = [(r.path, d.scope) for r in routes for d in _db_dependants(r.dependant)]
    assert len(routes) > 50 and len(found) > 50, "the route walk is not seeing the application's routes"
    late = sorted({path for path, scope in found if scope != "function"})
    assert not late, f"get_db not function-scoped on: {late}"


def test_write_is_visible_to_the_immediately_following_request(api):
    s = api.register("client")
    r = api.c.post("/api/v1/intakes", headers=s.h, json={"title": "Immediate read-back", "description": "A synthetic description long enough to pass validation."})
    assert r.status_code == 201
    assert api.c.get(f"/api/v1/intakes/{r.json()['id']}", headers=s.h).status_code == 200
