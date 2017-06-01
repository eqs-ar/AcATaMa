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
import tempfile

from PyQt4 import QtGui, uic
from PyQt4.QtCore import pyqtSignal, Qt, pyqtSlot
from qgis.utils import iface
from qgis.gui import QgsMessageBar

from AcATaMa.core.sampling import do_random_sampling_in_extent, do_random_sampling_in_shape
from AcATaMa.core.utils import do_clipping_with_shape, get_current_file_path_in, error_handler, \
    wait_process, load_layer_in_qgis, update_layers_list, unload_layer_in_qgis, get_layer_by_name

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'acatama_dockwidget_base.ui'))


class AcATaMaDockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(AcATaMaDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.canvas = iface.mapCanvas()
        self.setupUi(self)
        self.setup_gui()
        # tmp dir for all process and intermediate files
        self.tmp_dir = tempfile.mkdtemp()

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def setup_gui(self):
        # plugin info #########

        # load thematic raster image #########
        update_layers_list(self.selectThematicRaster, "raster")
        # handle connect when the list of layers changed
        self.canvas.layersChanged.connect(lambda: update_layers_list(self.selectThematicRaster, "raster"))
        # call to browse the thematic raster file
        self.browseThematicRaster.clicked.connect(lambda: self.fileDialog_browse(
            self.selectThematicRaster,
            dialog_title=self.tr(u"Select the thematic raster image to evaluate"),
            dialog_types=self.tr(u"Raster files (*.tif *.img);;All files (*.*)"),
            layer_type="raster"))

        # shape study area #########
        self.widget_ShapeArea.setHidden(True)
        update_layers_list(self.selectShapeArea, "vector")
        # handle connect when the list of layers changed
        self.canvas.layersChanged.connect(lambda: update_layers_list(self.selectShapeArea, "vector"))
        # call to browse the shape area
        self.browseShapeArea.clicked.connect(lambda: self.fileDialog_browse(
            self.selectShapeArea,
            dialog_title=self.tr(u"Select the shape file"),
            dialog_types=self.tr(u"Shape files (*.shp);;All files (*.*)"),
            layer_type="vector"))
        # do clip
        self.buttonClipping.clicked.connect(self.clipping_thematic_raster)

        # create categorical  ######### TODO
        self.widget_CategRaster.setHidden(True)
        # update_layers_list(self.selectCategRaster, "raster")
        # # handle connect when the list of layers changed
        # self.canvas.layersChanged.connect(lambda: update_layers_list(self.selectCategRaster, "raster"))
        # # call to browse the categorical raster
        # self.browseCategRaster.clicked.connect(lambda: self.fileDialog_browse(
        #     self.selectCategRaster,
        #     dialog_title=self.tr(u"Select the categorical raster file"),
        #     dialog_types=self.tr(u"Raster files (*.tif *.img);;All files (*.*)"),
        #     layer_type="raster"))

        # random sampling #########
        self.widget_RSwithCR.setHidden(True)
        update_layers_list(self.selectCategRaster_RS, "raster")
        # handle connect when the list of layers changed
        self.canvas.layersChanged.connect(lambda: update_layers_list(self.selectCategRaster_RS, "raster"))
        # call to browse the categorical raster
        self.browseCategRaster_RS.clicked.connect(lambda: self.fileDialog_browse(
            self.selectCategRaster_RS,
            dialog_title=self.tr(u"Select the categorical raster file"),
            dialog_types=self.tr(u"Raster files (*.tif *.img);;All files (*.*)"),
            layer_type="raster"))
        # generate sampling
        self.buttonGenerateRSampling.clicked.connect(self.generate_random_sampling)

        # stratified random sampling #########


    @pyqtSlot()
    def fileDialog_browse(self, combo_box, dialog_title, dialog_types, layer_type):
        file_path = str(QtGui.QFileDialog.getOpenFileName(self, dialog_title, "", dialog_types))
        if file_path != '' and os.path.isfile(file_path):
            # load to qgis and update combobox list
            filename = load_layer_in_qgis(file_path, layer_type)
            update_layers_list(combo_box, layer_type)
            selected_index = combo_box.findText(filename, Qt.MatchFixedString)
            combo_box.setCurrentIndex(selected_index)

    @pyqtSlot()
    @error_handler()
    @wait_process()
    def clipping_thematic_raster(self):
        clip_file = do_clipping_with_shape(
            get_current_file_path_in(self.selectThematicRaster),
            get_current_file_path_in(self.selectShapeArea), self.tmp_dir)
        # unload old thematic file
        unload_layer_in_qgis(get_current_file_path_in(self.selectThematicRaster))
        # load to qgis and update combobox list
        filename = load_layer_in_qgis(clip_file, "raster")
        update_layers_list(self.selectThematicRaster, "raster")
        selected_index = self.selectThematicRaster.findText(filename, Qt.MatchFixedString)
        self.selectThematicRaster.setCurrentIndex(selected_index)

        iface.messageBar().pushMessage("Done", "Clipping the thematic raster with shape, completed",
                                       level=QgsMessageBar.SUCCESS)

    @pyqtSlot()
    def generate_random_sampling(self):

        if self.groupBox_RSwithCR.isChecked():
            #         not self.groupBox_StratifiedSampling.isChecked():
            #     iface.messageBar().pushMessage("Error", "Please select and config one sampling method",
            #                                    level=QgsMessageBar.WARNING)
            #     return
            pass
        else:
            pass

        if self.tab_SamplingStrategy.currentIndex() == 0:  # tab points count
            number_of_samples = int(self.numberOfSamples_RS.value())
            min_distance = int(self.minDistance_RS.value())

            if self.groupBox_ShapeArea.isChecked():
                # make random sampling inside the shape area
                do_random_sampling_in_shape(self, number_of_samples, min_distance,
                                            get_layer_by_name(self.selectShapeArea.currentText()))
            else:
                # make random sampling in thematic raster extent
                do_random_sampling_in_extent(self)

        if self.tab_SamplingStrategy.currentIndex() == 1:  # tab points density
            pass