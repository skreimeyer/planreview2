"""## esri

Esri is the interface to GIS servers. The servers esri communicates with are:

- pagis.org
    - geocode LOCATOR service
    - parcels
    - flood hazard
- maps.littlerock.state.ar.us
    - master street plan
    - zoning map

Queries are made via REST APIs, and the basic structure of the included the 
included functions typically only vary in query parameters and result parsing.

esri contains its own algorithms for computational geometry, which are probably
too basic of an implementation for export.

Where server queries are to return multiple data to be used together, classes
exist to act as a container. Floodhazard information is the exception, which
returns a set of strings.
"""

import requests
import logging
from dataclasses import dataclass
from copy import deepcopy
from typing import List, Dict, Optional, Any, Tuple, Set
import numpy as np

log = logging.getLogger(__name__)

@dataclass
class Envelope:
    xmin: float
    ymin: float
    xmax: float
    ymax: float


@dataclass
class ParcelData:
    location: Dict[str,float]
    ring: List[List[float]]
    acres: float
    envelope: Envelope

@dataclass
class Street:
    name: str
    classification: str
    row: int
    alt: bool = False
    state: bool = False

@dataclass
class Zone:
    classification: str
    overlays: Optional[List[str]]
    cases: Optional[List[str]]

def geocode(address: str) -> Optional[Dict[str,float]]:
    """Returns northing and easting of a parcel by address. Coordinates returned
    are state plan for Arkansas North.    
    """
    url = "https://www.pagis.org/arcgis/rest/services/LOCATORS/CompositeAddressPtsRoadCL/GeocodeServer/findAddressCandidates"
    params = {
        "SingleLine": address,
        "f": "json",
        "outFields": "*",
        "maxLocations": 3,
        "outSR": {
            "wkid": 102651,
            "latestWkid": 3433,
        },
    }
    response = requests.get(url, params=params)
    log.debug(f"HTTP GET:\t{response.url}")
    data = server_ok(response, "Geolocator")
    if not data:
        return None
    try:
        log.debug(f"address: {address} has {len(data['candidates'])} valid candidates")
        location = data['candidates'][0]['location']
        if 'x' not in location.keys() and 'y' not in location.keys():
            log.warning(f"invalid location: {location}")
            return None
        return location
    except Exception as e:
        log.warning(f"Valid address candidate not found for `{address}` with error: {e}")
        return None

def params_from_loc(location: Dict[str,float]) -> Dict[str,Any]:
    """Creates query parameters for the PAGIS parcel map server from northing
    and easting provided as a dictionary of 'x'-'y' coordinates. Coordinates
    are expected to be State Plane coordinates for Arkansas North.
    
    ```python
    {
        'x': 123.45,
        'y': 678.90
    }
    ```
    """
    geom_query = {
        "xmin": location['x'],
        "ymin": location['y'],
        "xmax": location['x'] + 13,
        "ymax": location['y'] + 13,
        "spatialReference": {
            "wkid": 102651,
            "latestWkid": 3433,
        }
    }
    geom_string = ''.join(geom_query.__repr__().split()).replace("'",'"')
    params = {
        "f": "json",
        "spatialRel": "esriSpatialRelIntersects",
        "maxAllowableOffset": 1,
        "geometry": geom_string,
        "geometryType": "esriGeometryEnvelope",
        "inSR": 102651,
        "outFields": "CALC_ACRE",
        "returnGeometry": "true",
    }
    return params

def params_from_pid(pid: str) -> Dict[str,Any]:
    """Creates query parameters for the PAGIS parcel map server from a Pulaski
    County parcel ID number.
    """
    params = {
        "f":"json",
        "outFields":"CALC_ACRE,PARCEL_ID",
        "outSR": 102651,
        "returnGeometry":"true",
        "spatialRel":"esriSpatialRelIntersects",
        "where": f"Upper(PARCEL_ID) LIKE UPPER('{pid}')"
    }
    return params

def fetch_parcel(params: Dict[str,Any]) -> Optional[ParcelData]:
    """Queries PAGIS for land parcel data. `params` must be the result of either
    `params_from_pid` or `params_from_loc`.
    """
    url = "https://pagis.org/arcgis/rest/services/APPS/OperationalLayers/MapServer/51/query"

    response = requests.get(url, params=params)
    data = server_ok(response, "Parcel")
    if not data:
        return None
    try:
        ring = data["features"][0]['geometry']['rings'][0]
        if len(ring) < 3:
            raise ValueError("Ring has less than three points")
        log.debug(f"ring: {ring}")
        center = centroid(ring)
        log.debug(f"centroid: {centroid}")
        acres = data["features"][0]['attributes']['CALC_ACRE']
        log.debug(f"acres: {acres}")
        envelope = make_envelope(ring)
        log.debug(f"Envelope: ({envelope.xmin},{envelope.ymin}),({envelope.xmax},{envelope.ymax})")
        return ParcelData(center,ring,acres,envelope)
    except Exception as e:
        log.warning(f"failed to find unmarshal parcel data with error {e}")
        return None

# GEOMETRY FUNCTION

def make_envelope(ring: List[List[float]]) -> Envelope:
    """Creates a rectangle enclosing an entire ring geometry."""
    xmin = min(n[0] for n in ring)
    ymin = min(n[1] for n in ring)
    xmax = max(n[0] for n in ring)
    ymax = max(n[1] for n in ring)
    return Envelope(xmin,ymin,xmax,ymax)

def centroid(ring: List[List[float]]) -> Dict[str,float]:
    """Calculates centerpoint of a centroid as x-y dict"""
    x = sum(n[0] for n in ring) / len(ring)
    y = sum(n[1] for n in ring) / len(ring)
    log.debug(f"ring: {ring} has centroid of [{x},{y}]")
    return {'x': x, 'y':y}


def buffer_ring(ring: List[List[float]], buffer: float) -> List[List[float]]:
    """create a ring with all points pushed outward by the buffer value."""
    if ring[0] == ring[-1]: # Start and end point is redundant on most rings
        ring.pop()
    angle = lambda a,b: np.arctan(np.divide((b[1]-a[1]),(b[0]-a[0])))   
    norm_angle = lambda a, b: np.arctan(np.divide(-(b[0]-a[0]),(b[1]-a[1])))
    add_vec = lambda a, theta, mag: [a[0]+mag*np.cos(theta),a[1]+mag*np.sin(theta)]
    buffered_ring = []
    for i in range(len(ring)):
        a = ring[i-2] # origin
        b = ring[i-1] # vertex
        c = ring[i] # end
        norm_ab = norm_angle(a,b)
        norm_cb = norm_angle(c,b)
        na = add_vec(b, norm_ab, buffer)
        if np.isclose(norm_ab, angle(b,c),atol=1e-3) and in_domain(na,c,b,b,na):
            na = add_vec(b, norm_ab + np.pi, buffer)
        if not is_outside(ring, na):
            na = add_vec(b, norm_ab + np.pi, buffer)
        nc = add_vec(b, norm_cb, buffer)
        if np.isclose(norm_cb, angle(b,a),atol=1e-3) and in_domain(nc,a,b,b,nc):
            nc = add_vec(b, norm_cb + np.pi, buffer)
        if not is_outside(ring, nc):
            nc = add_vec(b, norm_cb + np.pi, buffer)
        delta = [nc[0]-b[0],nc[1]-b[1]]
        v = [na[0]+delta[0],na[1]+delta[1]]
        buffered_ring.append(v)
    log.debug(f"Input ring is:{ring}\nBuffered ring is: {buffered_ring}")
    if buffered_ring[0] != buffered_ring[-1]: # `close` the ring
        buffered_ring.append(buffered_ring[0])
    return buffered_ring

def is_outside(ring: List[List[float]], point: List[float]) -> bool:
    """Calculates whether a point is within or outside of a ring geometry. The
    inclusion is calculated by counting the number of intersections a ray from
    origin of -1,-1 to the coordinates of point. An even number of intersections
    is outside of the ring.

    ```
        o --> | --> | --> X (2 intersection, X is outside)
        o --> | -->X | (1 intersection, X is inside)
    ```
    
    The test is performed for each line segment of a ring, ie every two points
    in sequence are tested.
    """
    origin = [-1.0,-1.0]
    intersections = 0
    vertex_intersections = 0
    for i in range(len(ring)):
        p1 = ring[i-1]
        p2 = ring[i]
        intersect = intersection(origin,point,p1,p2)
        if intersect is None:
            continue
        if not in_domain(intersect,p1,p2,origin,point):
            continue
        if intersect == p1 or intersect == p2:
            vertex_intersections += 1
        intersections += 1
    intersections = intersections - vertex_intersections/2
    return intersections % 2 == 0

def point_slope(a,b:List[float]) -> Tuple[float,float]:
    """Returns the slope and y-intercept of a line drawn between two points
    given as x,y coordinates. Return values are intended to be used for point-
    slope formula representation of a line, ie `y = mx + b`
    
    ```python
    >>>a = [0.0,0.0]
    >>>b = [1.0,1.0]
    >>>point_slope(a,b)
    (1.0,0.0)
    ```
    """
    m = np.divide((b[1]-a[1]),(b[0]-a[0]))
    b = a[1] - np.multiply(m,a[0])
    if b == np.inf or b == -np.inf:
        return(m,np.nan)
    return (m,b)

def intersection(a,b,c,d: List[float]) -> Optional[List[float]]:
    """Calculates the coordinate at which two lines, defined as the first two
    and last two points provided in the arguments, respectively, intersect on a
    cartesian plane.

    all arguments should be arrays of x-y coordinates `[0.0,1.0]`

    ```
      c
      |
    a-X---b
      |
      |
      d
    ```
    Intersection does not test whether or not the point of intersection lies
    between the lines defined by the points. The solution is detemined by 
    converting the points into two equations for lines in point-slope form which
    are then solved as a system of equations. The point of intersection may be
    a projection beyond the points.
    """

    m1,b1 = point_slope(a,b)
    m2,b2 = point_slope(c,d)
    if m1 == m2:
        return None
    if np.isnan(b1): # vertical line
        x = a[0]
        y = m2*x+b2
        return [x,y]
    if np.isnan(b2):
        x = c[0]
        y = m1*x+b1
        return [x,y]
    x = np.divide((b2-b1),(m1-m2))
    y = m1*x + b1
    return [x,y]
    
def in_domain(intersect, p1, p2, o1, o2:List[float]) -> bool:
    """determines if a point `[x,y]` intersect lies on the line between points
    p1,p2 and o1,o2.
    """
    for i, coord in enumerate(intersect):
        if coord > max(p1[i],p2[i]) or coord < min(p1[i],p2[i]):
            return False
        if coord > max(o1[i],o2[i]) or coord < min(o1[i],o2[i]):
            return False
    return True

# END GEOMETRY

def trans(ring: List[float]) -> List[Street]:
    """Queries the City of Little Rock transportation plan map for streets 
    contained within the queried ring. The ring supplied should be buffered to
    include the maximum probable distance a street centerline may be from the
    property.

    This function returns an array of `Street` objects, which have the street
    name, classification and alternative-design flag.
    """
    classify = {
        "minor residential": 45,
        "residential": 50,
        "collector": 60,
        "commercial": 60,
        "minor arterial": 90,
        "principal arterial": 110,
    }
    state_highway = {
        "INTERSTATE 30",
        "INTERSTATE 430",
        "INTERSTATE 440",
        "INTERSTATE 530",
        "INTERSTATE 630",
        "CANTRELL RD",
        "BROADWAY ST",
        "W ROOSEVELT RD",
        "S UNIVERSITY AVE",
        "N UNIVERSITY AVE",
        "BASELINE RD",
        "S ARCH ST",
        "STAGECOACH RD",
        "COLONEL GLENN RD",
    }
    url = "https://maps.littlerock.state.ar.us/arcgis/rest/services/Master_Street_Plan/MapServer/0/query"
    rings = {"rings": [ring]}.__repr__()
    params = {
        'f': 'json',
        'geometry': rings,
        'geometryType': 'esriGeometryPolygon',
        'spatialRel': 'esriSpatialRelIntersects',
        'inSR': 102651,
        'outSR': 102651,
        'maxAllowableOffset': 1,
        'outFields': "MapName,AltDes,SCADD_Type",
    }
    resp = requests.get(url,params=params)
    data = server_ok(resp, "Master Street Plan")
    if not data:
        return []
    if not data.get('features'):
        log.debug(f"No streets founds for query:{resp.url}")
        return []
    streets = []
    for f in data['features']:
        name = f['attributes']['MapName']
        state = False
        if name in state_highway:
            state = True
        classification = f['attributes']['SCADD_Type'].lower()
        row = classify.get(classification,50)
        is_alt = f['attributes'].get('AltDes') is not None
        streets.append(Street(name,classification,row,is_alt,state))
    log.debug(f"query:{resp.url}\nreturned streets:{streets}")
    return streets

def zoning(ring: List[float]) -> Optional[Zone]:
    """Queries multiple CLR Planning & Development zoning GIS servers to find
    which zoning criteria apply to a particular ring geometry. Returns a
    `Zone` object which holds the zoning classification, the overlay district
    (if any), and any CLR Planning Commission case files associated with the
    property.
    """ 
    actions_url = "https://maps.littlerock.state.ar.us/arcgis/rest/services/Zoning/MapServer/7/query"
    dod_url = "https://maps.littlerock.state.ar.us/arcgis/rest/services/Zoning/MapServer/13/query"
    zone_url = "https://maps.littlerock.state.ar.us/arcgis/rest/services/Zoning/MapServer/32/query"
    rings = {"rings": [ring]}.__repr__()
    base_params = {
        "f": "json",
        "inSR": 102651,
        "outSR": 102651,
        "spatialRel": "esriSpatialRelIntersects",
        "geometryType": "esriGeometryPolygon",
        "geometry": rings,
        "maxAllowableOffset": 1,
        "returnGeometry": "false",
    }
    actions_params = deepcopy(base_params)
    actions_params["outFields"] = "GIS_LR.GISPLAN.Z_number.LABEL"
    dod_params = deepcopy(base_params)
    dod_params["outFields"] = "name,ordinance"
    zone_params = deepcopy(base_params)
    zone_params['outFields'] = "GIS_LR.GISPLAN.Zoning_Poly.ZONING"
    s = requests.session()
    actions_resp = s.get(actions_url,params=actions_params)
    actions_data = server_ok(actions_resp, "Planning actions")
    if not actions_data:
        return None
    features = actions_data.get("features",[])
    cases = []
    for f in features:
        case = f.get("attributes",{}).get("GIS_LR.GISPLAN.Z_Number.LABEL")
        cases.append(case)
    cases = cases or None
    dod_resp = s.get(dod_url,params=dod_params)
    dod_data = server_ok(dod_resp, "Design overlay")
    if not dod_data:
        return None
    features = dod_data.get("features",[])
    overlays = []
    for f in features:
        overlay = f.get("attributes",{}).get("name")
        overlays.append(overlay)
    overlays = overlays or None
    zone_resp = s.get(zone_url,params=zone_params)
    zone_data = server_ok(zone_resp, "Zoning")
    if not zone_data:
        return None
    zone = zone_data.get("features",[{}])[0].get("attributes",{}).get("GIS_LR.GISPLAN.Zoning_Poly.ZONING")
    if not zone:
        log.warning(f"Zoning data unavailable\nquery:{zone_resp.url}")
        return None
    result_zone =  Zone(zone,overlays,cases)
    log.debug(f"Zoning data: {result_zone}")
    return result_zone

def floodmap(ring: List[List[float]]) -> Set[str]:
    """Find all special flood hazard areas within a ring geometry.
    """
    url = "https://www.pagis.org/arcgis/rest/services/APPS/Apps_DFIRM/MapServer//dynamicLayer/query"
    rings = {"rings": [ring]}.__repr__()
    params = {
        "f":"json",
        "geometry": rings,
        "geometryType": "esriGeometryPolygon",
        "returnGeometry": "false",
        "inSR": 102651,
        "layer": {"source":{"type":"mapLayer","mapLayerId":20}}.__repr__(),
        "maxAllowableOffset":1,
        "outFields": "FLD_ZONE,LEGEND"
    }
    resp = requests.get(url,params=params)
    data = server_ok(resp, "Flood Hazard Map")
    if not data:
        return None
    features = data.get("features",[])
    log.debug(f"query returned {len(features)} features")
    zones = set()
    for feat in features:
        f = feat.get("attributes",{})
        zone = f.get("FLD_ZONE")
        legend = f.get("LEGEND")
        if zone is None or legend is None:
            continue
        zones.add(zone)
        if "Inside Floodway" in legend:
            zones.add("Floodway")
    log.debug(f"Zones are: {zones}")
    return zones


def server_ok(r: requests.Response, name: str) -> Optional[Dict[Any,Any]]:
    """Check for status code of 200 and return response.json() if successful.    
    Otherwise log a warning and return `None`
    """
    if r.status_code != 200:
        log.warning(f"Failed to connect to {name} server.\nStatus:{r.status_code}\nQuery:{r.url}")
        return None
    return r.json()