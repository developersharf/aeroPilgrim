from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q, F


class Search(models.Model):

    CITY_CHOICES = (
        ("JED", "Jeddah"),
        ("MED", "Medina"),
        ("DAC", "Dhaka"),
        ("CGP", "Chattogram"),
        ("ZYL", "Sylhet"),
    )

    DAYS_CHOICES = (
        (7, "7 Days"),
        (10, "10 Days"),
        (15, "15 Days"),
        (20, "20 Days"),
        (30, "30 Days"),
    )

    TIMESPAN_CHOICES = (
        (7, "7 Days"),
        (30, "30 Days"),
        (90, "3 Months"),
        (180, "6 Months"),
        (365, "1 Year"),
    )

    city_departure = models.CharField(max_length=3, choices=CITY_CHOICES, default='DAC')
    city_arrival = models.CharField(max_length=3, choices=CITY_CHOICES, default='JED')

    stay_days = models.IntegerField(choices=DAYS_CHOICES, default=7)
    timespan_to_search = models.IntegerField(choices=TIMESPAN_CHOICES, default=30)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.city_departure == self.city_arrival:
            raise ValidationError("Departure and arrival cities cannot be the same")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(city_departure=F('city_arrival')),
                name='city_departure_not_city_arrival'
            )
        ]