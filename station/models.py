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
