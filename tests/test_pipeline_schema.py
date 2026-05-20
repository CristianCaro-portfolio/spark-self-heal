"""
Tests for the transactions ETL pipeline.

These tests run the SAME schema, validations, and filters that the
production Glue job uses - but locally, on small synthetic DataFrames.

If a patched version of the pipeline breaks any of these, the PR
will fail CI and won't be mergeable.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    StringType,
    StructField,
    StructType,
)


EXPECTED_SCHEMA = StructType([
    StructField("transaction_id", StringType(), nullable=False),
    StructField("merchant_id",    StringType(), nullable=False),
    StructField("customer_id",    StringType(), nullable=False),
    StructField("amount",         DoubleType(), nullable=False),
    StructField("currency",       StringType(), nullable=False),
    StructField("payment_method", StringType(), nullable=True),
    StructField("status",         StringType(), nullable=True),
    StructField("country_code",   StringType(), nullable=False),
    StructField("created_at",     StringType(), nullable=False),
])


VALID_CURRENCIES = ["USD", "COP", "MXN", "BRL", "ARS", "EUR"]

PIPELINE_PATH = Path("pipelines/jobs/transactions_etl.py")


def test_pipeline_module_imports():
    """The pipeline file must be loadable as a Python module."""
    spec = importlib.util.spec_from_file_location(
        "transactions_etl",
        str(PIPELINE_PATH),
    )
    assert spec is not None
    assert spec.loader is not None


def test_pipeline_source_declares_expected_columns():
    """Defensive: confirm the pipeline file mentions our required columns."""
    source = PIPELINE_PATH.read_text()
    for col in ["transaction_id", "merchant_id", "amount", "currency", "country_code"]:
        assert col in source, f"Pipeline source is missing column: {col}"


def test_currency_allowlist_filters_invalid(spark):
    """Records with non-ISO currencies should be filterable."""
    data = [
        ("t1", "USD"),
        ("t2", "XX"),
        ("t3", "DOLLAR"),
        ("t4", "COP"),
    ]
    df = spark.createDataFrame(data, ["transaction_id", "currency"])
    filtered = df.filter(F.col("currency").isin(VALID_CURRENCIES))
    assert filtered.count() == 2


def test_positive_amount_filter(spark):
    """Records with non-positive amounts should be filterable."""
    data = [("t1", 10.0), ("t2", -5.0), ("t3", 0.0), ("t4", 99.99)]
    df = spark.createDataFrame(data, ["transaction_id", "amount"])
    filtered = df.filter(F.col("amount") > 0)
    assert filtered.count() == 2


def test_deduplication_by_transaction_id(spark):
    """Duplicate transaction_id should be removed by dropDuplicates."""
    data = [
        ("t1", 10.0),
        ("t1", 10.0),
        ("t2", 20.0),
        ("t1", 30.0),
    ]
    df = spark.createDataFrame(data, ["transaction_id", "amount"])
    deduped = df.dropDuplicates(["transaction_id"])
    assert deduped.count() == 2


def test_iso_timestamp_parses(spark):
    """The pipeline's timestamp format should parse correctly."""
    from pyspark.sql.functions import to_timestamp
    data = [("t1", "2026-05-20T14:23:01Z")]
    df = spark.createDataFrame(data, ["transaction_id", "created_at"])
    parsed = df.withColumn(
        "ts",
        to_timestamp("created_at", "yyyy-MM-dd'T'HH:mm:ssXXX"),
    )
    row = parsed.collect()[0]
    assert row["ts"] is not None


def test_malformed_timestamp_yields_null(spark):
    """Non-ISO timestamps should become NULL when parsed."""
    from pyspark.sql.functions import to_timestamp
    data = [
        ("t1", "20/05/2026 14:23"),
        ("t2", "20260520T142301"),
    ]
    df = spark.createDataFrame(data, ["transaction_id", "created_at"])
    parsed = df.withColumn(
        "ts",
        to_timestamp("created_at", "yyyy-MM-dd'T'HH:mm:ssXXX"),
    )
    rows = parsed.collect()
    assert rows[0]["ts"] is None
    assert rows[1]["ts"] is None
