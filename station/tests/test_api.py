from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from station.models import (
    Crew,
    Journey,
    Order,
    Route,
    Station,
    Ticket,
    Train,
    TrainType,
)

JOURNEY_URL = reverse("station:journey-list")
ORDER_URL = reverse("station:order-list")
ROUTE_URL = reverse("station:route-list")


def journey_detail_url(journey_id: int) -> str:
    return reverse("station:journey-detail", args=[journey_id])


class BaseStationTest(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.addCleanup(cache.clear)
        self.client = APIClient()
        self.kyiv = Station.objects.create(
            name="Kyiv", latitude=50.45, longitude=30.52
        )
        self.lviv = Station.objects.create(
            name="Lviv", latitude=49.84, longitude=24.03
        )
        self.odesa = Station.objects.create(
            name="Odesa", latitude=46.48, longitude=30.72
        )
        self.kyiv_lviv = Route.objects.create(
            source=self.kyiv, destination=self.lviv, distance=540
        )
        self.kyiv_odesa = Route.objects.create(
            source=self.kyiv, destination=self.odesa, distance=475
        )
        self.intercity = TrainType.objects.create(name="Intercity")
        self.train = Train.objects.create(
            name="IC 743",
            cargo_num=2,
            places_in_cargo=10,
            train_type=self.intercity,
        )
        self.driver = Crew.objects.create(first_name="Ivan", last_name="Koval")
        departure = timezone.now() + timedelta(days=1)
        self.journey = Journey.objects.create(
            route=self.kyiv_lviv,
            train=self.train,
            departure_time=departure,
            arrival_time=departure + timedelta(hours=5),
        )
        self.journey.crew.add(self.driver)
        self.other_journey = Journey.objects.create(
            route=self.kyiv_odesa,
            train=self.train,
            departure_time=departure + timedelta(days=2),
            arrival_time=departure + timedelta(days=2, hours=6),
        )


class ModelValidationTests(BaseStationTest):
    def test_route_source_must_differ_from_destination(self) -> None:
        route = Route(source=self.kyiv, destination=self.kyiv, distance=1)

        with self.assertRaises(ValidationError):
            route.full_clean()

    def test_journey_arrival_must_be_after_departure(self) -> None:
        journey = Journey(
            route=self.kyiv_lviv,
            train=self.train,
            departure_time=self.journey.arrival_time,
            arrival_time=self.journey.departure_time,
        )

        with self.assertRaises(ValidationError):
            journey.full_clean()

    def test_ticket_seat_out_of_train_range(self) -> None:
        user = get_user_model().objects.create_user("a@a.com", "pass12345")
        order = Order.objects.create(user=user)

        with self.assertRaises(ValidationError):
            Ticket.objects.create(
                cargo=1, seat=11, journey=self.journey, order=order
            )

    def test_train_capacity(self) -> None:
        self.assertEqual(self.train.capacity, 20)


class UnauthenticatedApiTests(BaseStationTest):
    def test_auth_required(self) -> None:
        for url in (JOURNEY_URL, ORDER_URL, ROUTE_URL):
            res = self.client.get(url)
            self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedApiTests(BaseStationTest):
    def setUp(self) -> None:
        super().setUp()
        self.user = get_user_model().objects.create_user(
            "user@railway.com", "password123"
        )
        self.client.force_authenticate(self.user)

    def test_list_journeys_shows_tickets_available(self) -> None:
        order = Order.objects.create(user=self.user)
        Ticket.objects.create(
            cargo=1, seat=1, journey=self.journey, order=order
        )

        res = self.client.get(JOURNEY_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = {journey["id"]: journey for journey in res.data}
        self.assertEqual(data[self.journey.id]["tickets_available"], 19)
        self.assertEqual(data[self.journey.id]["crew"], ["Ivan Koval"])
        self.assertEqual(data[self.journey.id]["route"], "Kyiv - Lviv")

    def test_filter_journeys_by_destination(self) -> None:
        res = self.client.get(JOURNEY_URL, {"destination": "odes"})

        self.assertEqual([j["id"] for j in res.data], [self.other_journey.id])

    def test_filter_journeys_by_date(self) -> None:
        date = self.journey.departure_time.date().isoformat()

        res = self.client.get(JOURNEY_URL, {"date": date})

        self.assertEqual([j["id"] for j in res.data], [self.journey.id])

    def test_filter_routes_by_source_and_destination(self) -> None:
        res = self.client.get(
            ROUTE_URL, {"source": "kyiv", "destination": "lviv"}
        )

        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["destination"], "Lviv")

    def test_journey_detail_shows_taken_places(self) -> None:
        order = Order.objects.create(user=self.user)
        Ticket.objects.create(
            cargo=2, seat=7, journey=self.journey, order=order
        )

        res = self.client.get(journey_detail_url(self.journey.id))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["taken_places"], [{"cargo": 2, "seat": 7}])
        self.assertEqual(res.data["route"]["source"]["name"], "Kyiv")

    def test_create_journey_forbidden(self) -> None:
        res = self.client.post(JOURNEY_URL, {})

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_order_with_tickets(self) -> None:
        payload = {
            "tickets": [
                {"cargo": 1, "seat": 1, "journey": self.journey.id},
                {"cargo": 1, "seat": 2, "journey": self.journey.id},
            ]
        }

        res = self.client.post(ORDER_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(id=res.data["id"])
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.tickets.count(), 2)

    def test_create_order_with_wrong_seat_returns_400(self) -> None:
        payload = {
            "tickets": [{"cargo": 3, "seat": 1, "journey": self.journey.id}]
        }

        res = self.client.post(ORDER_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)

    def test_create_order_with_taken_seat_returns_400(self) -> None:
        order = Order.objects.create(user=self.user)
        Ticket.objects.create(
            cargo=1, seat=1, journey=self.journey, order=order
        )
        payload = {
            "tickets": [{"cargo": 1, "seat": 1, "journey": self.journey.id}]
        }

        res = self.client.post(ORDER_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_empty_order_returns_400(self) -> None:
        res = self.client.post(ORDER_URL, {"tickets": []}, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_orders_list_only_own_and_paginated(self) -> None:
        other = get_user_model().objects.create_user("o@o.com", "pass12345")
        Order.objects.create(user=other)
        own = Order.objects.create(user=self.user)

        res = self.client.get(ORDER_URL)

        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["id"], own.id)


class AdminApiTests(BaseStationTest):
    def setUp(self) -> None:
        super().setUp()
        self.admin = get_user_model().objects.create_superuser(
            "admin@railway.com", "password123"
        )
        self.client.force_authenticate(self.admin)

    def test_create_journey(self) -> None:
        departure = timezone.now() + timedelta(days=5)
        payload = {
            "route": self.kyiv_odesa.id,
            "train": self.train.id,
            "departure_time": departure.isoformat(),
            "arrival_time": (departure + timedelta(hours=7)).isoformat(),
            "crew": [self.driver.id],
        }

        res = self.client.post(JOURNEY_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        journey = Journey.objects.get(id=res.data["id"])
        self.assertEqual(list(journey.crew.all()), [self.driver])

    def test_create_journey_with_wrong_times_returns_400(self) -> None:
        departure = timezone.now() + timedelta(days=5)
        payload = {
            "route": self.kyiv_odesa.id,
            "train": self.train.id,
            "departure_time": departure.isoformat(),
            "arrival_time": (departure - timedelta(hours=1)).isoformat(),
        }

        res = self.client.post(JOURNEY_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_route_with_same_stations_returns_400(self) -> None:
        payload = {
            "source": self.lviv.id,
            "destination": self.lviv.id,
            "distance": 10,
        }

        res = self.client.post(ROUTE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
