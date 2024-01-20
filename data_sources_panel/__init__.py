"""
/***************************************************************************
 DataSourcesPanel
                                 A QGIS plugin
 Panel with overview of layer data sources
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2023-12-23
        copyright            : (C) 2023 by Florian Jenn
        email                : devel@effjot.net
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


MSG_TAG = 'Data Sources Panel'  # tag for log messages and message bar


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load DataSourcesPanel class from file data_sources_panel.py.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .data_sources_panel import DataSourcesPanel
    return DataSourcesPanel(iface)
