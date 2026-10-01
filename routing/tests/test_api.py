from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from routing.models import FuelStation, Place
from routing.services import external
from routing.services.stations import get_station_index

ROUTE_COORDS = [[-100.0 + i * 0.151, 40.0] for i in range(101)]
ROUTE = (800.0, 12 * 3600.0, ROUTE_COORDS)


class RouteApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Place.objects.create(state='KS', name='westville', display_name='Westville city', kind='place', lat=40.0, lon=-100.0)
        Place.objects.create(state='MO', name='eastville', display_name='Eastville city', kind='place', lat=40.0, lon=-84.9)
        for opis, lon, price in [(1, -94.0, '3.50'), (2, -93.0, '3.10'), (3, -90.0, '3.90')]:
            FuelStation.objects.create(opis_id=opis, name=f'Stop {opis}', address='I-70', city='X', state='KS',
                                       price=Decimal(price), lat=40.02, lon=lon)
        FuelStation.objects.create(opis_id=9, name='Far', address='', city='Y', state='TX',
                                   price=Decimal('1.00'), lat=30.0, lon=-95.0)

    def setUp(self):
        cache.clear()
        get_station_index.cache_clear()

    def get(self, **params):
        return self.client.get('/api/route/', params)

    @mock.patch.object(external, '_get')
    def test_plan_uses_single_routing_call_and_cheapest_station(self, http_get):
        http_get.return_value = {'code': 'Ok', 'routes': [{'distance': 800 * 1609.344, 'duration': 43200,
                                                           'geometry': {'coordinates': ROUTE_COORDS}}]}
        resp = self.get(start='Westville, KS', finish='Eastville, Missouri')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()

        self.assertEqual(http_get.call_count, 1)
        self.assertEqual(body['meta']['routing_api_calls'], 1)
        self.assertEqual(body['meta']['geocoding_api_calls'], 0)
        self.assertEqual([s['opis_id'] for s in body['fuel_stops']], [2])
        stop = body['fuel_stops'][0]
        self.assertAlmostEqual(stop['cost'], stop['gallons_purchased'] * 3.10, places=1)
        self.assertEqual(body['summary']['total_fuel_cost'], stop['cost'])
        self.assertEqual(body['route']['geometry']['type'], 'LineString')
        self.assertIn('/route/map/?', body['map_url'])

        again = self.client.post('/api/route/', {'start': 'Westville, KS', 'finish': 'Eastville, Missouri'},
                                 content_type='application/json')
        self.assertTrue(again.json()['meta']['cached'])
        self.assertEqual(self.client.get(body['map_url']).status_code, 200)
        self.assertEqual(http_get.call_count, 1)

    @mock.patch('routing.services.planner.osrm_route', return_value=ROUTE)
    def test_accepts_coordinates(self, _):
        resp = self.get(start='40.0,-100.0', finish='40.0,-84.9')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['start']['geocoded_by'], 'coordinates')

    def test_rejects_location_outside_usa(self):
        resp = self.get(start='48.85,2.35', finish='Eastville, MO')
        self.assertEqual(resp.status_code, 400)

    def test_requires_both_locations(self):
        resp = self.get(start='Westville, KS')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('finish', resp.json())

    @mock.patch.object(external, '_get', return_value={'code': 'NoRoute', 'message': 'Impossible route'})
    def test_no_route_is_422(self, _):
        resp = self.get(start='Westville, KS', finish='Eastville, MO')
        self.assertEqual(resp.status_code, 422)

    @mock.patch.object(external, '_get', side_effect=external.ExternalServiceError('timeout'))
    def test_upstream_failure_is_502(self, _):
        resp = self.get(start='Westville, KS', finish='Eastville, MO')
        self.assertEqual(resp.status_code, 502)
