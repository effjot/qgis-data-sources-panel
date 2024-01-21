"""Utility functions for Data Sources Panel plugin"""

# Copyright (C) 2024 by Florian Jenn

from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtWidgets import QApplication


def tr(message):
    """Get translation for text; QTranslator must be set up in plugin initialisation

    We implement this ourselves since we do not inherit QObject.

    :param message: String for translation.
    :type message: str, QString

    :returns: Translated version of message.
    :rtype: QString
    """
    return QApplication.translate('@default', message)


MSG_TAG = tr('Data Sources Panel')  # tag for log messages and message bar


def log(message: str):
    """Send message to Qgis Message Log, masking HTML entities"""
    escaped = message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    QgsMessageLog.logMessage(escaped, MSG_TAG, Qgis.Info)
