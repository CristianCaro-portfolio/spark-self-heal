output "raw_bucket_name" {
  description = "Name of the raw S3 bucket"
  value       = aws_s3_bucket.raw.id
}

output "silver_bucket_name" {
  description = "Name of the silver S3 bucket"
  value       = aws_s3_bucket.silver.id
}

output "glue_database_name" {
  description = "Name of the Glue Catalog database"
  value       = aws_glue_catalog_database.transactions.name
}
