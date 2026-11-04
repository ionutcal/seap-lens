# AWS Runbook

This takes the pipeline from local DuckDB to AWS: S3, Athena, Airflow on EC2, and Terraform. It has run end to end on a free plan account in `eu-north-1`.

## Result of the first complete run

The run on 2026-11-02 took about 7 minutes once the image was built, and built all 35 dbt steps on Athena. Its dashboard extract matches the local DuckDB warehouse:

- **Awards, labels and suspect contracts:** the same, at 2,177,330, 557,340 and 1,187.
- **Competition by county, CPV group and authority:** identical on every row.
- **Contracted value per year:** the same to one decimal, in billion RON. Contract counts differ by up to 11 and values by up to 3 million RON per row.
- **Median values:** differ by up to about 18,000 RON, because Athena's median is approximate. Treat Athena's medians as estimates.
- **Supplier rankings:** one row of 17,918 differs, in a tie or an arbitrary pick.

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
3. Create an IAM user with administrator access and an access key for the CLI. On the new sign-up these users work only for programmatic access, which is all this needs.
4. Find your region at [settings.aws.com](https://settings.aws.com), under **Project → Overview → Additional Info**. On the new sign-up it is fixed by your contact address, and Europe gets `eu-north-1`, which is this project's default. For another region, add `region = "..."` to `terraform.tfvars` in step 2.

Enter the key on your own machine. Never paste it into a chat, a file in this repository, or a commit:

```bash
aws configure
```

Use your region, then confirm it works:

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

To run the pipeline again in the same month, for example after a fix, remove the monthly marker and reboot. The instance stops after the run, so start it first if needed:

```bash
aws ssm start-session --target "$(terraform output -raw instance_id)"
sudo rm /opt/seap-lens/.last_run && sudo reboot
```

Only stop the instance through the pipeline or the console. `terraform apply` is safe while it's stopped.

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
