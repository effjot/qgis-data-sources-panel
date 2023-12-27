"""Retrieve and process layer data sources"""

from dataclasses import astuple, dataclass, fields
from typing import Union

from qgis.core import (
    QgsProject,
    QgsProviderRegistry
)


@dataclass(frozen=True)  # frozen for hashable class, necessary for set()
class StorageLocation:
    hierarchical: Union[str, list[str]] = None
    textual: str = ''

    def __str__(self):
        if self.textual:
            return self.textual
        if type(self.hierarchical) is str:
            return self.hierarchical
        if not self.hierarchical:
            return ''
        return ' '.join(self.hierarchical)


@dataclass
class LayerSource:
    layerid: str
    name: str
    provider: str
    location: StorageLocation

    def num_fields(self):
        return len(fields(self))

    def by_index(self, index: int):
        if index >= 0 and index < self.num_fields():
            return getattr(self, fields(self)[index].name)


class LayerSources:
    def __init__(self, sources=None):
        if sources:
            self.sources = sources
        else:
            self.get_sources(QgsProject.instance().mapLayers())

    def __iter__(self):
        return iter(self.sources)

    def clear(self):
        self.sources = []

    def add_source(self, source: LayerSource):
        self.sources.append(source)

    def get_sources(self, layers: dict):
        self.clear()
        for layerid, layer in layers.items():
            provider = layer.dataProvider().name()
            decoded = QgsProviderRegistry.instance().decodeUri(provider, layer.publicSource())
            if provider == 'postgres':
                db = decoded['dbname']
                schema = decoded['schema']
                table = decoded['table']
                location = StorageLocation(
                    (db, schema, table),
                    f'{db}: "{schema}"."{table}"')
            elif provider == 'memory':
                location = StorageLocation()
            elif 'path' in decoded:
                location = StorageLocation(decoded['path'])
#            elif 'url' in decoded:
#                location = StorageLocation(decoded['url'])
            else:
                location = StorageLocation(None, '(unknown)')
            self.add_source(LayerSource(
                layerid=layerid, name=layer.name(),
                provider=provider, location=location))

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

    def by_index(self, index: int) -> LayerSource:
        if index >= 0 and index < self.num_layers():
            return self.sources[index]

    def by_layerid(self, layerid: str):
        pass

    def by_provider(self, provider: str):
        provider_sources = [s for s in self.sources if s.provider == provider]
        return LayerSources(provider_sources)

    def by_location(self, location: str):
        location_sources = [s for s in self.sources if s.location == location]
        return LayerSources(location_sources)
