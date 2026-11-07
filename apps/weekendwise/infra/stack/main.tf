# WeekendWise stack: resources inside the project.
#
# Added by later stories:
#   iam.tf        IAC-03  service accounts and least-privilege IAM (built)
#   firestore.tf  IAC-04  Firestore (default) database and vector index (built)
#   registry.tf   IAC-05  Artifact Registry (built)
#   run.tf        IAC-05  Cloud Run service (built)
#
# The project data source is used for outputs and to prove the remote state
# backend and credentials work.

data "google_project" "this" {
  project_id = var.project_id
}
