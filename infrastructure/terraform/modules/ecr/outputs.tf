###############################################################################
# ECR Module Outputs
###############################################################################

output "repository_uri" {
  description = "URI of the ECR repository"
  value       = aws_ecr_repository.main.repository_url
}

output "repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.main.arn
}

output "registry_id" {
  description = "AWS account ID owning the ECR repository"
  value       = aws_ecr_repository.main.registry_id
}

output "repository_name" {
  description = "Name of the ECR repository"
  value       = aws_ecr_repository.main.name
}
