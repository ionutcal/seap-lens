data "aws_caller_identity" "current" {}

locals {
  bucket_name   = "seap-lens-${data.aws_caller_identity.current.account_id}"
  glue_database = "seap_lens_standard"
  glue_columns  = jsondecode(file("${path.module}/../glue_columns.json"))
  # The trained model isn't in Git. The instance needs it to score new notices.
  model_directory = "${path.module}/../../data/model"
}

resource "aws_s3_bucket" "data" {
  bucket = local.bucket_name
  # Everything here can be rebuilt, and the free plan ends by closing the account anyway.
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "expire-query-results"
    status = "Enabled"

    filter {
      prefix = "athena-results/"
    }

    expiration {
      days = 7
    }
  }
}

resource "aws_s3_object" "model" {
  for_each = fileset(local.model_directory, "*")

  bucket = aws_s3_bucket.data.id
  key    = "model/${each.value}"
  source = "${local.model_directory}/${each.value}"
  etag   = filemd5("${local.model_directory}/${each.value}")
}

resource "aws_glue_catalog_database" "standard" {
  name = local.glue_database
}

resource "aws_glue_catalog_table" "standard" {
  for_each = local.glue_columns

  name          = each.key
  database_name = aws_glue_catalog_database.standard.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    classification = "parquet"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data.id}/standard/${each.key}/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    dynamic "columns" {
      for_each = each.value

      content {
        name = columns.key
        type = columns.value
      }
    }
  }
}

resource "aws_athena_workgroup" "main" {
  name          = "seap-lens"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration = true
    # A full rebuild reads well under 1 GB per query, so this only stops a mistake.
    bytes_scanned_cutoff_per_query = 5 * 1024 * 1024 * 1024

    result_configuration {
      output_location = "s3://${aws_s3_bucket.data.id}/athena-results/"
    }
  }
}
