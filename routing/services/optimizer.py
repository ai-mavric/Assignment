from dataclasses import dataclass, field


class NoFeasiblePlan(Exception):
    pass


@dataclass(frozen=True)
class Candidate:
    key: int
    mile: float
    off_route: float
    price: float


@dataclass
class Stop:
    candidate: Candidate
    fuel_on_arrival: float
    miles_purchased: float
    gallons: float


@dataclass
class Plan:
    stops: list[Stop] = field(default_factory=list)
    total_cost: float = 0.0
    gallons_purchased: float = 0.0
    driven_miles: float = 0.0


EPS = 1e-9


def plan_fuel_stops(route_miles, candidates, tank_range, mpg, start_fuel=None, price_tolerance=0.0,
                    min_purchase=0.0) -> Plan:
    cands = sorted(candidates, key=lambda c: (c.mile, c.price))
    fuel = tank_range if start_fuel is None else start_fuel
    cur = None
    cur_mile = cur_off = 0.0
    next_idx = 0
    plan = Plan()

    def dist(c):
        return (c.mile - cur_mile) + cur_off + c.off_route

    def sized(buy, needed):
        if buy <= EPS or buy >= min_purchase:
            return buy
        if fuel + EPS >= needed:
            return 0.0
        return min(min_purchase, tank_range - fuel)

    while True:
        to_end = (route_miles - cur_mile) + cur_off
        limit = tank_range if cur is not None else fuel
        reachable = []
        for k in range(next_idx, len(cands)):
            c = cands[k]
            if c.mile - cur_mile > limit:
                break
            d = dist(c)
            if d <= limit + EPS:
                reachable.append((k, c, d))

        if cur is None:
            if to_end <= fuel + EPS:
                plan.driven_miles += to_end
                return plan
            target, buy = _cheapest(reachable, price_tolerance), 0.0
        else:
            cheaper = next((r for r in reachable if r[1].price < cur.price - price_tolerance), None)
            if cheaper is not None and to_end <= tank_range + EPS and to_end - cheaper[2] < min_purchase:
                cheaper = None
            if to_end <= fuel + EPS:
                plan.driven_miles += to_end
                return plan
            if cheaper is not None:
                target, buy = cheaper, sized(max(0.0, cheaper[2] - fuel), cheaper[2])
            elif to_end <= tank_range + EPS:
                buy = sized(max(0.0, to_end - fuel), to_end)
                _record(plan, cur, fuel, buy, mpg)
                plan.driven_miles += to_end
                return plan
            else:
                target = _cheapest(reachable, price_tolerance)
                if target is not None and target[1].price <= cur.price + price_tolerance:
                    buy = max(0.0, target[2] - fuel)
                else:
                    buy = tank_range - fuel
                if target is not None:
                    buy = sized(buy, target[2])

        if target is None:
            raise NoFeasiblePlan(
                f'No fuel station within {limit:.0f} miles after mile {cur_mile:.0f} of the route.'
            )
        if cur is not None:
            _record(plan, cur, fuel, buy, mpg)
        k, c, d = target
        fuel = fuel + buy - d
        plan.driven_miles += d
        cur, cur_mile, cur_off, next_idx = c, c.mile, c.off_route, k + 1


def _cheapest(reachable, tolerance):
    if not reachable:
        return None
    best = min(r[1].price for r in reachable)
    return max((r for r in reachable if r[1].price <= best + tolerance), key=lambda r: (r[1].mile, -r[1].price))


def _record(plan, cand, fuel, buy, mpg):
    if buy <= EPS:
        return
    stop = Stop(candidate=cand, fuel_on_arrival=fuel, miles_purchased=buy, gallons=buy / mpg)
    plan.stops.append(stop)
    plan.gallons_purchased += stop.gallons
    plan.total_cost += stop.gallons * cand.price
