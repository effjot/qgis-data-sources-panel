# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DataSourceDockWidget
                                 A QGIS plugin
 Panel with overview of layer data sources
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2023-12-23
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Florian Jenn
        email                : devel@effjot.net
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
from functools import partial
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsLayerTree,
    QgsMessageLog,
    QgsProject,
    QgsProviderRegistry,
    QgsSettings,
    QgsVectorFileWriter
)
from qgis.PyQt import QtCore, QtWidgets, uic
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QAction, QFileDialog

from . import MSG_TAG
from .layer_sources import LayerSources, nice_provider_name

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'dockwidget.ui'))


class SourcesTableModel(QtCore.QAbstractTableModel):
    def __init__(self, data: LayerSources):
        super().__init__()
        self._data = data
        self._header = ['Layer', 'Provider', 'Storage Location']

    def data(self, index, role):
        if role == Qt.DisplayRole:
            src = self._data.by_index(index.row())
            item = src.by_index(index.column() + 1)  # skip layerid field
            if index.column() == 1:
                return nice_provider_name(item)
            return str(item)
        if role == Qt.DecorationRole:
            if index.column() == 0:
                return self._data.by_index(index.row()).icon  # icon field

    def rowCount(self, index):
        return self._data.num_layers()

    def columnCount(self, index):
        return self._data.num_fields() - 2  # skip layerid, icon fields

    def headerData(self, index, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self._header[index]

    def add_source_begin(self):
        self.layoutChanged.emit()
    def add_source_end(self, src):
        self.layoutChanged.emit()

    def remove_source_begin(self, src):
        self.layoutAboutToBeChanged.emit()
    def remove_source_end(self):
        self.layoutChanged.emit()

    def rename_layer(self, src):
        row = self._data.index(src)
        self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [Qt.DisplayRole])

    def change_layer_source(self, src):
        row = self._data.index(src)
        self.dataChanged.emit(self.index(row, 1), self.index(row, 2), [Qt.DisplayRole])

    def update(self):
        self.get_icons()
        self.layoutChanged.emit()


# FIXME: Tree model is too complicated. Try to generate return values on the fly from LayerSources

class TreeItem():
    """Item in simple tree data structure from https://doc.qt.io/qtforpython-5/overviews/qtwidgets-itemviews-simpletreemodel-example.html#simple-tree-model-example"""
    def __init__(self, data, data_type=None, parent=None):
        self.parent_item = parent
        self.children = []
        self._data = data
        self._icon = None
        self.layerid = None
        if data_type == 'provider':
            self._icon = QgsProviderRegistry.instance().providerMetadata(
                data).icon()
            self._data = nice_provider_name(data)
        elif data_type == 'location':
            self._icon = None
        elif data_type == 'layer':
            self._icon = data.icon
            self._data = data.name
            self.layerid = data.layerid
        self.data_type = data_type

    def append_child(self, item):
        self.children.append(item)

    def insert_in_tree(self, item, where=None, insert_if_exists=True):
        if not where:
            exists = self.child_by_data(item.data())
            if exists and not insert_if_exists:
                return exists
            item.parent_item = self
            self.append_child(item)
            return item
        insert_at = where[0]
        if insert_at not in [c.data() for c in self.children]:
            new_child = TreeItem(insert_at, item.data_type, parent=self)
            self.append_child(new_child)
        row = [c.data() for c in self.children].index(insert_at)
        return self.child(row).insert_in_tree(item, where[1:], insert_if_exists)

    def remove_child(self, item):
        self.children.remove(item)

    def remove_children(self):
        if not self.children:
            return None
        for child in self.children:
            child.remove_children()
        self.children = []

    def child(self, row):
        return self.children[row]

    def child_by_data(self, data):
        children_data = [c.data() for c in self.children]
        if data in children_data:
            return self.child(children_data.index(data))
        else:
            return None

    def child_count(self):
        return len(self.children)

    def column_count(self):  # at the moment no columns used
        return 1

    def data(self, column=None):  # at the moment no columns used
        return self._data

    def set_data(self, data):
        self._data = data

    def parent(self):
        return self.parent_item

    def row(self):
        """Row number of item for non-toplevel items; 0 for toplevel items"""
        if self.parent_item:
            return self.parent_item.children.index(self)
        return 0

    def icon(self):
        return self._icon


class SourcesTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, data: LayerSources):
        super().__init__()
        self._data = data  # original / “flat” data
        self.root_item = TreeItem('Data Sources', parent=None)
        self.setup_model_tree(data)

    def clear(self):
        self.root_item.remove_children()

    def data(self, index, role):
        if not index.isValid():
            return None
        item = index.internalPointer()
        if role == Qt.DisplayRole:
            return item.data()  # at the moment no columns used
        if role == Qt.DecorationRole:
            return item.icon()
        if role == Qt.UserRole:
            return item.layerid
        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()
        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()
        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()
        child_item = index.internalPointer()
        parent_item = child_item.parent()
        if parent_item == self.root_item:
            return QtCore.QModelIndex()
        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()
        return parent_item.child_count()

    def columnCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().column_count()
        else:
            return self.root_item.column_count()

    # FIXME: factor out common code from setup_model_tree, add_source, remove_source

    def setup_model_tree(self, data):
        self.clear()
        providers = data.providers()
        for prov in providers:
            prov_item = TreeItem(prov, 'provider', self.root_item)
            self.root_item.append_child(prov_item)
            prov_sources = data.by_provider(prov)
            locations = prov_sources.locations()
            # loc_common = locations_common_part(locations)  # FIXME: for no, skip flattening common parts; first, get adding and removing right
            for loc in locations:
                if loc.is_empty():
                    loc_item = prov_item
                elif loc.is_deep():
                    loc_item = TreeItem(str(loc.hierarchical[-1]),
                                        'location', parent=None)
                    # if loc_common and prov in ('ogr', 'gdal'):
                    #     common_part = str(
                    #         Path().joinpath(*loc.hierarchical[:loc_common]))
                    #     remainder = loc.hierarchical[loc_common:-1]
                    #     where = (common_part,) + remainder
                    # else:
                    where = loc.hierarchical[:-1]
                    prov_item.insert_in_tree(loc_item, where)
                else:
                    loc_item = TreeItem(str(loc), 'location', prov_item)
                    prov_item.append_child(loc_item)
                sources = prov_sources.by_location(loc)
                for src in sources:
                    src_item = TreeItem(src, 'layer', loc_item)
                    loc_item.append_child(src_item)

    def add_source_begin(self):
        self.layoutAboutToBeChanged.emit()

    def add_source_end(self, src):
        prov = src.provider
        prov_item = self.root_item.child_by_data(nice_provider_name(prov))
        if not prov_item:
            prov_item = TreeItem(prov, 'provider', self.root_item)
            self.root_item.append_child(prov_item)
        # prov_sources = self._data.by_provider(prov)
        # locations = prov_sources.locations()
        # loc_common = locations_common_part(locations)  # FIXME: handle case with new common_part
        loc = src.location
        if loc.is_empty():
            loc_item = prov_item
        elif loc.is_deep():
            loc_item = TreeItem(str(loc.hierarchical[-1]),
                                'location', parent=None)
            # if loc_common and prov in ('ogr', 'gdal'):
            #     common_part = str(
            #         Path().joinpath(*loc.hierarchical[:loc_common]))
            #     remainder = loc.hierarchical[loc_common:-1]
            #     where = (common_part,) + remainder
            # else:
            where = loc.hierarchical[:-1]
            loc_item = prov_item.insert_in_tree(loc_item, where, insert_if_exists=False)
        else:
            loc_item = prov_item.child_by_data(str(loc))
            if not loc_item:
                loc_item = TreeItem(str(loc), 'location', prov_item)
            prov_item.append_child(loc_item)
        src_item = TreeItem(src, 'layer', loc_item)
        loc_item.append_child(src_item)
        self.layoutChanged.emit()

    def remove_source_begin(self, src):
        self.layoutAboutToBeChanged.emit()
        prov = src.provider
        prov_item = self.root_item.child_by_data(nice_provider_name(prov))
        # prov_sources = self._data.by_provider(prov)
        # locations = prov_sources.locations()
        # loc_common = locations_common_part(locations)
        loc = src.location
        if loc.is_empty():
            loc_item = prov_item
        elif loc.is_deep():
            # if loc_common and prov in ('ogr', 'gdal'):
            #     common_part = str(
            #         Path().joinpath(*loc.hierarchical[:loc_common]))
            #     remainder = loc.hierarchical[loc_common:]
            #     where = (common_part,) + remainder
            # else:
            where = loc.hierarchical
            loc_item = prov_item
            for node in where:
                loc_item = loc_item.child_by_data(node)
        else:
            loc_item = prov_item.child_by_data(str(loc))
        src_item = loc_item.child_by_data(src.name)
        loc_item.remove_child(src_item)

    def remove_source_end(self):
        self.layoutChanged.emit()

    def rename_layer(self, src):
        matching_indexes = self.match(self.index(0, 0, QtCore.QModelIndex()), Qt.UserRole,
                                      src.layerid, 1, Qt.MatchRecursive)
        if matching_indexes:
            index = matching_indexes[0]
            index.internalPointer().set_data(src.name)
            self.dataChanged.emit(index, index, [Qt.DisplayRole])

    def update(self):
        self.beginResetModel()
        self.setup_model_tree(self._data)
        self.endResetModel()


class DataSourceDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super().__init__(parent)
        self.iface = iface
        self.proj = QgsProject.instance()

        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://doc.qt.io/qt-5/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # Layout like QGIS/src/gui/qgsbrowserwidget.cpp and QGIS/src/ui/qgsbrowserwidgetbase.u
        self.vertical_layout.setContentsMargins(0, 0, 0, 0)
        self.vertical_layout.setSpacing(0)

        # Toolbar
        self.act_tableview = QAction(
            QgsApplication.getThemeIcon('/mActionOpenTable.svg'),
            '&Table View', self)
        self.act_treeview = QAction(
            QgsApplication.getThemeIcon('/mIconTreeView.svg'),
            'T&ree View', self)
        self.act_expandall = QAction(
            QgsApplication.getThemeIcon('mActionExpandTree.svg'),
            '&Expand All', self)
        self.act_collapseall = QAction(
            QgsApplication.getThemeIcon('mActionCollapseTree.svg'),
            '&Collapse All', self)
        self.act_export = QAction(
            QgsApplication.getThemeIcon('mActionFileSave.svg'),
            'E&xport', self)
        self.act_tableview.setCheckable(True)
        self.act_treeview.setCheckable(True)
        self.act_tableview.setChecked(True)
        self.act_expandall.setEnabled(False)
        self.act_collapseall.setEnabled(False)
        self.act_tableview.triggered.connect(self.show_table)
        self.act_treeview.triggered.connect(self.show_tree)
        self.act_expandall.triggered.connect(self.v_sources_tree.expandAll)
        self.act_collapseall.triggered.connect(self.v_sources_tree.collapseAll)
        self.act_export.triggered.connect(self.export_xlsx)
        self.toolbar.addAction(self.act_tableview)
        self.toolbar.addAction(self.act_treeview)
        self.toolbar.addAction(self.act_expandall)
        self.toolbar.addAction(self.act_collapseall)
        self.toolbar.addAction(self.act_export)

        # Data sources display
        self.sources = LayerSources()
        self.table_model = SourcesTableModel(self.sources)
        self.proxy_model = QtCore.QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.v_sources_table.setSortingEnabled(True)
        self.v_sources_table.setModel(self.proxy_model)
        self.tree_model = SourcesTreeModel(self.sources)
        self.v_sources_tree.setHeaderHidden(True)
        self.v_sources_tree.setModel(self.tree_model)

        # Listen to layer changes
        self.proj.layersAdded.connect(self.add_layers)
        self.proj.layersWillBeRemoved.connect(self.remove_layers)
        self.proj.layerTreeRoot().nameChanged.connect(self.rename_layer)
        for layer in self.proj.mapLayers().values():
            layer.dataSourceChanged.connect(partial(self.change_layer_source, layer))

    def show_table(self):
        self.act_tableview.setChecked(True)
        self.act_treeview.setChecked(False)
        self.act_expandall.setEnabled(False)
        self.act_collapseall.setEnabled(False)
        self.stk_sourcesview.setCurrentIndex(0)

    def show_tree(self):
        self.act_tableview.setChecked(False)
        self.act_treeview.setChecked(True)
        self.act_expandall.setEnabled(True)
        self.act_collapseall.setEnabled(True)
        self.stk_sourcesview.setCurrentIndex(1)

    def update_models(self):
        self.sources.update()
        self.table_model.update()
        self.tree_model.update()

    def add_layers(self, layers):
        for layer in layers:
            self.table_model.add_source_begin()
            self.tree_model.add_source_begin()
            src = self.sources.add_layer(layer)
            self.table_model.add_source_end(src)
            self.tree_model.add_source_end(src)
            layer.dataSourceChanged.connect(partial(self.change_layer_source, layer))

    def remove_layers(self, layerids):
        for layerid in layerids:
            src = self.sources.by_layerid(layerid)
            self.table_model.remove_source_begin(src)
            self.tree_model.remove_source_begin(src)
            self.sources.remove_layer(QgsProject.instance().mapLayer(layerid))
            self.table_model.remove_source_end()
            self.tree_model.remove_source_end()

    def rename_layer(self, node, name):
        if not QgsLayerTree.isLayer(node):
            return
        layer = node.layer()
        src = self.sources.rename_layer(layer)
        self.table_model.rename_layer(src)
        self.tree_model.rename_layer(src)

    def change_layer_source(self, layer):
        new = self.sources.change_layer_source(layer)
        self.table_model.change_layer_source(new)

    def export_xlsx(self):
        mem_layer = self.sources.as_memory_layer()
        # self.proj.addMapLayer(mem_layer)  # for testing
        file_path = (Path(QgsSettings().value("UI/lastFileNameWidgetDir"))
                     / f'{mem_layer.name()}.xlsx')
        output_file, _ = QFileDialog.getSaveFileName(
            self, 'Export Data Sources Table as Excel workbook',
            str(file_path), 'Excel workbook (*.xlsx)'
        )
        if not output_file:
            self.iface.messageBar().pushMessage(
                MSG_TAG, 'Export cancelled', level=Qgis.Info
            )
            return
        save_options = QgsVectorFileWriter.SaveVectorOptions()
        save_options.fileEncoding = "UTF-8"
        save_options.driverName = 'XLSX'
        error, message, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
            mem_layer, output_file,
            QgsProject.instance().transformContext(),
            save_options)
        if error == QgsVectorFileWriter.NoError:
            self.iface.messageBar().pushMessage(
                MSG_TAG, f'Data sources table successfully exported to {output_file}',
                level=Qgis.Success
            )
        else:
            self.iface.messageBar().pushMessage(
                MSG_TAG, f'Export to {output_file} failed: {error} {message}',
                level=Qgis.Critical
            )

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()
