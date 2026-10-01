from urllib.parse import urlencode

from django.shortcuts import render
from django.urls import reverse
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.external import ExternalServiceError, NoRouteFound
from .services.geocoding import LocationError
from .services.optimizer import NoFeasiblePlan
from .services.planner import get_trip_plan


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField(max_length=200, help_text='"City, ST", a US address, or "lat,lon"')
    finish = serializers.CharField(max_length=200, help_text='"City, ST", a US address, or "lat,lon"')


def _plan_or_error(data):
    params = RouteRequestSerializer(data=data)
    if not params.is_valid():
        return None, (params.errors, status.HTTP_400_BAD_REQUEST)
    start, finish = params.validated_data['start'], params.validated_data['finish']
    try:
        return get_trip_plan(start, finish), None
    except LocationError as exc:
        return None, ({'detail': str(exc)}, status.HTTP_400_BAD_REQUEST)
    except (NoRouteFound, NoFeasiblePlan) as exc:
        return None, ({'detail': str(exc)}, status.HTTP_422_UNPROCESSABLE_ENTITY)
    except ExternalServiceError as exc:
        return None, ({'detail': f'Routing/geocoding service unavailable: {exc}'}, status.HTTP_502_BAD_GATEWAY)


class RoutePlanView(APIView):
    def get(self, request):
        return self._respond(request, request.query_params)

    def post(self, request):
        return self._respond(request, request.data)

    def _respond(self, request, data):
        plan, error = _plan_or_error(data)
        if error:
            return Response(error[0], status=error[1])
        query = urlencode({'start': plan['start']['query'], 'finish': plan['finish']['query']})
        map_url = request.build_absolute_uri(f"{reverse('route-map')}?{query}")
        return Response({'map_url': map_url, **plan})


def route_map(request):
    plan, error = _plan_or_error(request.GET)
    if error:
        return render(request, 'routing/map.html', {'error': error[0]}, status=error[1])
    return render(request, 'routing/map.html', {'plan': plan})
