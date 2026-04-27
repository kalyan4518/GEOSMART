import heapq
import math

from config import Config, DEPOT_COORDS, NODE_COORDS, ROUTE_GRAPH, WARD_CENTROIDS


class AStarRouter:
    def __init__(self, graph=None, node_coords=None, depots=None):
        self.graph = graph or ROUTE_GRAPH
        self.node_coords = node_coords or NODE_COORDS
        self.depots = depots or DEPOT_COORDS
        self.future_features = {
            "multi_stop_vehicle_routing": False,
            "traffic_aware_costs": False,
            "external_routing_provider": None,
        }

    @staticmethod
    def distance_km(point_a, point_b):
        if not point_a or not point_b:
            return 0.0
        lat_scale = 111.0
        lng_scale = 111.0 * math.cos(math.radians((point_a[0] + point_b[0]) / 2))
        delta_lat = (point_a[0] - point_b[0]) * lat_scale
        delta_lng = (point_a[1] - point_b[1]) * lng_scale
        return math.sqrt(delta_lat * delta_lat + delta_lng * delta_lng)

    def nearest_ward(self, latitude, longitude):
        point = (latitude, longitude)
        return min(WARD_CENTROIDS, key=lambda ward: self.distance_km(point, WARD_CENTROIDS[ward]))

    def route_hint_for_point(self, latitude, longitude, ward=None):
        if latitude is None or longitude is None:
            if ward and ward in WARD_CENTROIDS:
                latitude, longitude = WARD_CENTROIDS[ward]
            else:
                return {"depot": "Central Transfer Hub", "etaMinutes": None}

        point = (latitude, longitude)
        depot = min(self.depots, key=lambda name: self.distance_km(point, self.depots[name]))
        eta = max(
            8,
            int(round(self.distance_km(point, self.depots[depot]) / max(Config.RESPONSE_SPEED_KMPH, 1) * 60 + 6)),
        )
        return {"depot": depot, "etaMinutes": eta}

    def shortest_path(self, start, goal):
        if start == goal:
            return [start], 0.0

        open_heap = [(0.0, start)]
        came_from = {}
        g_score = {start: 0.0}

        while open_heap:
            _, current = heapq.heappop(open_heap)
            if current == goal:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path, round(g_score[goal], 2)

            for neighbor in self.graph.get(current, []):
                tentative = g_score[current] + self.distance_km(self.node_coords[current], self.node_coords[neighbor])
                if tentative < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative
                    heuristic = self.distance_km(self.node_coords[neighbor], self.node_coords[goal])
                    heapq.heappush(open_heap, (tentative + heuristic, neighbor))

        return [start], 0.0

    def build_route_plan(self, hotspot):
        ward = hotspot["ward"]
        target_point = (hotspot["latitude"], hotspot["longitude"])
        start = min(self.depots, key=lambda depot: self.distance_km(self.depots[depot], target_point))
        goal = ward if ward in self.node_coords else self.nearest_ward(target_point[0], target_point[1])
        path, distance = self.shortest_path(start, goal)

        route_points = [
            {"name": node, "latitude": self.node_coords[node][0], "longitude": self.node_coords[node][1]}
            for node in path
        ]
        last_point = (route_points[-1]["latitude"], route_points[-1]["longitude"]) if route_points else target_point
        final_leg = self.distance_km(last_point, target_point)
        total_distance = round(distance + final_leg, 2)
        if not route_points or last_point != target_point:
            route_points.append({
                "name": hotspot["title"],
                "latitude": target_point[0],
                "longitude": target_point[1],
            })

        eta_minutes = max(
            10,
            int(round(total_distance / max(Config.RESPONSE_SPEED_KMPH, 1) * 60 + 6)),
        )
        return {
            "startDepot": start,
            "targetWard": ward,
            "distanceKm": total_distance,
            "etaMinutes": eta_minutes,
            "path": route_points,
            "stops": [point["name"] for point in route_points],
        }


default_router = AStarRouter()