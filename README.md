# QGIS Data Sources Panel plugin

This QGIS plugin shows layer data sources in a panel (as table or as
tree grouped by data provider) and offers exporting the information to
CSV/Excel files.

Data source information for each layer is presented as its *data
provider* and its “*storage location*”, i.e. directory+file on the
harddrive or database+schema+table for a PostGIS layer.

This is related to the
“[TocTable](https://github.com/Korto19/TocTable)”
plugin, which produces a static table of the layer data sources with
more details. However,the ”Data Sources Panel” offers an additional
tree view, and both views are dynamic, i. e. they follow changes to
the layers.

This plugin provides a similar experience as the “List by Source“ view
in the ESRI ArcGIS Table of Contents.


## Usage

The panel can be opened from the View menu → Panels → Data Sources.

You can switch between a table view and a tree view of the layer
sources with the first two buttons of the toolbar.

The table can be sorted by layer, data provider and storage location.
Exporting this information as a CSV or Excel file is possible with the
“Save” button on the toolbar.
