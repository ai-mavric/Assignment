from django.db import models


class Place(models.Model):
    KIND_PLACE = 'place'
    KIND_COUSUB = 'cousub'

    state = models.CharField(max_length=2)
    name = models.CharField(max_length=128, help_text='Normalized name, see services.normalize')
    display_name = models.CharField(max_length=128)
    kind = models.CharField(max_length=8, choices=[(KIND_PLACE, 'Place'), (KIND_COUSUB, 'County subdivision')])
    lat = models.FloatField()
    lon = models.FloatField()

    class Meta:
        indexes = [models.Index(fields=['state', 'name'])]

    def __str__(self):
        return f'{self.display_name}, {self.state}'


class FuelStation(models.Model):
    opis_id = models.IntegerField(db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=128)
    state = models.CharField(max_length=2)
    rack_id = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=7, decimal_places=4, help_text='Retail price, USD per gallon')
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    geocode_source = models.CharField(max_length=16, blank=True)

    class Meta:
        indexes = [models.Index(fields=['state', 'city'])]

    def __str__(self):
        return f'{self.name} ({self.city}, {self.state}) ${self.price}'
