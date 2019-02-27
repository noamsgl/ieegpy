##################################################################################
# Copyright 2013-19 by the Trustees of the University of Pennsylvania
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
##################################################################################

import xml.etree.ElementTree as ET
import datetime
import requests
import numpy as np
import pandas as pd
from deprecation import deprecated


class TimeSeriesDetails:
    """
    Metadata on a given time series
    """

    acquisition = ""
    name = ""
    duration = 0.
    channel_label = ""
    min_sample = 0
    max_sample = 0
    number_of_samples = 0
    start_time = 0
    voltage_conversion_factor = 1.

    def __init__(self, name, label, duration, min_sample, max_sample, number_of_samples, start_time, voltage_conversion):
        self.name = name
        self.channel_label = label
        self.duration = float(duration)
        self.min_sample = int(min_sample)
        self.max_sample = int(max_sample)
        self.number_of_samples = int(number_of_samples)
        self.start_time = int(start_time)
        self.voltage_conversion_factor = float(voltage_conversion)
        return

    def __str__(self):
        return self.name + "(" + self.channel_label + ") spans " + \
            str(self.duration) + " usec, range [" + str(self.min_sample) + "-" + \
               str(self.max_sample) + "] in " + str(self.number_of_samples) + \
               str(self.number_of_samples) + " samples.  Starts @" + str(self.start_time) + \
               " with voltage conv factor " + str(self.voltage_conversion_factor)

class Dataset:
    """
    Class representing Dataset on the platform
    """
    snap_id = ""
    ts_details = {} # Time series details
    ch_labels = []  # Channel Labels
    ts_array = []   # Channel
    
    def __init__(self, ts_details, snapshot_id, parent):
        self.session = parent
        self.snap_id = snapshot_id
        details = ts_details.findall('details')[0]  #only one details in timeseriesdetails
        
        for dt in details.findall('detail'):
            ET.dump(dt)
            name = dt.findall('channelLabel')[0].text
            self.ch_labels.append(name)
            self.ts_array.append(dt)
            self.ts_details[name] = TimeSeriesDetails(dt.findall('name')[0].text,
                                                      dt.findall('channelLabel')[0].text,
                                                      dt.findall('duration')[0].text,
                                                      dt.findall('minSample')[0].text,
                                                      dt.findall('maxSample')[0].text,
                                                      dt.findall('numberOfSamples')[0].text,
                                                      dt.findall('startTime')[0].text,
                                                      dt.findall('voltageConversionFactor')[0].text,)
             
    def __repr__(self):
        return "Dataset with: " + str(len(self.ch_labels)) + " channels."
             
    def __str__(self):
        return "Dataset with: " + str(len(self.ch_labels)) + " channels."
            
    def get_channel_labels(self):
        return self.ch_labels

    def get_channel_indices(self, list_of_labels):
        """
        Create a list of indices (suitable for get_data) from a list
        of labels
        :param list_of_labels: Ordered list of channel labels
        :return: Ordered list of channel indices
        """
        return [self.ch_labels.index(x) for x in list_of_labels]

    def get_time_series_details(self, label):
        """
        Get the metadata on a channel

        :param label: Channel label
        :return: object of type TimeSeriesDetails
        """
        return self.ts_details[label]
             
    def get_data(self, start, duration, channels):
        """
        Returns data from the IEEG platform
        :param start: Start time (usec)
        :param duration: Number of usec to request samples from
        :param channels: Integer indices of the channels we want
        :return: 2D array, rows = samples, columns = channels
        """

        def all_same(items):
            return all(x == items[0] for x in items)
        
        # Request location
        get_data_str = "/services/timeseries/getUnscaledTimeSeriesSetBinaryRaw/"

        # Build Data Content XML
        wrapper1 = ET.Element('timeSeriesIdAndDChecks')
        wrapper2 = ET.SubElement(wrapper1, 'timeSeriesIdAndDChecks')
        i=0
        for ts in self.ts_array:
            if i in channels:
                el1 = ET.SubElement(wrapper2, 'timeSeriesIdAndCheck')
                el2 = ET.SubElement(el1, 'dataCheck')
                el2.text = ts.findall('revisionId')[0].text
                el3 = ET.SubElement(el1, 'id')
                el3.text = ts.findall('revisionId')[0].text
            i += 1
            
        data = ET.tostring(wrapper1, encoding="us-ascii", method="xml").decode('utf-8')
        data = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>' + data
        
        # Create request content        
        req_path = get_data_str + self.snap_id
        http_method = "POST"
        params = {'start': start, 'duration': duration}
        payload = self.session.create_ws_header(req_path, http_method, params, data)
        url_str = self.session.url_builder(req_path)
        
        # response to request 
        r = requests.post(url_str, headers=payload, params=params, data=data,verify=False)

        # collect data in numpy array
        d = np.fromstring(r.content, dtype='>i4') 
        h = r.headers

        # Check all channels are the same length
        sample_per_row = [int(numeric_string) for numeric_string in r.headers['samples-per-row'].split(',')]
        if not all_same(sample_per_row):
            raise IeegConnectionError('Not all channels in response have equal length')
            
        conv_f = np.array([float(numeric_string) for numeric_string in r.headers['voltage-conversion-factors-mv'].split(',')])
    
        # Reshape to 2D array and Multiply by conversionFactor
        d2 = np.reshape(d, (-1,len(sample_per_row))) * conv_f[np.newaxis,:]

        return d2

    def get_dataframe(self, start, duration, channels):
        """
        Returns data from the IEEG platform
        :param start: Start time (usec)
        :param duration: Number of usec to request samples from
        :param channels: Integer indices of the channels we want
        :return: dataframe, rows = samples, columns = labeled channels
        """

        array = self.get_data(start, duration, channels)
        return pd.DataFrame(array, columns=[self.ch_labels[i] for i in channels])

    @deprecated
    def getChannelLabels(self):
        return self.get_channel_labels()

    @deprecated
    def getData(self, start, duration, channels):
        return self.get_data(start, duration, channels)


class IeegConnectionError(Exception):
    """
    A simple exception for connectivity errors
    """
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)