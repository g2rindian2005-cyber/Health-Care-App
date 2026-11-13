# database/

The MySQL schema + sample-data SQL files that used to live here were
removed in the DynamoDB migration.

DynamoDB has no schema files: tables are created by Terraform
(`terraform/main.tf` → `aws_dynamodb_table.hospital`) and the sample
data lives as JSON in `backend/db-init-lambda/seed/*.json`, loaded
automatically by the `hospital-db-init-service` Lambda after
`terraform apply` (and after every CI/CD deploy).

Table mapping (old MySQL table → new DynamoDB table):

| MySQL table          | DynamoDB table               |
|----------------------|------------------------------|
| patients             | hospital-patients            |
| doctors              | hospital-doctors             |
| doctor_assignments   | hospital-doctor-assignments  |
| diseases             | hospital-diseases            |
| bills                | hospital-bills               |
| payments             | hospital-payments            |
| lab_tests            | hospital-lab-tests           |
| lab_orders           | hospital-lab-orders          |
| medicines            | hospital-medicines           |
| prescriptions        | hospital-prescriptions       |

See `README.md` (STEP 3–4) for the deploy steps.
