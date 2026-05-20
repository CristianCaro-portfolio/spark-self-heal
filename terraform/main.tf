# ---------------------------------------------------------------------------
# S3 BUCKETS
# ---------------------------------------------------------------------------

# Raw zone: JSON crudo de transacciones cae acá
resource "aws_s3_bucket" "raw" {
  bucket = "${var.project_name}-raw-${var.bucket_suffix}"
}

# Bloqueo de acceso público — buena práctica obligatoria
resource "aws_s3_bucket_public_access_block" "raw" {
  bucket = aws_s3_bucket.raw.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Silver zone: Parquet limpios después del Glue Job
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
