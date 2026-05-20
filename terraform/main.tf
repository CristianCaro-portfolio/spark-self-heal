# ---------------------------------------------------------------------------
# S3 BUCKETS
# ---------------------------------------------------------------------------

# Raw zone: landing area for incoming JSON transaction events
resource "aws_s3_bucket" "raw" {
  bucket = "${var.project_name}-raw-${var.bucket_suffix}"
}

# Public access block — mandatory baseline for any bucket holding data
resource "aws_s3_bucket_public_access_block" "raw" {
  bucket = aws_s3_bucket.raw.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Silver zone: cleaned Parquet output from the Glue Job
resource "aws_s3_bucket" "silver" {
  bucket = "${var.project_name}-silver-${var.bucket_suffix}"
}

resource "aws_s3_bucket_public_access_block" "silver" {
  bucket = aws_s3_bucket.silver.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# GLUE DATA CATALOG
# ---------------------------------------------------------------------------

resource "aws_glue_catalog_database" "transactions" {
  name        = replace("${var.project_name}_${var.environment}", "-", "_")
  description = "Catalog database for fintech transactions pipeline"
}

# ---------------------------------------------------------------------------
# ARTIFACTS BUCKET (Glue scripts, temp files, drivers)
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project_name}-artifacts-${var.bucket_suffix}"
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# IAM ROLE for Glue Job
# ---------------------------------------------------------------------------

# Trust policy: Glue service is allowed to assume this role
data "aws_iam_policy_document" "glue_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue_job" {
  name               = "${var.project_name}-glue-job-role"
  assume_role_policy = data.aws_iam_policy_document.glue_trust.json
}

# AWS-managed policy with broad Glue permissions
resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_job.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Inline policy: read raw, write silver, read scripts from artifacts
data "aws_iam_policy_document" "glue_s3_access" {
  statement {
    sid = "ReadRawBucket"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.raw.arn,
      "${aws_s3_bucket.raw.arn}/*",
    ]
  }

  statement {
    sid = "WriteSilverBucket"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.silver.arn,
      "${aws_s3_bucket.silver.arn}/*",
    ]
  }

  statement {
    sid = "ReadArtifactsBucket"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
      "s3:PutObject", # for temp files Glue writes
    ]
    resources = [
      aws_s3_bucket.artifacts.arn,
      "${aws_s3_bucket.artifacts.arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "glue_s3" {
  name   = "${var.project_name}-glue-s3-access"
  role   = aws_iam_role.glue_job.id
  policy = data.aws_iam_policy_document.glue_s3_access.json
}

# ---------------------------------------------------------------------------
# GLUE JOB
# ---------------------------------------------------------------------------

resource "aws_glue_job" "transactions_etl" {
  name              = "${var.project_name}-transactions-etl"
  role_arn          = aws_iam_role.glue_job.arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 10 # minutes — fail fast if it hangs

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.artifacts.id}/jobs/transactions_etl.py"
    python_version  = "3"
  }

  default_arguments = {
    "--JOB_NAME"                         = "${var.project_name}-transactions-etl"
    "--raw_bucket"                       = aws_s3_bucket.raw.id
    "--silver_bucket"                    = aws_s3_bucket.silver.id
    "--database_name"                    = aws_glue_catalog_database.transactions.name
    "--table_name"                       = "transactions"
    "--source_prefix"                    = "transactions/"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--job-language"                     = "python"
    "--TempDir"                          = "s3://${aws_s3_bucket.artifacts.id}/tmp/"
  }
}
