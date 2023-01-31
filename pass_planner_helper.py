'''
This code was reproduced from Richard Arthurs via the ORCASat 
gitlab January 17, 2023. 
'''

from datetime import timedelta, datetime
from dateutil import tz
from typing import List, SupportsFloat, Tuple, Optional

from skyfield.api import EarthSatellite, load
from skyfield.toposlib import wgs84
import urllib.request
import urllib.error as url_error

UVIC_GROUND_STATION = wgs84.latlon(+48.46, -123.31)

USE_MANUAL_TLE = False  # TODO Set to False once we use Celestrak TLE https://gitlab.orcasat.ca/orcasat-group/cdh/gcs/-/issues/209
ORCASAT_NORAD_ID = 55126 # TODO update from ISS ID to ORCASat ID https://gitlab.orcasat.ca/orcasat-group/cdh/gcs/-/issues/209

# tle_name = "ORCAGPS_2023-01-05_0738"
# line_1 = "1 99999U          23005.31851852 +.00000000  00000 0  00000 0 0 00009"
# line_2 = "2 99999  51.6443  55.2455 0004903 269.6366 143.8400 15.51087205000004"

class PassInfo:
    """
    Information about a pass including start/end times and satellite ground track.
    """
    def __init__(self, sat: EarthSatellite, pass_start: datetime, pass_end:datetime):
        """
        Create a PassInfo instance.

        :param sat: The satellite performing the pass.
        :param pass_start: Pass start time.
        :param pass_end: Pass end time.
        """
        self._sat_name = sat.name
        self._start_dt = pass_start.replace(tzinfo = tz.gettz('UTC'))
        self._end_dt = pass_end.replace(tzinfo = tz.gettz('UTC'))

        # Generate timestamps every 10 seconds in the pass in skyfield and datetime formats
        timescale = load.timescale()
        self._t_skyfield = []
        self._t_datetime_utc = []
        t = timescale.from_datetime(self._start_dt)
        while t.utc_datetime() < self._end_dt:
            self._t_skyfield.append(t)
            self._t_datetime_utc.append(t.utc_datetime())
            t = t + timedelta(seconds=10)

        self._latitude_deg = []
        self._longitude_deg = []
        self._d_slant_km = []
        self._alt_deg = []
        self._az_deg = []

        # Generate satellite ground track and azimuth/elevation angles
        for t in self._t_skyfield:
            difference = sat - UVIC_GROUND_STATION
            topocentric_pos = difference.at(t)
            lat, lon = wgs84.latlon_of(sat.at(t))
            self._latitude_deg.append(lat.degrees)
            self._longitude_deg.append(lon.degrees)

            alt, az, d = topocentric_pos.altaz()
            self._alt_deg.append(alt.degrees)
            self._az_deg.append(az.degrees)
            self._d_slant_km.append(d.km)

        self._max_alt_deg = max(self._alt_deg)

    @property
    def sat_name(self) -> str:
        """Satellite name"""
        return self._sat_name

    @property
    def duration(self) -> timedelta:
        """Length of the pass"""
        return self._end_dt - self._start_dt

    @property 
    def local_start_time(self) -> datetime:
        """Start time in the Vancouver/Victoria time zone"""
        return self._start_dt.astimezone(tz.gettz('Canada/Vancouver'))

    @property 
    def local_end_time(self) -> datetime:
        """End time in the Vancouver/Victoria time zone"""
        return self._end_dt.astimezone(tz.gettz('Canada/Vancouver'))

    @property 
    def start_dt_utc(self) -> datetime:
        """Start time in UTC"""
        return self._start_dt

    @property 
    def end_dt_utc(self) -> datetime:
        """End time in UTC"""
        return self._end_dt

    @property
    def t_datetime_utc(self) -> List[datetime]:
        """Time steps of orbit propagation in UTC datetimes"""
        return self._t_datetime_utc

    @property
    def rating(self) -> int:
        """
        A basic measure for pass quality. One is added to the rating for each of the following criteria:
            1. Max altitude > 70 degrees (spacecraft passes roughly overhead)
            2. Duration is greater than average
            3. Start time is between 7:00 AM and 10:00 PM
        """
        rating = 0

        if self.max_alt_deg > 70:
            rating = rating + 1

        if self.duration.total_seconds() > 275:
            rating = rating + 1

        if self.local_start_time.hour >= 7 and self.local_end_time.hour <= 22:
            rating = rating + 1

        return rating

    @property
    def latitude_deg(self) -> List[SupportsFloat]:
        """Latitude of spacecraft ground track (deg)"""
        return self._latitude_deg

    @property
    def longitude_deg(self) -> List[SupportsFloat]:
        """Longitude of spacecraft ground track (deg)"""
        return self._longitude_deg

    @property
    def d_slant_km(self) -> List[SupportsFloat]:
        """Slant range to spacecraft from ground station (km)"""
        return self._d_slant_km

    @property
    def alt_deg(self) -> List[SupportsFloat]:
        """Altitude of spacecraft when viewed from ground station (deg)"""
        return self._alt_deg

    @property
    def az_deg(self) -> List[SupportsFloat]:
        """Azimuth of spacecraft when viewed from ground station (deg)"""
        return self._az_deg

    @property
    def max_alt_deg(self) -> float:
        """Maximum azimuth angle of spacecraft when viewed from ground station (deg)"""
        return self._max_alt_deg

def compute_passes(norad_catalog_num: int=ORCASAT_NORAD_ID, num_days=1) -> List[PassInfo]:
    """
        Computes the start/end times for future passes
    Args:
        norad_catalog_num: The norad catalog number of ORCASat (or the satellite to compute passes for)
        num_days: How many days in the future to compute passes for

    Returns: A list of pass times for the specified period

    """
    # Get the latest TLE from celestrak
    if not USE_MANUAL_TLE:
        sat = get_sat(norad_catalog_num)    # Load from CelesTrak
    else:
        ts = load.timescale()
        sat = EarthSatellite(line_1, line_2, name=tle_name, ts=ts)

    ts = load.timescale()

    start = ts.now()
    end = start + timedelta(days=num_days)

    passes = []
    pass_start = None

    # Compute the times when the satellite rises and sets
    t, events = sat.find_events(UVIC_GROUND_STATION, start, end, altitude_degrees=15.0)

    for ti, event in zip(t, events):
        # Satellite passing above the horizon
        if event == 0:
            pass_start = ti
        # Satellite passing below the horizon
        if event == 2 and pass_start is not None:
            passes.append(PassInfo(sat, pass_start=pass_start.utc_datetime(), pass_end=ti.utc_datetime()))

    return passes

def get_tle(norad_catalog_num: int=ORCASAT_NORAD_ID) -> Tuple[Tuple[str, str], str]:
    """
    Get the TLE for a NORAD ID from Celestrak.

    Returns: ((TLE line 1, TLE line 2), satellite name)
    """
    celestrak_url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_catalog_num}&FORMAT=tle"
    try:
        uf = urllib.request.urlopen(celestrak_url)
    except Exception as e:
        raise RuntimeError(f"URLLib error received when trying to contact Celestrak. Error: {e}")

    html = uf.read().decode()
    tle = html.split('\r\n')[0:3]

    if tle[2] == "<html>":
        raise RuntimeError(f"NORAD ID of {norad_catalog_num} was not found in Celestrak")
    elif len(tle) == 0:
        raise RuntimeError("No data was received from Celestrak")

    name = tle[0].strip()

    return ((str(tle[1]), str(tle[2])), name)

def get_sat(norad_catalog_num: int=ORCASAT_NORAD_ID) -> EarthSatellite:
    """
    Returns a satellite for propagating orbits.

    :param norad_catalog_num: The norad catalog number of ORCASat (or the satellite to compute passes for)
    """
    tle, name = get_tle(norad_catalog_num)
    ts = load.timescale()
    sat = EarthSatellite(*tle, name, ts)
    return sat