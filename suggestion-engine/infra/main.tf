# Minimal Google Cloud setup for Field Shift: APIs, a data bucket, a pipeline service account and its roles.
# NOT validated with `terraform validate` in the development sandbox (Terraform was not available there):
# run `terraform init && terraform validate && terraform plan` before applying.
terraform {
  required_version = ">= 1.5"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
}

variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "asia-south1"
}
variable "bucket_suffix" {
  type    = string
  default = "dev"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  apis = [
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudbuild.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "data" {
  name                        = "${var.project_id}-fieldshift-${var.bucket_suffix}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false
  depends_on                  = [google_project_service.apis]
}

resource "google_service_account" "pipelines" {
  account_id   = "fieldshift-pipelines"
  display_name = "Field Shift Vertex pipelines"
}

resource "google_project_iam_member" "pipelines_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/secretmanager.secretAccessor",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.pipelines.email}"
}

resource "google_storage_bucket_iam_member" "pipelines_bucket" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipelines.email}"
}

resource "google_secret_manager_secret" "api_key" {
  secret_id = "fieldshift-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

output "bucket" { value = google_storage_bucket.data.url }
output "pipeline_service_account" { value = google_service_account.pipelines.email }
