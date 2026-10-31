data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

data "aws_ssm_parameter" "amazon_linux" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "pipeline" {
  name               = "seap-lens-pipeline"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

data "aws_iam_policy_document" "pipeline" {
  statement {
    sid       = "ReadWriteProjectBucket"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation", "s3:AbortMultipartUpload"]
    resources = [aws_s3_bucket.data.arn, "${aws_s3_bucket.data.arn}/*"]
  }

  statement {
    sid = "QueryWithAthena"
    actions = [
      "athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults", "athena:StopQueryExecution",
      "athena:GetWorkGroup", "athena:GetDataCatalog", "athena:ListDatabases", "athena:ListTableMetadata",
      "athena:GetDatabase", "athena:GetTableMetadata",
    ]
    resources = ["*"]
  }

  statement {
    sid = "ManageProjectCatalog"
    actions = [
      "glue:GetDatabase", "glue:GetDatabases", "glue:CreateDatabase", "glue:GetTable", "glue:GetTables",
      "glue:CreateTable", "glue:UpdateTable", "glue:DeleteTable", "glue:BatchDeleteTable", "glue:GetPartition",
      "glue:GetPartitions", "glue:BatchCreatePartition", "glue:BatchDeletePartition",
    ]
    resources = [
      "arn:aws:glue:${var.region}:${data.aws_caller_identity.current.account_id}:catalog",
      "arn:aws:glue:${var.region}:${data.aws_caller_identity.current.account_id}:database/seap_lens_*",
      "arn:aws:glue:${var.region}:${data.aws_caller_identity.current.account_id}:table/seap_lens_*/*",
    ]
  }

  statement {
    sid       = "StopItself"
    actions   = ["ec2:StopInstances"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Project"
      values   = ["seap-lens"]
    }
  }
}

resource "aws_iam_role_policy" "pipeline" {
  name   = "pipeline"
  role   = aws_iam_role.pipeline.id
  policy = data.aws_iam_policy_document.pipeline.json
}

# Access goes through Session Manager, so no port is open to the internet.
resource "aws_iam_role_policy_attachment" "session_manager" {
  role       = aws_iam_role.pipeline.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "pipeline" {
  name = "seap-lens-pipeline"
  role = aws_iam_role.pipeline.name
}

resource "aws_security_group" "pipeline" {
  name        = "seap-lens-pipeline"
  description = "Outbound only"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "pipeline" {
  ami                    = data.aws_ssm_parameter.amazon_linux.value
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  iam_instance_profile   = aws_iam_instance_profile.pipeline.name
  vpc_security_group_ids = [aws_security_group.pipeline.id]

  # A shutdown from inside stops the instance, so the data on its disk stays.
  instance_initiated_shutdown_behavior = "stop"
  associate_public_ip_address          = true

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repository_url = var.repository_url
    bucket         = aws_s3_bucket.data.id
    region         = var.region
  })

  metadata_options {
    http_tokens = "required"
    # Containers are one extra network hop away, and need the instance's role.
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 30
    encrypted   = true
  }

  tags = {
    Name = "seap-lens-pipeline"
  }

  # The first boot runs the pipeline, which needs the model and the tables in place.
  depends_on = [aws_s3_object.model, aws_glue_catalog_table.standard, aws_athena_workgroup.main]

  lifecycle {
    ignore_changes = [ami]
  }
}

data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "seap-lens-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler" {
  statement {
    actions   = ["ec2:StartInstances"]
    resources = [aws_instance.pipeline.arn]
  }
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "start-instance"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler.json
}

resource "aws_scheduler_schedule" "monthly_start" {
  name                = "seap-lens-monthly-start"
  schedule_expression = var.start_schedule

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:ec2:startInstances"
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ InstanceIds = [aws_instance.pipeline.id] })
  }
}
