'''
 Copyright 2019 Trustees of the University of Pennsylvania

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
'''
import math as m
import datetime

from ieeg.mprov_listener import MProvWriter, AnnotationActivity
from ieeg.processing import Window


class SlidingWindowAnnotator:

    def __init__(self,
                 window_size_usec,
                 slide_usec,
                 annotator_function,
                 mprov_connection=None):
        self.window_size_usec = window_size_usec
        self.slide_usec = slide_usec
        self.annotator_function = annotator_function
        self.mprov_writer = MProvWriter(
            mprov_connection) if mprov_connection else None

    def annotate_dataset(self,
                         dataset,
                         annotation_layer,
                         start_time_usec=None,
                         duration_usec=None,
                         input_channel_labels=None):
        if input_channel_labels is None:
            input_channel_labels = dataset.get_channel_labels()
        if start_time_usec is None:
            start_time_usec = 0
        if duration_usec is None:
            duration_usec = dataset.end_time - dataset.start_time

        input_channel_indices = dataset.get_channel_indices(
            input_channel_labels)
        if self.mprov_writer:
            self.mprov_writer.write_input_channel_entities(
                dataset, input_channel_labels)

        annotations = []

        for window_index in range(0, int(m.ceil(duration_usec / self.slide_usec))):
            window_start_usec = start_time_usec + window_index * self.slide_usec
            data_block = dataset.get_data(window_start_usec,
                                          self.window_size_usec,
                                          input_channel_indices)
            print(data_block.shape)
            window = Window(dataset, input_channel_labels, data_block,
                            window_index, window_start_usec, self.window_size_usec)
            activity_start_time = datetime.datetime.now(datetime.timezone.utc)
            new_annotation = self.annotator_function(
                window, annotation_layer)
            activity_end_time = datetime.datetime.now(datetime.timezone.utc)
            if new_annotation:
                annotations.append(new_annotation)
            if self.mprov_writer:
                activity = AnnotationActivity(
                    self.annotator_function.__name__, annotation_layer, window_index,
                    activity_start_time, activity_end_time)
                self.mprov_writer.write_widow_prov(
                    window, activity, new_annotation)

        dataset.add_annotations(annotations)
        return annotations
