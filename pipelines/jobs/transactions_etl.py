"""
spark-self-heal :: transactions_etl
====================================

Reads raw transaction JSONL from s3://<raw-bucket>/transactions/
and writes cleaned Parquet to s3://<silver-bucket>/transactions/,
partitioned by country_code and ingestion date.

The job is INTENTIONALLY brittle on several axes — those failure
modes are what the self-healing agent (see Phase 4) learns to diagnose.
The full catalog lives in docs/failure-modes.md.

Expected Glue Job arguments:
    --JOB_NAME              <auto-injected by Glue>
    --raw_bucket            spark-self-heal-raw-<suffix>
    --silver_bucket         spark-self-heal-silver-<suffix>
    --database_name         spark_self_heal_dev
    --table_name            transactions
    --source_prefix         transactions/                 (S3 prefix under raw bucket)
"""

import sys
from datetime import datetime, timezone

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# ---------------------------------------------------------------------------
# 1) Bootstrap Glue context
# ---------------------------------------------------------------------------

args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "raw_bucket",
        "silver_bucket",
        "database_name",
        "table_name",
        "source_prefix",
    ],
)

sc = SparkContext.getOrCreate()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

print(f"[ETL] job started: {args['JOB_NAME']}")
print(f"[ETL] raw    = s3://{args['raw_bucket']}/{args['source_prefix']}")
print(f"[ETL] silver = s3://{args['silver_bucket']}/transactions/")

# ---------------------------------------------------------------------------
# 2) Explicit schema (defensive: rejects shape drift at read time)
# ---------------------------------------------------------------------------

TRANSACTION_SCHEMA = StructType([
    StructField("transaction_id", StringType(), nullable=False),
    StructField("merchant_id",    StringType(), nullable=False),
    StructField("customer_id",    StringType(), nullable=False),
    StructField("amount",         DoubleType(), nullable=False),
    StructField("currency",       StringType(), nullable=False),
    StructField("payment_method", StringType(), nullable=True),
    StructField("status",         StringType(), nullable=True),
    StructField("country_code",   StringType(), nullable=False),
    StructField("created_at",     StringType(), nullable=False),  # parsed below
])

VALID_CURRENCIES = ["USD", "COP", "MXN", "BRL", "ARS", "EUR"]

# ---------------------------------------------------------------------------
# 3) Read raw JSONL with explicit schema
# ---------------------------------------------------------------------------

raw_path = f"s3://{args['raw_bucket']}/{args['source_prefix']}"

raw_df: DataFrame = (
    spark.read
    .schema(TRANSACTION_SCHEMA)
    .option("mode", "FAILFAST")        # fails on records that don't match schema
    .json(raw_path)
)

raw_count = raw_df.count()
print(f"[ETL] read {raw_count} raw records")

if raw_count == 0:
    raise RuntimeError(f"No records found at {raw_path} — empty partition?")

# ---------------------------------------------------------------------------
# 4) Transformations + validations
# ---------------------------------------------------------------------------

cleaned_df = (
    raw_df
    # Parse timestamp — only ISO 8601 with Z suffix. Others become NULL.
    .withColumn(
        "created_at_ts",
        F.to_timestamp("created_at", "yyyy-MM-dd'T'HH:mm:ssXXX"),
    )
    # Validate currency against allow-list
    .withColumn(
        "currency_valid",
        F.col("currency").isin(VALID_CURRENCIES),
    )
    # Reject negative amounts (refunds should come with status='refunded' + positive amount)
    .withColumn(
        "amount_valid",
        F.col("amount") > 0,
    )
)

# Hard filter: drop anything that failed validation
clean_count_before = cleaned_df.count()

cleaned_df = cleaned_df.filter(
    F.col("created_at_ts").isNotNull()
    & F.col("currency_valid")
    & F.col("amount_valid")
)

clean_count_after = cleaned_df.count()
dropped = clean_count_before - clean_count_after

print(f"[ETL] dropped {dropped} invalid records ({dropped/clean_count_before:.1%})")

if clean_count_after == 0:
    raise RuntimeError("All records filtered out — pipeline is producing zero output")

# ---------------------------------------------------------------------------
# 5) Deduplicate by transaction_id (keep first occurrence)
# ---------------------------------------------------------------------------

before_dedup = clean_count_after
deduplicated_df = cleaned_df.dropDuplicates(["transaction_id"])
after_dedup = deduplicated_df.count()
duplicates = before_dedup - after_dedup

if duplicates > 0:
    print(f"[ETL] removed {duplicates} duplicate transaction_id(s)")

# ---------------------------------------------------------------------------
# 6) Final shape + partition columns
# ---------------------------------------------------------------------------

ingestion_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

final_df = (
    deduplicated_df
    .drop("created_at", "currency_valid", "amount_valid")
    .withColumnRenamed("created_at_ts", "created_at")
    .withColumn("ingestion_date", F.lit(ingestion_date))
)

# ---------------------------------------------------------------------------
# 7) Write Parquet partitioned, registered in Glue Catalog
# ---------------------------------------------------------------------------

output_path = f"s3://{args['silver_bucket']}/transactions/"

(
    final_df.write
    .mode("append")
    .partitionBy("country_code", "ingestion_date")
    .parquet(output_path)
)

print(f"[ETL] wrote {after_dedup} records to {output_path}")
print(f"[ETL] partitioned by country_code, ingestion_date={ingestion_date}")

# ---------------------------------------------------------------------------
# 8) Commit (releases Glue bookmark, marks job successful)
# ---------------------------------------------------------------------------

job.commit()
print("[ETL] job committed successfully")
