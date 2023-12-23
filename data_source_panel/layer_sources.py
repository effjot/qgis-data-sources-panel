"""Retrieve and process layer data sources"""

from dataclasses import dataclass

from qgis.core import (
    QgsProject,
    QgsProviderRegistry
)


@dataclass
class LayerSource:
    layerid: str
    name: str
    provider: str
    location: str


def get_sources():
    sources = []
    for layerid, layer in QgsProject.instance().mapLayers().items():
        provider = layer.dataProvider().name()
        decoded = QgsProviderRegistry.instance().decodeUri(provider, layer.publicSource())
        if provider == 'postgres':
            location = '{db}: "{schema}"."{table}"'.format(
                db=decoded['dbname'], schema=decoded['schema'], table=decoded['table'])
        elif provider == 'memory':
            location = '(memory)'
        elif 'path' in decoded:
            location = decoded['path']
        else:
            location = '(unknown)'
        sources.append(LayerSource(layerid=layerid, name=layer.name(), provider=provider, location=location))
    return sources

