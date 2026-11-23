from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Station(models.Model):
    name = models.CharField(max_length=255, unique=True)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Route(models.Model):
    source = models.ForeignKey(
        Station, on_delete=models.CASCADE, related_name="routes_from"
    )
    destination = models.ForeignKey(
        Station, on_delete=models.CASCADE, related_name="routes_to"
    )
    distance = models.PositiveIntegerField(help_text="Distance in km")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "destination"],
                name="unique_route_source_destination",
            ),
            models.CheckConstraint(
                condition=~Q(source=F("destination")),
                name="route_source_not_destination",
            ),
        ]
        ordering = ["source__name", "destination__name"]

    def clean(self) -> None:
        if self.source_id and self.source_id == self.destination_id:
            raise ValidationError(
                {"destination": "Destination must differ from source."}
            )

    def __str__(self) -> str:
        return f"{self.source} - {self.destination}"


class TrainType(models.Model):
    name = models.CharField(max_length=255, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Train(models.Model):
    name = models.CharField(max_length=255)
    cargo_num = models.PositiveIntegerField(help_text="Number of cars")
    places_in_cargo = models.PositiveIntegerField(
        help_text="Seats in one car"
    )
    train_type = models.ForeignKey(
        TrainType, on_delete=models.PROTECT, related_name="trains"
    )

    class Meta:
        ordering = ["name"]

    @property
    def capacity(self) -> int:
        return self.cargo_num * self.places_in_cargo

    def __str__(self) -> str:
        return f"{self.name} ({self.train_type})"


class Crew(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)

    class Meta:
        ordering = ["last_name", "first_name"]

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __str__(self) -> str:
        return self.full_name


class Journey(models.Model):
    route = models.ForeignKey(
        Route, on_delete=models.CASCADE, related_name="journeys"
    )
    train = models.ForeignKey(
        Train, on_delete=models.CASCADE, related_name="journeys"
    )
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    crew = models.ManyToManyField(Crew, related_name="journeys", blank=True)

    class Meta:
        ordering = ["departure_time"]

    def clean(self) -> None:
        if (
            self.departure_time
            and self.arrival_time
            and self.arrival_time <= self.departure_time
        ):
            raise ValidationError(
                {"arrival_time": "Arrival must be after departure."}
            )

    def __str__(self) -> str:
        return f"{self.route} ({self.departure_time:%Y-%m-%d %H:%M})"


class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.pk} ({self.created_at:%Y-%m-%d %H:%M})"


class Ticket(models.Model):
    cargo = models.PositiveIntegerField()
    seat = models.PositiveIntegerField()
    journey = models.ForeignKey(
        Journey, on_delete=models.CASCADE, related_name="tickets"
    )
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="tickets"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["journey", "cargo", "seat"],
                name="unique_ticket_journey_cargo_seat",
            ),
        ]
        ordering = ["cargo", "seat"]

    @staticmethod
    def validate_ticket(
        cargo: int, seat: int, train: Train, error_to_raise: type
    ) -> None:
        for value, field_name, limit_name in [
            (cargo, "cargo", "cargo_num"),
            (seat, "seat", "places_in_cargo"),
        ]:
            limit = getattr(train, limit_name)
            if not (1 <= value <= limit):
                raise error_to_raise(
                    {
                        field_name: f"{field_name} must be in range "
                        f"[1, {limit}], got {value}"
                    }
                )

    def clean(self) -> None:
        Ticket.validate_ticket(
            self.cargo, self.seat, self.journey.train, ValidationError
        )

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.journey} (cargo {self.cargo}, seat {self.seat})"
