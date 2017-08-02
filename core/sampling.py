# -*- coding: utf-8 -*-
"""
/***************************************************************************
 AcATaMa
                                 A QGIS plugin
 AcATaMa is a Qgis plugin for Accuracy Assessment of Thematic Maps
                              -------------------
        copyright            : (C) 2017 by Xavier Corredor Llano, SMBYC
        email                : xcorredorl@ideam.gov.co
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import random
from datetime import datetime

from qgis.gui import QgsMessageBar
from qgis.utils import iface
from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsGeometry, QgsField, QgsFields, QgsRectangle, QgsSpatialIndex, \
    QgsFeature, QGis
from processing.tools import vector

from AcATaMa.core.point import Point
from AcATaMa.core.raster import Raster
from AcATaMa.core.dockwidget import error_handler, wait_process, load_layer_in_qgis, valid_file_selected_in


@error_handler()
@wait_process('widget_generate_RS.buttonGenerateSampling')
def do_random_sampling(dockwidget):
    # first check input files requirements
    if not valid_file_selected_in(dockwidget.selectThematicRaster, "thematic raster"):
        return
    if dockwidget.groupBox_RSwithCR.isChecked():
        if not valid_file_selected_in(dockwidget.selectCategRaster_RS, "categorical raster"):
            return
    # get and define some variables
    number_of_samples = int(dockwidget.numberOfSamples_RS.value())
    min_distance = int(dockwidget.minDistance_RS.value())

    ThematicR = Raster(file_selected_combo_box=dockwidget.selectThematicRaster,
                       nodata=int(dockwidget.nodata_ThematicRaster.value()))

    # random sampling in categorical raster
    if dockwidget.groupBox_RSwithCR.isChecked():
        CategoricalR = Raster(file_selected_combo_box=dockwidget.selectCategRaster_RS)
        try:
            pixel_values = [int(p) for p in dockwidget.pixelsValuesCategRaster.text().split(",")]
        except:
            iface.messageBar().pushMessage("AcATaMa", "Error, wrong pixel values, set only integers and separated by commas",
                                           level=QgsMessageBar.WARNING, duration=10)
            return
    else:
        CategoricalR = None
        pixel_values = None

    # check neighbors aggregation
    if dockwidget.widget_generate_RS.groupBox_neighbour_aggregation.isChecked():
        number_of_neighbors = int(dockwidget.widget_generate_RS.number_of_neighbors.currentText())
        same_class_of_neighbors = int(dockwidget.widget_generate_RS.same_class_of_neighbors.currentText())
        neighbor_aggregation = (number_of_neighbors, same_class_of_neighbors)
    else:
        neighbor_aggregation = None

    # set the attempts_by_sampling
    if dockwidget.widget_generate_RS.button_attempts_by_sampling.isChecked():
        attempts_by_sampling = int(dockwidget.widget_generate_RS.attempts_by_sampling.value())
    else:
        attempts_by_sampling = None

    # process
    sampling = Sampling("RS", ThematicR, CategoricalR, dockwidget.tmp_dir)
    sampling.generate_sampling_points(pixel_values, number_of_samples, min_distance,
                                      neighbor_aggregation, attempts_by_sampling)

    # success
    if len(sampling.points) == number_of_samples:
        load_layer_in_qgis(sampling.output_file + ".shp", "vector")
        iface.messageBar().pushMessage("AcATaMa", "Generate the random sampling, completed",
                                       level=QgsMessageBar.SUCCESS)
    # success but not completed
    if len(sampling.points) < number_of_samples and len(sampling.points) > 0:
        load_layer_in_qgis(sampling.output_file + ".shp", "vector")
        iface.messageBar().pushMessage("AcATaMa", "Generated the random sampling, but can not generate requested number of "
                                                  "random points {}/{}, attempts exceeded".format(len(sampling.points), number_of_samples),
                                       level=QgsMessageBar.INFO, duration=10)
    # zero points
    if len(sampling.points) < number_of_samples and len(sampling.points) == 0:
        # delete instance where storage all sampling generated
        Sampling.samplings.pop(sampling.sampling_name, None)
        iface.messageBar().pushMessage("AcATaMa", "Error, could not generate any random points with this settings, "
                                                  "attempts exceeded", level=QgsMessageBar.WARNING, duration=10)


@error_handler()
@wait_process('widget_generate_SRS.buttonGenerateSampling')
def do_stratified_random_sampling(dockwidget):
    # first check input files requirements
    if not valid_file_selected_in(dockwidget.selectThematicRaster, "thematic raster"):
        return
    if not valid_file_selected_in(dockwidget.selectCategRaster_SRS, "categorical raster"):
        return
    # get and define some variables
    min_distance = int(dockwidget.minDistance_SRS.value())
    ThematicR = Raster(file_selected_combo_box=dockwidget.selectThematicRaster,
                       nodata=int(dockwidget.nodata_ThematicRaster.value()))
    CategoricalR = Raster(file_selected_combo_box=dockwidget.selectCategRaster_SRS)

    # get values from category table  #########
    pixel_values = []
    number_of_samples = []
    for row in range(dockwidget.TableWidget_SRS.rowCount()):
        pixel_values.append(int(dockwidget.TableWidget_SRS.item(row, 0).text()))
        number_of_samples.append(dockwidget.TableWidget_SRS.item(row, 2).text())
    # convert and check if number of samples only positive integers
    try:
        number_of_samples = [int(ns) for ns in number_of_samples]
        if True in [ns < 0 for ns in number_of_samples]:
            raise
    except:
        iface.messageBar().pushMessage("AcATaMa", "Error, the number of samples should be only positive integers",
                                       level=QgsMessageBar.WARNING, duration=10)
        return
    total_of_samples = sum(number_of_samples)
    if total_of_samples == 0:
        iface.messageBar().pushMessage("AcATaMa", "Error, no number of samples configured!",
                                       level=QgsMessageBar.WARNING, duration=10)
        return

    # check neighbors aggregation
    if dockwidget.widget_generate_SRS.groupBox_neighbour_aggregation.isChecked():
        number_of_neighbors = int(dockwidget.widget_generate_SRS.number_of_neighbors.currentText())
        same_class_of_neighbors = int(dockwidget.widget_generate_SRS.same_class_of_neighbors.currentText())
        neighbor_aggregation = (number_of_neighbors, same_class_of_neighbors)
    else:
        neighbor_aggregation = None

    # set the attempts_by_sampling
    if dockwidget.widget_generate_SRS.button_attempts_by_sampling.isChecked():
        attempts_by_sampling = int(dockwidget.widget_generate_SRS.attempts_by_sampling.value())
    else:
        attempts_by_sampling = None

    # process
    sampling = Sampling("SRS", ThematicR, CategoricalR, dockwidget.tmp_dir)
    sampling.generate_sampling_points(pixel_values, number_of_samples, min_distance,
                                      neighbor_aggregation, attempts_by_sampling)

    # success
    if len(sampling.points) == total_of_samples:
        load_layer_in_qgis(sampling.output_file + ".shp", "vector")
        iface.messageBar().pushMessage("AcATaMa", "Generate the stratified random sampling, completed",
                                       level=QgsMessageBar.SUCCESS)
    # success but not completed
    if len(sampling.points) < total_of_samples and len(sampling.points) > 0:
        load_layer_in_qgis(sampling.output_file + ".shp", "vector")
        iface.messageBar().pushMessage("AcATaMa", "Generated the stratified random sampling, but can not generate requested number of "
                                                  "random points {}/{}, attempts exceeded".format(len(sampling.points), total_of_samples),
                                       level=QgsMessageBar.INFO, duration=10)
    # zero points
    if len(sampling.points) < total_of_samples and len(sampling.points) == 0:
        # delete instance where storage all sampling generated
        Sampling.samplings.pop(sampling.sampling_name, None)
        iface.messageBar().pushMessage("AcATaMa", "Error, could not generate any stratified random points with this settings, "
                                                  "attempts exceeded", level=QgsMessageBar.WARNING, duration=10)


class Sampling():
    # for save all instances
    samplings = dict()  # {name_in_qgis: class instance}

    def __init__(self, sampling_type, ThematicR, CategoricalR, out_dir):
        # set and init variables
        # sampling_type => "RS" (random sampling),
        #                  "SRS" (stratified random sampling)
        self.sampling_type = sampling_type
        self.ThematicR = ThematicR
        self.CategoricalR = CategoricalR

        # set the name and output file
        if self.sampling_type == "RS":
            self.sampling_name = "random_sampling_{}".format(datetime.now().strftime('%H:%M:%S'))
        if self.sampling_type == "SRS":
            self.sampling_name = "stratified_random_sampling_{}".format(datetime.now().strftime('%H:%M:%S'))
        self.output_file = os.path.join(out_dir, self.sampling_name)
        # save instance
        Sampling.samplings[self.sampling_name] = self
        # for save all sampling points
        self.points = dict()

    def generate_sampling_points(self, pixel_values, number_of_samples, min_distance,
                                 neighbor_aggregation, attempts_by_sampling):
        """Some code base from (by Alexander Bruy):
        https://github.com/qgis/QGIS/blob/release-2_18/python/plugins/processing/algs/qgis/RandomPointsExtent.py
        """
        self.pixel_values = pixel_values
        self.number_of_samples = number_of_samples
        self.min_distance = min_distance
        self.neighbor_aggregation = neighbor_aggregation

        xMin, yMax, xMax, yMin = self.ThematicR.extent()
        self.ThematicR_boundaries = QgsGeometry().fromRect(QgsRectangle(xMin, yMin, xMax, yMax))

        fields = QgsFields()
        fields.append(QgsField('id', QVariant.Int, '', 10, 0))
        mapCRS = iface.mapCanvas().mapSettings().destinationCrs()
        writer = vector.VectorWriter(self.output_file, None, fields, QGis.WKBPoint, mapCRS)

        if self.sampling_type == "RS":
            total_of_samples = self.number_of_samples
        if self.sampling_type == "SRS":
            total_of_samples = sum(self.number_of_samples)
            self.nPointsInCategories = [0] * len(self.number_of_samples)

        nPoints = 0
        nIterations = 0
        random.seed()
        total = 100.0 / total_of_samples
        self.index = QgsSpatialIndex()
        if attempts_by_sampling:
            maxIterations = total_of_samples * attempts_by_sampling
        else:
            maxIterations = float('Inf')

        while nIterations < maxIterations and nPoints < total_of_samples:
            rx = xMin + (xMax - xMin) * random.random()
            ry = yMin + (yMax - yMin) * random.random()

            sampling_point = Point(rx, ry)

            # checks to the sampling point, else discard and continue
            if not self.check_sampling_point(sampling_point):
                nIterations += 1
                continue

            f = QgsFeature(nPoints)
            f.initAttributes(1)
            f.setFields(fields)
            f.setAttribute('id', nPoints)
            f.setGeometry(sampling_point.QgsGeom)
            writer.addFeature(f)
            self.index.insertFeature(f)
            self.points[nPoints] = sampling_point.QgsPnt
            nPoints += 1
            nIterations += 1
            if self.sampling_type == "SRS":
                self.nPointsInCategories[sampling_point.index_pixel_value] += 1
            # feedback.setProgress(int(nPoints * total))
        del writer

    def check_sampling_point(self, sampling_point):
        """Make several checks to the sampling point, else discard
        """
        if not sampling_point.in_valid_data(self.ThematicR):
            return False

        if not sampling_point.in_extent(self.ThematicR_boundaries):
            return False

        if not sampling_point.in_mim_distance(self.index, self.min_distance, self.points):
            return False

        if self.sampling_type == "RS":
            if not sampling_point.in_categorical_raster(self.pixel_values, self.CategoricalR):
                return False
        if self.sampling_type == "SRS":
            if not sampling_point.in_stratified_raster(self.pixel_values, self.number_of_samples,
                                                       self.CategoricalR, self.nPointsInCategories):
                return False

        if self.neighbor_aggregation and \
                not sampling_point.check_neighbors_aggregation(self.ThematicR, *self.neighbor_aggregation):
            return False

        return True


