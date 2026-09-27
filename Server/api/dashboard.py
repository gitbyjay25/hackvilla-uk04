"""
Dashboard API – thin aggregator.
All endpoint logic lives in the three domain sub-routers:
  • dashboard_overview.py  – /overview, /architecture-map, /services, /health, /dependencies, /bottlenecks
  • dashboard_trends.py    – /trends, /traces/timeline
  • dashboard_insights.py  – /insights, /recommendations, /workflows
"""
from fastapi import APIRouter
from api.dashboard_overview import router as overview_router
from api.dashboard_trends   import router as trends_router
from api.dashboard_insights import router as insights_router
from api.dashboard_projects import router as projects_router

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
router.include_router(overview_router)
router.include_router(trends_router)
router.include_router(insights_router)
router.include_router(projects_router)




