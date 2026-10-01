from django.contrib import admin

from .models import FuelStation, Place


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = ('opis_id', 'name', 'city', 'state', 'price', 'lat', 'lon', 'geocode_source')
    list_filter = ('state', 'geocode_source')
    search_fields = ('name', 'city', 'opis_id')


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'state', 'kind', 'lat', 'lon')
    list_filter = ('kind', 'state')
    search_fields = ('name', 'display_name')
