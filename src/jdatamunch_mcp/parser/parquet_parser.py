"""Streaming Parquet parser via PyArrow."""

import os
from pathlib import Path
from typing import Generator

from .normalize import normalize_native
from .types import ColumnInfo, ParsedDataset


def _row_generator(path: str, col_count: int) -> Generator:
    """Yield data rows as lists of strings from a Parquet file."""
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=10_000):
        arrays = [batch.column(i).to_pylist() for i in range(col_count)]
        for row_idx in range(len(batch)):
            yield [
                normalize_native(arrays[col][row_idx], "parquet")
                for col in range(col_count)
            ]


def _arrow_to_logical_type(arrow_type) -> str:
    """Map a PyArrow type to jdatamunch's logical column type (B6).

    Lets index_local skip the 10k-row sample-based type inference when the
    source format already carries authoritative type metadata.
    """
    import pyarrow as pa
    if pa.types.is_integer(arrow_type):
        return "integer"
    if pa.types.is_floating(arrow_type):
        return "float"
    if pa.types.is_timestamp(arrow_type) or pa.types.is_date(arrow_type) or pa.types.is_time(arrow_type):
        return "datetime"
    if pa.types.is_boolean(arrow_type):
        return "string"  # canonical "True"/"False" strings via normalize_native
    return "string"


def parse_parquet(path: str) -> ParsedDataset:
    """Parse a Parquet file and return a streaming ParsedDataset."""
    import pyarrow.parquet as pq

    path = str(Path(path).resolve())
    file_size = os.path.getsize(path)

    pf = pq.ParquetFile(path)
    schema = pf.schema_arrow
    num_rows = pf.metadata.num_rows
    col_count = len(schema)

    columns = [
        ColumnInfo(name=field.name, position=i)
        for i, field in enumerate(schema)
    ]

    # Pushdown (B6): pre-resolved column types from Parquet schema. index_local
    # consumes `column_types` to skip type-inference sampling.
    column_types = [_arrow_to_logical_type(schema.field(i).type) for i in range(col_count)]

    metadata = {
        "encoding": "binary/parquet",
        "delimiter": None,
        "header_row": None,
        "estimated_rows": num_rows,
        "file_size": file_size,
        "parquet_num_row_groups": pf.metadata.num_row_groups,
        "column_types": column_types,
    }

    return ParsedDataset(
        columns=columns,
        row_iterator=_row_generator(path, col_count),
        metadata=metadata,
    )
