import xarray as xr
import datetime
from datetime import timedelta as td
from datetime import datetime as dt
import pandas as pd
import copy
import cftime

from . import _consts as consts

class basics():
    """The :class:`basics` contains some basics functions for controlling netCDF CF standard time axis

    **Attributes**
        *fmt:* str
            Time format for converting strings into ``cftime.datetime`` object
        *calendar:* str
            Calendar type for the datetimes.
    """

    def __init__(self, fmt=None, calendar=None):
        if not fmt: fmt = '%Y-%m-%dT%H:%M:%S'
        if not calendar: calendar = 'standard'
        self.fmt = fmt
        self.calendar = calendar
        
    def _flatten_list(self, lst):
        """Flatten a list containing strings and lists of arbitrarily nested lists

        Parameters
        ----------
        lst: list
            List containing strings and lists of arbitrarily nested lists

        Returns
        -------
        list
        """
        rt = []
        for i in lst:
            if isinstance(i,list): rt.extend(self._flatten_list(i))
            else: rt.append(i)
        return rt

    def _convert_to_string(self, values, delim=',',fmt=None):
        """Converts list of strings and ``cftime.datetime`` or ``datetime.datetime`` objects to string

        Parameters
        ----------
        values: list
            List of strings and ``cftime.datetime`` or ``datetime.datetime`` objects
        delim: str, default: ','
            Output string delimiter between input list entries
        fmt: str, default: ' %Y-%m-%dT%H:%M:%S'
            Explicit format string for converting string into ``cftime.datetime`` or ``datetime.datetime`` object
            Consider only if list element is ``cftime.datetime`` object
        
        Returns
        -------
        str
        """
        if not fmt: fmt=self.fmt
        converted = ''
        for v in values:
            try:
                v = self._date_to_str(v, fmt=fmt)
            except:
                pass
            converted += str(v) + delim
        return converted[:-1]

    def _dictionary(self, attr, keys, value):
        """Write or update attribute using key-value pairs

        Parameters
        ----------
        attr: str
            Attribute name
        keys: str
            Key names
        values: any type
            Key values
        """
        for key in keys:
            if attr in self.__dict__:
                getattr(self, attr)[key] = value
            else:
                setattr(self, attr, {key : value})

    def _get_key_to_value(self, dict, value):
        """Get key of key-value pair using value

        Parameters
        ----------
        dict: dict
            Dictionary containing key-value pair
        value: any type
            Value of key-value pair
        
        Returns
        -------
        key: str
            Key of key-value pair
        """
        key_list = list(dict.keys())
        val_list = list(dict.values())
        position = val_list.index(value)
        return key_list[position]

    def _get_date_attr(self, frequencies):
        """Get ``cftime.datetime`` instance attribute from CF frequency
        
        Parameters
        ----------
        frequencies: str or list
            CF frequency or list of CF frequencies
        
        Returns
        -------
        attribute: str
            ``cftime.datetime`` instance attribute
        """
        f = self._get_key_to_value(consts.frequencies, frequencies)
        return consts.translator[f]

    def _str_to_date(self, str, fmt=None, mode='start', calendar=None):
        """Converts string to ``cftime.datetime`` object

        Parameters
        ----------
        str: str
            string representing the time
        fmt: str, default: '%Y-%m-%dT%H:%M:%S'
            Explicit format string
        calendar: str, default: 'standard'
            Calendar type for the datetimes
        mode: {'start', 'end'}, default: 'start'
            `start`: Set ``cftime.datetime`` instance attributes not represented by `fmt` to 0  
            `end`: Set ``cftime.datetime`` instance attributes not represented by `fmt` to last possible values considering `str`

        Returns
        -------
        ``cftime.datetime`` object
        """
        i=1
        if not fmt: fmt=self.fmt
        if not calendar: calendar=self.calendar
        if mode not in ['start', 'end']: return
        while True:
            try:
                date = dt.strptime(str, fmt[:i])
                break
            except:
                i+=1
        cfdate = cftime.datetime(date.year, date.month, date.day, calendar=calendar)
        if mode == 'start': return cfdate
        if mode == 'end': return cfdate + td(days=1) - td(seconds=1)

    def _date_to_str(self, date, fmt=None):
        """Converts ``cftime.datetime`` or ``datetime.datetime`` object to string

        Parameters
        ----------
        date: ``cftime.datetime`` or ``datetime.datetime`` object
            time to be converted
        fmt: str, default: '%Y-%m-%dT%H:%M:%S'
            Explicit format string
        
        Returns
        -------
        str: str
            string representing the time
        """
        if not fmt: fmt=self.fmt
        return date.strftime(fmt)

    def _convert_time(self, time):
        """Converts time object to ``datetime.datetime`` object"""
        try:
            return pd.to_datetime(time.indexes['time'].astype('str'), format=time.units.split(' ')[-1])
        except:
            return time.indexes['time']

    def _equalize_time(self, time, ignore=['second','microsecond','nanosecond']):
        """Ignore ``datetime.datetime`` instance attributes and set them to 0

        Parameters
        ----------
        time: CFTimeIndex
            CFTimeIndex containing cftime.datetime objects
        ignore: list, default: ['second','microsecond','nanosecond']
            list of datetime.datetime instance attributes to be ignored

        Returns
        -------
        time: CFTimeIndex
            ``CFTimeIndex`` containing ``cftime.datetime`` objects with ignored instance attributes
        """
        n = 0
        while n < len(ignore):
            etime = time.tolist()
            query = {ignr:1 for ignr in ignore[::-1][n:]}
            try:
                i = 0
                while i < len(etime):
                    etime[i] = etime[i].replace(**query)
                    i += 1
                return etime
            except:
                n += 1
        return time.tolist()

    def _mid_timestep(self, freq, st, end, calendar=None):
        """Build ``CFTimeIndex`` 
        Set elements between user-given frequencies

        Parameters
        ----------
        freq: list
            list of two frequency strings for use with ``cftime`` calendars
            https://xarray.pydata.org/en/stable/generated/xarray.cftime_range.html
        st: cftime.datetime or datetime.datetime
            Left bound for generating dates
        end: cftime.datetime or datetime.datetime
            Right bound for generating dates
        calendar: str, default: 'standard'
            Calendar type for the datetimes

        Returns
        -------
        CFTimeIndex
        """
        def end_of(date, attr):
            while True:
                m  = getattr(date, attr)
                nm = getattr((date + td(hours=1)), attr)
                if nm != m:
                    return date
                date += td(hours=1)

        def begin_of(date, attr):
            while True:
                m  = getattr(date, attr)
                pm = getattr((date - td(hours=1)), attr)
                if pm !=m:
                    return date
                date -= td(hours=1)

        if not calendar: calendar = self.calendar
        attr = self._get_date_attr(freq)
        t1  = xr.cftime_range(st, end, freq=freq[0], calendar=calendar)
        t2 = xr.cftime_range(st, periods=len(t1), freq=freq[1], calendar=calendar)
        return t1 + (t2 - t1 + td(days=1)) / 2

    def _point_timestep(self, freq, st, end, calendar=None):
        """Build ``CFTimeIndex`` 
        Set elements to user-given frequency

        Parameters
        ----------
        freq: str
            frequency string for use with ``cftime`` calendars
            https://xarray.pydata.org/en/stable/generated/xarray.cftime_range.html
        st: cftime.datetime or datetime.datetime
            Left bound for generating dates
        end: cftime.datetime or datetime.datetime
            Right bound for generating dates
        calendar: str, default: 'standard'
            Calendar type for the datetimes

        Returns
        -------
        CFTimeIndex
        """
        if not calendar: calendar=self.calendar
        return xr.cftime_range(st, end, freq=freq, calendar=calendar)

    def _date_range(self, start, end, frequency, calendar=None):
        """Build ``CFTimeIndex``

        Parameters
        ----------
        start: cftime.datetime or datetime.datetime or str
            Left bound for generating dates
        end: cftime.datetime or datetime.datetime or str
            Right bound for generating dates
        frequency: str ot list
            frequency string or list of frequency strings for use with ``cftime`` calendars
            https://xarray.pydata.org/en/stable/generated/xarray.cftime_range.html
            Set elements to user-given frequency if type of frequency is str
            Set elements between user-given frequencies if type
        calendar: str, default: 'standard'
            
        Returns
        -------
        CFTimeIndex
        """
        if not calendar: calendar = self.calendar
        function = xr.cftime_range
        if isinstance(frequency, str):
            return self._point_timestep(frequency, start, end, calendar=calendar)
        if isinstance(frequency, list):
            return self._mid_timestep(frequency, start, end, calendar=calendar)

    def _is_month_start(self, cftime_range):
        """Check whether each element of ``CFTimeIndex`` is first day of the month

        Parameters
        ----------
        cftime_range: CFTimeIndex
            CFTimeIndex containing cftime.datetime objects
        
        Returns
        -------
        list
            list of True or False values
        """
        array = []
        for cftime in cftime_range:
            prev = cftime - td(days=1)
            if prev.month != cftime.month:
                array += [True]
                continue
            array += [False]
        return array

    def _is_month_end(self, cftime_range):
        """Check whether each element of ``CFTimeIndex`` is last day of the month

        Parameters
        ----------
        cftime_range: CFTimeIndex
            CFTimeIndex containing cftime.datetime objects
        
        Returns
        -------
        list
            list of True or False values
        """

        array = []
        for cftime in cftime_range:
            next = cftime + td(days=1)
            if next.month != cftime.month:
                array += [True]
                continue
            array += [False]
        return array

    def date_range_to_frequency_limits(self, start=None,
                                       end=None,
                                       date_range=None,
                                       frequency='mon',
                                       calendar=None,
                                       smonth=[1,2,3,4,5,6,7,8,9,10,11,12],
                                       emonth=[12,11,10,9,8,7,6,5,4,3,2,1],
                                       is_month_start=None,
                                       is_month_end=None):
        """
        Get bounds of CFTimeIndex which satisfy user-given conditions.

        Parameters
        ----------
        start: str, optional
            Left bound for generating dates
        end: str, optional
            Right bound for generating dates
        date_range: CFTimeIndex
            CFTimeIndex containing cftime.datetime objects
        frequency: str ot list, default:'mon'
            CF frequency string or list of CF frequency strings or frequency string or list of frequency strings for use with ``cftime`` calendars
            https://xarray.pydata.org/en/stable/generated/xarray.cftime_range.html
        smonth: list, default: [1,2,3,4,5,6,7,8,9,10,11,12]
            One of the allowed values of left bound's ``datetime.datetime`` instance attribute month 
        emonth: list, default: [12,11,10,9,8,7,6,5,4,3,2,1]
            One of the allowed values of left bound's ``datetime.datetime`` instance attribute month
        is_month_start: bool, optional
            Value of left bound's ``datetime.datetime`` instance attribute day must be equal to first day of the month
            Automatically set to True for sub_monthly frequencies
        is_month_end: bool, optional
            Value of right bound's ``datetime.datetime`` instance attribute day must be equal to last day of the month
           Automatically set to True for sub_monthly frequencies

        Returns
        -------
        tuple
            Tuple of start and end dates satisfying all conditions

        Example
        -------
        To get bounds of CFTimeIndex which satisfy user-given conditions.
        Monthly frequency values with a 360-day calendar have to start with the first month of any season and have to end with the last month of any season.
        It returns the tuple (2005-03-16 00:00:00 2005-11-16 00:00:00)::

            from pyhomogenize import basics

            start, end = basics().date_range_to_frequency_limits(start='2005-01-01',
                                                                 end='2005-12-30',
                                                                 smonth=[3,6,9,12],
                                                                 emonth=[2,5,8,11],
                                                                 calendar='360_day')
      
        """
        if not calendar: calendar = self.calendar
        if isinstance(frequency, str):
            if frequency in consts.frequencies.keys():
                frequency = consts.frequencies[frequency]
        if date_range is None:
            if not start or not end: return None, None
            date_range = self._date_range(start, end, frequency, calendar=calendar)
        start = date_range[0]
        end   = date_range[-1]
        sdate_range = copy.copy(date_range)
        edate_range = copy.copy(date_range)
        if is_month_start is None: is_month_start = consts.is_month[self._get_date_attr(frequency)]
        if is_month_end is None: is_month_start = consts.is_month[self._get_date_attr(frequency)]
        if is_month_start: sdate_range=date_range[self._is_month_start(date_range)]
        if is_month_end: edate_range=date_range[self._is_month_end(date_range)]
        if sdate_range.empty: return None, None
        if edate_range.empty: return None, None
        for sdate in sdate_range:
            if sdate < start: continue
            if sdate.month in smonth: break
            sdate = None
        if not sdate: return None, None
        for edate in reversed(edate_range):
            if edate > end: continue
            if edate.month in emonth: break
            edate=None
        if not edate: return None, None
        return sdate, edate
