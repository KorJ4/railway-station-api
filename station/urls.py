from django.urls import include, path
from rest_framework import routers

from station.views import (
    CrewViewSet,
    JourneyViewSet,
    OrderViewSet,
    RouteViewSet,
    StationViewSet,
    TrainTypeViewSet,
    TrainViewSet,
)

router = routers.DefaultRouter()
router.register("stations", StationViewSet)
router.register("routes", RouteViewSet)
router.register("train-types", TrainTypeViewSet)
router.register("trains", TrainViewSet)
router.register("crew", CrewViewSet)
router.register("journeys", JourneyViewSet)
router.register("orders", OrderViewSet)

urlpatterns = [path("", include(router.urls))]

app_name = "station"
