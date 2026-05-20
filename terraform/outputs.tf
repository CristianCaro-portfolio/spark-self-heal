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

output "artifacts_bucket_name" {
  description = "Name of the artifacts S3 bucket"
  value       = aws_s3_bucket.artifacts.id
}

output "glue_job_name" {
  description = "Name of the Glue ETL job"
  value       = aws_glue_job.transactions_etl.name
}

output "glue_role_arn" {
  description = "ARN of the IAM role used by the Glue job"
  value       = aws_iam_role.glue_job.arn
}
