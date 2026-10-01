from django.test import SimpleTestCase

from routing.services.optimizer import Candidate, NoFeasiblePlan, plan_fuel_stops


def cand(key, mile, price, off=0.0):
    return Candidate(key=key, mile=mile, off_route=off, price=price)


class PlanFuelStopsTests(SimpleTestCase):
    def test_short_trip_needs_no_stop(self):
        plan = plan_fuel_stops(300, [cand(1, 100, 3.0)], tank_range=500, mpg=10)
        self.assertEqual(plan.stops, [])
        self.assertEqual(plan.total_cost, 0)
        self.assertAlmostEqual(plan.driven_miles, 300)

    def test_buys_only_what_is_needed_to_finish(self):
        plan = plan_fuel_stops(700, [cand(1, 400, 3.0)], tank_range=500, mpg=10)
        [stop] = plan.stops
        self.assertAlmostEqual(stop.gallons, 20)
        self.assertAlmostEqual(plan.total_cost, 60)

    def test_prefers_cheaper_station_in_range(self):
        stations = [cand(1, 300, 4.0), cand(2, 450, 3.0)]
        plan = plan_fuel_stops(800, stations, tank_range=500, mpg=10)
        self.assertEqual([s.candidate.key for s in plan.stops], [2])
        self.assertAlmostEqual(plan.total_cost, 30 * 3.0)

    def test_fills_up_at_cheap_station_before_expensive_stretch(self):
        stations = [cand(1, 400, 3.0), cand(2, 800, 5.0)]
        plan = plan_fuel_stops(1200, stations, tank_range=500, mpg=10)
        bought = {s.candidate.key: round(s.gallons, 6) for s in plan.stops}
        self.assertEqual(bought, {1: 40, 2: 30})
        self.assertAlmostEqual(plan.total_cost, 40 * 3 + 30 * 5)

    def test_detour_counts_against_range(self):
        plan = plan_fuel_stops(600, [cand(1, 300, 3.0, off=10)], tank_range=500, mpg=10)
        [stop] = plan.stops
        self.assertAlmostEqual(stop.fuel_on_arrival, 190)
        self.assertAlmostEqual(stop.miles_purchased, 310 - 190)
        self.assertAlmostEqual(plan.driven_miles, 620)

    def test_gap_longer_than_range_is_infeasible(self):
        with self.assertRaises(NoFeasiblePlan):
            plan_fuel_stops(1200, [cand(1, 200, 3.0), cand(2, 900, 3.0)], tank_range=500, mpg=10)

    def test_never_runs_dry(self):
        stations = [cand(i, i * 37.0, 3 + (i * 7919 % 13) / 10) for i in range(1, 80)]
        plan = plan_fuel_stops(2900, stations, tank_range=500, mpg=10, price_tolerance=0.05)
        fuel, pos = 500.0, 0.0
        for stop in plan.stops:
            fuel -= stop.candidate.mile - pos
            self.assertGreaterEqual(fuel, -1e-6)
            self.assertAlmostEqual(fuel, stop.fuel_on_arrival)
            fuel += stop.miles_purchased
            self.assertLessEqual(fuel, 500 + 1e-6)
            pos = stop.candidate.mile
        self.assertGreaterEqual(fuel - (2900 - pos), -1e-6)

    def test_min_purchase_skips_token_top_up(self):
        stations = [cand(1, 10, 3.0), cand(2, 450, 3.5)]
        plan = plan_fuel_stops(800, stations, tank_range=500, mpg=10, min_purchase=50)
        self.assertEqual([s.candidate.key for s in plan.stops], [2])

    def test_min_purchase_rounds_up_instead_of_stopping_at_the_end(self):
        stations = [cand(1, 450, 3.5), cand(2, 599, 3.0, off=1)]
        plan = plan_fuel_stops(600, stations, tank_range=500, mpg=10, min_purchase=50)
        self.assertEqual([s.candidate.key for s in plan.stops], [1])
        self.assertAlmostEqual(plan.stops[0].gallons, 10)
