
import xarray as xr
import datetime
from datetime import timedelta as td
from datetime import datetime as dt
import pandas as pd
import numpy as np
from iteration_utilities import duplicates

from . import consts

class basics():

    def __init__(self):
        self.fmt = '%Y-%m-%dT%H:%M:%S'

    def _convert_to_string(self, values, delim=',',fmt=None):
        converted = ''
        for v in values:
            try:
                v = self._date_to_str(v, fmt=fmt)
            except:
                pass
            converted += str(v) + delim
        return converted[:-1]

    def _dictionary(self, attr, keys, value):
        for key in keys:
            if attr in self.__dict__:
                getattr(self, attr)[key] = value
            else:
                setattr(self, attr, {key : value})

    def _get_key_to_value(self, dict, value):
        key_list = list(dict.keys())
        val_list = list(dict.values())
        position = val_list.index(value)
        return key_list[position]

    def _str_to_date(self, str, mode='start'):
        i=1
        if mode not in ['start', 'end']: return
        while True:
            try:
                if mode == 'start': return dt.strptime(str, self.fmt[:i])
                if mode == 'end'  : return dt.strptime(str, self.fmt[:i]) + td(days=1) - td(seconds=1)
            except:
                i+=1

    def _date_to_str(self, date, fmt=None):
        if not fmt: fmt=self.fmt
        return date.strftime(fmt)

    def _convert_time(self, time):
        try:
            return pd.to_datetime(time.indexes['time'].astype('str'), format=time.units.split(' ')[-1])
        except:
            return time.indexes['time']

    def _equalize_time(self, time, ignore=['second','microsecond','nanosecond']):
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

    def _end_of(self, date, attr):
        while True:
            m  = getattr(date, attr)
            nm = getattr((date + td(hours=1)), attr)
            if nm != m:
                return date
            date += td(hours=1)

    def _begin_of(self, date, attr):
        while True:
            m  = getattr(date, attr)
            pm = getattr((date - td(hours=1)), attr)
            if pm !=m:
                return date
            date -= td(hours=1)

    def _mid_timestep(self, freq, st, end):
        f    = self._get_key_to_value(consts.frequencies, freq)
        attr = consts.translator[f] 
        st  = self._begin_of(st, attr)
        end = self._end_of(end, attr) 
        t1  = xr.cftime_range(st, end, freq=freq[0])
        t2  = xr.cftime_range(st, end, freq=freq[1])
        return t1 + (t2 - t1 + td(days=1)) / 2

    def _point_timestep(self, freq, st, end):
        return xr.cftime_range(st, end, freq=freq)

    def _date_range(self, start, end, frequency):
        function = xr.cftime_range
        if isinstance(frequency, str):
            return self._point_timestep(frequency, start, end)
        if isinstance(frequency, list):
            return self._mid_timestep(frequency, start, end)

    def _is_month_start(self, cftime_range):
        array = []
        for cftime in cftime_range:
            prev = cftime - td(days=1)
            if prev.month != cftime.month:
                array += [True]
                continue
            array += [False]
        return array

    def _is_month_end(self, cftime_range):
        array = []
        for cftime in cftime_range:
            next = cftime + td(days=1)
            if next.month != cftime.month:
                array += [True]
                continue
            array += [False]
        return array 

    def _adjust_time(self, start, end, frequency, smonth=[1], emonth=[12]): 

        date_range = self._date_range(start, end, frequency)
        for start in date_range[self._is_month_start(date_range)]:
            if start.month in smonth:
                break
            start = None
        for end in reversed(date_range[self._is_month_end(date_range)]):
            if end.month in emonth:
                end = self._end_of(end, 'day')
                break
            end = None

        return start, end

class netcdf_basics(basics):

    def __init__(self, files):
        if isinstance(files, str): files = [files]
        self.files = files 
        self.ds    = self.open()
        self.name = self._get_var_name() 

    def _is_dataset(self, input):
        if not isinstance(input, xr.Dataset): input = self.ds
        return input

    def _add_to_attrs(self, target, attr_name, value):
        if attr_name in target.attrs:
            value = target.attrs[attr_name] + ', ' + value
        target.attrs[attr_name] = value 

    def _to_variable_attributes(self, indexes, attr_name):
        var_name = self.name
        if isinstance(indexes, list):
            indexes = str(indexes)
        if indexes:
            for var in var_name:
                self._add_to_attrs(getattr(self.ds, var), attr_name, indexes)
        
    def _to_global_attributes(self, indexes, attr_name):
        if isinstance(indexes, list):
            indexes = str(indexes)
        if indexes:
            self._add_to_attrs(self.ds, attr_name, indexes)

    def _get_var_name(self):
        name = []
        coords = self.ds.coords
        for n in self.ds.data_vars:
            if getattr(self.ds, n).attrs and getattr(self.ds, n).coords: name += [n]
        return name

    def open(self):      

        ds = xr.open_mfdataset(self.files, use_cftime=True, data_vars='minimal', coords='minimal', compat='override', concat_dim='time')
        return ds.sortby('time')

    def write(self, input=None, output=None):
        input = self._is_dataset(input)
        if not output:
            print('No output selected.')
            return
        self._to_variable_attributes(self._convert_to_string(self.files), 'associated_files')
        input.to_netcdf(output)

class time_control(netcdf_basics):

    def __init__(self, files):
        basics.__init__(self)
        netcdf_basics.__init__(self, files)
        self.time        = self._convert_time(self.ds.time)
        self.frequency   = self._get_frequency()
        self.fmt         = consts.format[self.ds.frequency]
        self.equalize    = consts.equalize[self.ds.frequency]

    def _get_frequency(self):
        frequency = xr.infer_freq(self.ds.time)
        if not frequency:
            try:
                frequency = consts.frequencies[self.ds.frequency]
            except:
                print('Could not determine any frequency')
                return
        return frequency

    def _duplicates(self):
        time =  self._equalize_time(self.time, ignore=self.equalize)
        return sorted(list(duplicates(time)))

    def _missings(self):
        time       = self._equalize_time(self.time, ignore=self.equalize)
        date_range = self._equalize_time(self._date_range(time[0], time[-1], self.frequency), ignore=self.equalize)
        return sorted(list(set(date_range).difference(time)))

    def _redundants(self):
        time       = self._equalize_time(self.time, ignore=self.equalize)
        date_range = self._equalize_time(self._date_range(time[0], time[-1], self.frequency), ignore=self.equalize) 
        return sorted(list(set(time).difference(date_range)))

    def _write_timesteps(self, timesteps, naming):
        timesteps = self._convert_to_string(timesteps)
        self._dictionary(naming, self.name, timesteps)
        self._to_variable_attributes(timesteps, naming)

    def get_duplicates(self):
        return self._convert_to_string(self._duplicates())

    def get_missings(self):
        return self._convert_to_string(self._missings())

    def get_redundants(self):
        return self._convert_to_string(self._redundants())
    
    def check_timestamps(self, selection=['duplicates','redundants','missings'], output=None, correct = False):
        if isinstance(selection, str): selection = [selection]
        deletes = []
        time    = self._equalize_time(self.time, ignore=self.equalize)
        for select in selection:
            nmng = consts.naming[select]
            if not select.startswith('_'): select = '_' + select
            add = getattr(self, select)()
            range = np.arange(len(time))
            for a in add:
                loc = [index for index, element in enumerate(time) if element == a][1:]
                deletes += loc
            self._write_timesteps(add, nmng)
        timesteps = [n for n,t in enumerate(time) if n not in list(dict.fromkeys(deletes))]
        if correct: self.ds = self.ds.isel(time=timesteps)
        if not output: return self
        self.write(input=self.ds, output=output)

    def select_range(self, time_range, output=None):
        start_date=time_range[0]
        if not isinstance(start_date, str): 
            start_date = self._date_to_str(start_date)
        end_date=time_range[1]
        if not isinstance(end_date, str):
            end_date = self._date_to_str(end_date)
        self.ds   = self.ds.sel(time=slice(start_date, end_date))
        self.time = self._convert_time(self.ds.time)
        if not output: return self
        self.write(input=self.ds, output=output)

    def within_time_range(self, requested_time_range):
        avail_start = self.time[0]
        avail_end   = self.time[-1]
        req_start   = requested_time_range[0]
        req_end     = requested_time_range[-1]
        if isinstance(req_start, str):
            req_start   = self._str_to_date(req_start, mode='start')
        if isinstance(req_end, str):
            req_end     = self._str_to_date(req_end, mode='end')
        try:
            key = self.ds.frequency
        except:
            key = self._get_key_to_value(consts.frequencies, self.frequency)
        for unit_of_time in consts.within[key]:
            if getattr(avail_start, unit_of_time) > getattr(req_start, unit_of_time):
                return False
            if getattr(avail_start, unit_of_time) == getattr(req_start, unit_of_time):
                continue
            break
        for unit_of_time in consts.within[key]:
            if getattr(avail_end, unit_of_time) < getattr(req_end, unit_of_time):
                return False
            if getattr(avail_end, unit_of_time) == getattr(req_end, unit_of_time):
                continue
            break
            
        return True


class time_compare(basics):

    def __init__(self, list_of_datasets):
        basics.__init__(self)
        self.times    = [ds.time for ds in list_of_datasets]

    def _max_intersection(self):
        start = False
        end   = False
        for time in self.times:
            if not start: start = time[0]
            if not end: end = time[-1]
            if time[0]  > start: start = time[0]
            if time[-1] < end: end = time[-1]
        return start, end

                


