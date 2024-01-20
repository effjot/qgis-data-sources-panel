"""Retrieve and process layer data sources"""

from dataclasses import astuple, dataclass, fields
from pathlib import Path
from typing import Union

from qgis.core import (
    Qgis,
    QgsField,
    QgsGeometry,
    QgsIconUtils,
    QgsMessageLog,
    QgsProject,
    QgsProviderRegistry,
    QgsVectorLayer,
    QgsVectorLayerUtils
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QIcon

from . import MSG_TAG

# TODO: make this a config option
POSTGRESQL_COMBINE_PROVIDERS = True  # Combine postres and postgresraster as a single provider


@dataclass(frozen=True)  # frozen for hashable class, necessary for set()
class StorageLocation:
    hierarchical: Union[str, tuple[str]] = None
    textual: str = ''

    def is_empty(self):
        return not self.hierarchical

    def is_deep(self):
        return not self.is_empty() and type(self.hierarchical) is tuple

    def __str__(self):
        if self.textual:
            return self.textual
        if self.is_empty():
            return ''
        if self.is_deep():
            return ' '.join(self.hierarchical)
        return self.hierarchical


@dataclass
class LayerSource:
    layerid: str
    name: str
    provider: str
    location: StorageLocation
    icon: QIcon

    def num_fields(self):
        return len(fields(self))

    def by_index(self, index: int):
        if index >= 0 and index < self.num_fields():
            return getattr(self, fields(self)[index].name)


class LayerSources:
    def __init__(self, sources=None):
        self.update(sources)

    def __iter__(self):
        return iter(self.sources)

    def clear(self):
        self.sources = []

    def update(self, sources=None):
        if sources:
            self.sources = sources
        else:
            self.get_sources_from_layers()

    def add_layer(self, layer):
        src = self.get_source_from_layer(layer)
        self.add_source(src)
        return src

    def remove_layer(self, layer):
        src = self.by_layerid(layer.id())
        self.sources.remove(src)
        return src

    def rename_layer(self, layer):
        """Get new name from layer and store it in sources list"""
        src = self.by_layerid(layer.id())
        src.name = layer.name()
        return src

    def change_layer_source(self, layer):
        """Get new data source from layer and store it in sources list"""
        src = self.by_layerid(layer.id())
        index = self.index(src)
        new = self.get_source_from_layer(layer)
        self.sources[index] = new
        return new

    def add_source(self, source: LayerSource):
        self.sources.append(source)

    def get_sources_from_layers(self, layers: dict = None):
        if not layers:
            layers = QgsProject.instance().mapLayers()
        self.clear()
        for layerid, layer in layers.items():
            src = self.get_source_from_layer(layer, layerid)
            self.add_source(src)

    def get_source_from_layer(self, layer, layerid: str = None):
        if not layerid:
            layerid = layer.id()
        provider = layer.dataProvider().name()
        decoded = QgsProviderRegistry.instance().decodeUri(provider, layer.publicSource())
        if provider in ('postgres', 'postgresraster'):
            if POSTGRESQL_COMBINE_PROVIDERS:
                provider = 'postgres'
            db = decoded['dbname']
            schema = decoded['schema']
            table = decoded['table']
            location = StorageLocation(
                ('DB ' + db, 'Schema ' + schema, table),
                f'{db}: "{schema}"."{table}"')
        elif provider == 'memory':
            location = StorageLocation()
        elif 'path' in decoded:
            path = decoded['path']
            hierarchical = Path(path).parts
            if 'layerName' in decoded and decoded['layerName']:
                name = decoded['layerName']
                path += ': ' + name
                hierarchical += (name,)
            location = StorageLocation(hierarchical, path)
        elif 'url' in decoded:
            location = StorageLocation(decoded['url'])
        else:
            location = StorageLocation(None, '(unknown)')
        icon = QgsIconUtils.iconForLayer(
            QgsProject.instance().mapLayer(layerid))
        return LayerSource(
            layerid=layerid, name=layer.name(),
            provider=provider, location=location, icon=icon)

    def num_layers(self) -> int:
        return len(self.sources)

    def num_fields(self) -> int:
        return len(fields(LayerSource))

    def providers(self):
        provs = [s.provider for s in self.sources]
        return list(set(provs))

    def locations(self):
        locs = [s.location for s in self.sources]
        return list(set(locs))

    def index(self, src: LayerSource) -> int:
        """Get index of src in sources"""
        return self.sources.index(src)

    def by_index(self, index: int) -> LayerSource:
        """Get source by index"""
        if index >= 0 and index < self.num_layers():
            return self.sources[index]

    def by_layerid(self, layerid: str):
        layerid_sources = [s for s in self.sources if s.layerid == layerid]
        return layerid_sources[0]  # there should be only one source as ids are unique

    def by_provider(self, provider: str):
        provider_sources = [s for s in self.sources if s.provider == provider]
        return LayerSources(provider_sources)

    def by_location(self, location: str):
        location_sources = [s for s in self.sources if s.location == location]
        return LayerSources(location_sources)

    def as_memory_layer(self, name: str = 'Data Sources'):
        mem_layer = QgsVectorLayer('NoGeometry', name, 'memory')
        prov = mem_layer.dataProvider()
        prov.addAttributes([
            QgsField('layerid', QVariant.String),
            QgsField('Name', QVariant.String),
            QgsField('Provider', QVariant.String),
            QgsField('Storage Location', QVariant.String)
        ])
        mem_layer.updateFields()
        features = [
            QgsVectorLayerUtils.createFeature(
                mem_layer, QgsGeometry(), {
                    0: src.layerid, 1: src.name, 2: nice_provider_name(src.provider),
                    3: str(src.location)
                })
            for src in self.sources
        ]
        prov.addFeatures(features)
        return mem_layer


def nice_provider_name(provider):
    """Nice / properly capitalised provider names. (Couldn’t find API for this.)

    Using function instead of just a dict for easier drop-in replacement
    if I find API for nice provider names.
    """
    names = {
        'ogr': 'OGR',
        'gdal': 'GDAL',
        'wms': 'WMS/WMTS',
        'WFS': 'WFS',
        'postgres': 'PostgreSQL',
        'postgresraster': 'PostgreSQL Raster',
        'spatialite': 'SpatiaLite',
        'memory': 'Memory / Scratch Layer'
    }
    return names.get(provider, provider)


def locations_common_part(locations):
    if not all([loc.is_deep() for loc in locations]):
        return None
    for i, elem in enumerate(locations[0].hierarchical):
        if any([len(loc.hierarchical) <= i or loc.hierarchical[i] != elem
                for loc in locations[1:]]):
            return i
    return None
