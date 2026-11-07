# project_id and region are written to bootstrap.auto.tfvars.json by `make bootstrap`.

variable "project_id" {
  description = "Project created by infra/bootstrap."
  type        = string
}

variable "region" {
  description = "Region created by infra/bootstrap."
  type        = string
}

variable "operator_principals" {
  description = "People allowed to impersonate the WeekendWise service accounts, e.g. [\"user:you@example.com\"]. `make` fills this from your gcloud account."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for p in var.operator_principals : can(regex("^(user|group|serviceAccount):[^@\\s]+@[^@\\s]+$", p))])
    error_message = "Each operator must look like user:you@example.com, group:team@example.com, or serviceAccount:x@y.iam.gserviceaccount.com."
  }
}

variable "embedding_dimension" {
  description = "Vector size of the embedding model (MVP-02: gemini-embedding-001 at 768). Must equal VERTEX_EMBEDDING_DIMENSION in .env."
  type        = number
  default     = 768

  validation {
    condition     = var.embedding_dimension >= 1 && var.embedding_dimension <= 2048 && floor(var.embedding_dimension) == var.embedding_dimension
    error_message = "embedding_dimension must be a whole number from 1 to 2048 (Firestore's maximum)."
  }
}

variable "firestore_location" {
  description = "Firestore location. Defaults to the project region. Can't be changed after creation."
  type        = string
  default     = null
}

variable "firestore_delete_protection" {
  description = "Block deletion of the Firestore database. Only the destroy commands set this to false."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------- IAC-05: registry and Cloud Run

variable "image" {
  description = "Container image Cloud Run runs. `make deploy` sets this (image.auto.tfvars.json); until the first build, Google's public placeholder is used."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "max_instances" {
  description = "Upper bound on Cloud Run instances (cost and abuse control). Min is always 0 (scale to zero)."
  type        = number
  default     = 2

  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 5 && floor(var.max_instances) == var.max_instances
    error_message = "max_instances must be a whole number from 1 to 5."
  }
}

variable "allow_unauthenticated" {
  description = "Make the service public (allUsers can invoke). Default false. Read the cost and abuse warning in guide 00 before enabling."
  type        = bool
  default     = false
}

variable "cloud_run_deletion_protection" {
  description = "Block deletion of the Cloud Run service. Only the destroy commands set this to false."
  type        = bool
  default     = true
}

variable "registry_keep_count" {
  description = "How many recent images the registry keeps; older ones are cleaned up automatically."
  type        = number
  default     = 10
}

variable "app_env" {
  description = "Non-secret app settings passed to Cloud Run as environment variables (mirror of .env)."
  type        = map(string)
  default = {
    VERTEX_GENERATION_MODEL_ID = "gemini-3.8-flash"
    VERTEX_GENERATION_LOCATION = "global"
    VERTEX_THINKING_LEVEL      = "LOW"
    VERTEX_EMBEDDING_MODEL_ID  = "gemini-embedding-001"
    MAX_PROMPT_CHARS           = "24000"
    MAX_OUTPUT_TOKENS          = "4096"
    REQUEST_TIMEOUT_SECONDS    = "45"
    MODEL_RETRY_ATTEMPTS       = "1"
    SUPPORTED_CITY_IDS         = "san-francisco,portland,santa-cruz,napa-valley"
    RETRIEVAL_TOP_K            = "4"
    RETRIEVAL_MAX_TOP_K        = "5"
    RETRIEVAL_MAX_DISTANCE     = "0.34"
    FIRESTORE_TIMEOUT_SECONDS  = "10"
    PLAN_MAX_CONCURRENT        = "3"
    PLAN_RATE_PER_CLIENT       = "6"
    PLAN_DAILY_LIMIT           = "30"
    LOG_LEVEL                  = "INFO"
  }
}
