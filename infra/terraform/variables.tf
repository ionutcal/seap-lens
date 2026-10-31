variable "region" {
  description = "AWS region for every resource."
  type        = string
  default     = "eu-central-1"
}

variable "alert_email" {
  description = "Address that receives budget alerts. It has to confirm the subscription."
  type        = string
}

variable "budget_usd" {
  description = "Monthly budget that the alerts refer to, set to the sign-up credit."
  type        = number
  default     = 100
}

variable "instance_type" {
  description = "Airflow needs at least 4 GB. This type is on the free plan and has 8 GB."
  type        = string
  default     = "m7i-flex.large"
}

variable "repository_url" {
  description = "Public repository the instance runs the pipeline from."
  type        = string
  default     = "https://github.com/ionutcal/seap-lens.git"
}

variable "start_schedule" {
  description = "When the instance starts each month, in UTC."
  type        = string
  default     = "cron(0 6 2 * ? *)"
}
