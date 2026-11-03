# infra

`main.tf` creates the APIs, the data bucket, the pipeline service account (with its roles) and an empty
Secret Manager secret for the engine API key. It was syntax-checked only; run `terraform validate` and
`terraform plan` before `apply`. Add the secret value yourself (never in Terraform state or git):

    echo -n "THE_KEY" | gcloud secrets versions add fieldshift-api-key --data-file=-

Not included yet: Artifact Registry repository, Cloud Run service for the engine, Vertex schedules.
See docs/runbook.md for the manual steps for those.
