from django.db import transaction
from rest_framework import serializers

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


class StationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Station
        fields = ("id", "name", "latitude", "longitude")


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ("id", "source", "destination", "distance")

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        if attrs.get("source") and attrs.get("source") == attrs.get(
            "destination"
        ):
            raise serializers.ValidationError(
                {"destination": "Destination must differ from source."}
            )
        return data


class RouteListSerializer(RouteSerializer):
    source = serializers.SlugRelatedField(read_only=True, slug_field="name")
    destination = serializers.SlugRelatedField(
        read_only=True, slug_field="name"
    )


class RouteDetailSerializer(RouteSerializer):
    source = StationSerializer(read_only=True)
    destination = StationSerializer(read_only=True)


class TrainTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainType
        fields = ("id", "name")


class TrainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Train
        fields = (
            "id",
            "name",
            "cargo_num",
            "places_in_cargo",
            "capacity",
            "train_type",
        )


class TrainListSerializer(TrainSerializer):
    train_type = serializers.SlugRelatedField(
        read_only=True, slug_field="name"
    )


class TrainDetailSerializer(TrainSerializer):
    train_type = TrainTypeSerializer(read_only=True)


class CrewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Crew
        fields = ("id", "first_name", "last_name", "full_name")


class JourneySerializer(serializers.ModelSerializer):
    class Meta:
        model = Journey
        fields = (
            "id",
            "route",
            "train",
            "departure_time",
            "arrival_time",
            "crew",
        )

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        departure = attrs.get(
            "departure_time", getattr(self.instance, "departure_time", None)
        )
        arrival = attrs.get(
            "arrival_time", getattr(self.instance, "arrival_time", None)
        )
        if departure and arrival and arrival <= departure:
            raise serializers.ValidationError(
                {"arrival_time": "Arrival must be after departure."}
            )
        return data


class JourneyListSerializer(serializers.ModelSerializer):
    route = serializers.StringRelatedField(read_only=True)
    train_name = serializers.CharField(source="train.name", read_only=True)
    train_type = serializers.CharField(
        source="train.train_type.name", read_only=True
    )
    train_capacity = serializers.IntegerField(
        source="train.capacity", read_only=True
    )
    tickets_available = serializers.IntegerField(read_only=True)
    crew = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="full_name"
    )

    class Meta:
        model = Journey
        fields = (
            "id",
            "route",
            "departure_time",
            "arrival_time",
            "train_name",
            "train_type",
            "train_capacity",
            "tickets_available",
            "crew",
        )


class TicketSeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("cargo", "seat")


class JourneyDetailSerializer(JourneySerializer):
    route = RouteDetailSerializer(read_only=True)
    train = TrainListSerializer(read_only=True)
    crew = CrewSerializer(many=True, read_only=True)
    taken_places = TicketSeatSerializer(
        source="tickets", many=True, read_only=True
    )

    class Meta:
        model = Journey
        fields = (
            "id",
            "route",
            "train",
            "departure_time",
            "arrival_time",
            "crew",
            "taken_places",
        )


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("id", "cargo", "seat", "journey")

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        Ticket.validate_ticket(
            attrs["cargo"],
            attrs["seat"],
            attrs["journey"].train,
            serializers.ValidationError,
        )
        return data


class JourneyShortSerializer(serializers.ModelSerializer):
    route = serializers.StringRelatedField(read_only=True)
    train_name = serializers.CharField(source="train.name", read_only=True)

    class Meta:
        model = Journey
        fields = (
            "id",
            "route",
            "train_name",
            "departure_time",
            "arrival_time",
        )


class TicketListSerializer(TicketSerializer):
    journey = JourneyShortSerializer(read_only=True)


class OrderSerializer(serializers.ModelSerializer):
    tickets = TicketSerializer(many=True, read_only=False, allow_empty=False)

    class Meta:
        model = Order
        fields = ("id", "tickets", "created_at")

    def create(self, validated_data: dict) -> Order:
        with transaction.atomic():
            tickets_data = validated_data.pop("tickets")
            order = Order.objects.create(**validated_data)
            for ticket_data in tickets_data:
                Ticket.objects.create(order=order, **ticket_data)
            return order


class OrderListSerializer(OrderSerializer):
    tickets = TicketListSerializer(many=True, read_only=True)
