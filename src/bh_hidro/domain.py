"""Download domain. CDS area is [latmax, lonmin, latmin, lonmax]."""

# lonmin, lonmax, latmin, latmax
ARG_PAR_URU = [-73.75, -52.75, -56.0, -19.0]


def cds_area(bounds: list[float] | None = None) -> list[float]:
    lonmin, lonmax, latmin, latmax = bounds or ARG_PAR_URU
    return [latmax, lonmin, latmin, lonmax]
