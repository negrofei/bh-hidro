import pytest

from bh_hidro.config import Settings
from bh_hidro.db.tables import OPERATIVE_TABLES, REFERENCE_TABLES


def test_reference_and_operative_are_disjoint():
    assert set(REFERENCE_TABLES).isdisjoint(OPERATIVE_TABLES)
    assert len(REFERENCE_TABLES) == len(set(REFERENCE_TABLES))
    assert len(OPERATIVE_TABLES) == len(set(OPERATIVE_TABLES))


def test_reference_tables_are_mapped():
    from bh_hidro.db.base import Base
    from bh_hidro.db import models as _models  # noqa: F401

    names = set(Base.metadata.tables)
    assert set(REFERENCE_TABLES) <= names
    assert set(OPERATIVE_TABLES) <= names
    assert names == set(REFERENCE_TABLES) | set(OPERATIVE_TABLES)


def test_refuse_copy_onto_same_database():
    from bh_hidro.db.bootstrap import copy_reference_tables

    settings = Settings(
        database_host="127.0.0.1",
        database_port=3308,
        database_name="fdc_database",
        source_database_name="fdc_database",
    )
    with pytest.raises(ValueError, match="refusing"):
        import asyncio

        asyncio.run(copy_reference_tables(settings, dry_run=True))


def test_refuse_copy_across_instances():
    from bh_hidro.db.bootstrap import copy_reference_tables

    settings = Settings(
        database_host="127.0.0.1",
        database_port=3308,
        source_database_host="127.0.0.1",
        source_database_port=3309,
        database_name="bh_hidro",
        source_database_name="fdc_database",
    )
    with pytest.raises(ValueError, match="misma instancia"):
        import asyncio

        asyncio.run(copy_reference_tables(settings, dry_run=True))
