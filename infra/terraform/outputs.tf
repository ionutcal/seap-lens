output "bucket" {
  value = aws_s3_bucket.data.id
}

output "instance_id" {
  value = aws_instance.pipeline.id
}
