# AWS Runbook

This takes the pipeline from local DuckDB to AWS: S3, Athena, Airflow on EC2, and Terraform. The code has been validated without an account, but **has not yet run on AWS**, so expect to fix some things on the first run.

Create the account only when you can work on this in the following weeks. The free plan ends after six months or when the credits run out, and the account then closes.

## What it costs

Everything draws on the sign-up credit of 100 USD, and the free plan doesn't charge beyond it.

- **EC2:** charged only while running, about two hours a month after the first load.
- **Disk:** the 30 GB volume is charged even while the instance is stopped. This is the main steady cost.
- **Athena:** 5 USD per TB scanned. A full rebuild reads little, since all the standardized data is about 345 MB.
- **S3:** about 3 GB.

Budget alerts fire at 50% and 80% of the credit.

## 1. Create the account

1. Sign up at [aws.amazon.com/free](https://aws.amazon.com/free/) and choose the **Free plan**.
2. Turn on multi-factor authentication for the root user.
3. Create an IAM user for yourself with administrator access and an access key. Don't use the root user's keys.
4. Check that the Free plan lists Athena, EC2, S3, EventBridge and Budgets, and `m7i-flex.large` in `eu-central-1`.

Enter the key on your own machine. Never paste it into a chat, a file in this repository, or a commit:

```bash
aws configure
```

Use `eu-central-1` as the region, then confirm it works:

```bash
aws sts get-caller-identity
```

## 2. Create the infrastructure

The first boot starts the pipeline immediately, so check the plan before applying it.

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Put your email in `terraform.tfvars`, which Git ignores. Then:

```bash
terraform init
terraform plan
terraform apply
```

Confirm the subscription email from AWS, or budget alerts won't arrive.

`data/model` has to exist locally, because Terraform uploads the trained model from there. The Terraform state stays on your machine and Git ignores it.

## 3. Watch the first run

The first run downloads and processes everything, so it takes the longest. The instance stops after 4 hours, whatever happens.

Connect without any open port, using the Session Manager plugin (`brew install --cask session-manager-plugin`):

```bash
aws ssm start-session --target "$(terraform output -raw instance_id)"
```

Boot logs are in `/var/log/cloud-init-output.log`, and the pipeline start is under `journalctl -u seap-lens`. To open the Airflow screen on your machine at `http://localhost:8080`:

```bash
aws ssm start-session --target "$(terraform output -raw instance_id)" --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
```

Take the screenshots for the README here. To keep the instance on after a run, create the hold file from inside the container:

```bash
sudo docker compose -f /opt/seap-lens/infra/airflow/docker-compose.yml exec airflow-scheduler touch /opt/seap/app/data/.hold
```

## 4. Publish a new extract

The pipeline writes the extract to S3 and stops there, so a person checks the numbers before the public dashboard changes. From the repository root:

```bash
aws s3 sync "s3://$(terraform -chdir=infra/terraform output -raw bucket)/exports/dashboard" dashboard/data
```

Review the changes and open a pull request. Streamlit redeploys after the merge.

## 5. Shut it down

When the project is done, or before the free plan ends:

```bash
terraform -chdir=infra/terraform destroy
```

This deletes all the data in the bucket. The dashboard and code keep working, because they don't depend on AWS, and everything can be rebuilt from the repository.
