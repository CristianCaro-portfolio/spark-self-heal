variable "aws_region" {
  description = "AWS region where all resources will be created"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile name (from ~/.aws/credentials)"
  type        = string
  default     = "spark-self-heal"
}

variable "project_name" {
  description = "Project identifier, used in resource names and tags"
  type        = string
  default     = "spark-self-heal"
}

variable "environment" {
  description = "Environment name (dev/test/prod)"
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Owner of the resources (for tagging)"
  type        = string
  default     = "cristian"
}

variable "bucket_suffix" {
  description = "Random suffix to make bucket names globally unique"
  type        = string
}
