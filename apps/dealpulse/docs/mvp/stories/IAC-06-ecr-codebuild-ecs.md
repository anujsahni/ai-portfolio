# IAC-06 — ECR, CodeBuild and private ECS service (Terraform)

**Type:** Infrastructure as code + deployment  
**Priority:** P0  
**Estimate:** 6–9 hours  
**Story points:** 5 (registry, remote build, Fargate service with ECS Exec, private tunnel and pause/resume)  

## User story

As the demo owner, I want the app built remotely and run as a private container that only I can reach through a tunnel so that the demo is hosted on AWS without exposing anything to the internet or paying for a load balancer.

## Scope

- **ECR** repository `dealpulse`: scan on push, immutable tags, lifecycle rule keeping the last 10 images.
- **CodeBuild** project (role `dealpulse-build`, small Linux instance): source is a zip uploaded to S3 by `make build`; `buildspec.yml` runs the offline tests, then builds and pushes the image tagged with the git SHA.
- **ECS**:
  - cluster `dealpulse` with Container Insights off (cost);
  - task definition: 0.5 vCPU, 1 GB, Linux/x86_64, task role `dealpulse-run`, execution role `dealpulse-task-exec`, port 8501, environment from stack outputs (no secrets), `awslogs` driver to `/dealpulse/app` with 14-day retention;
  - service: desired count 1, public subnet with a public IP for outbound calls, the no-inbound security group, `enable_execute_command = true`, deployment circuit breaker with rollback;
  - variable `image_tag` drives deploys.
- **Make targets:** `build` (zip, upload, start CodeBuild, wait, print tag), `deploy IMAGE=<tag>` (Terraform apply with the tag), `release` (test → build → deploy), `images`, `proxy` (SSM port forwarding from `localhost:8502` to the task's 8501 via `AWS-StartPortForwardingSession`), `pause` / `resume` (desired count 0 / 1).
- Write guide 06 (ECS deployment and the private tunnel).

**Out of scope:** load balancers, custom domains, TLS certificates, Cognito login, autoscaling, blue/green deploys and Fargate Spot.

## Acceptance criteria

- [ ] `make build` produces an image in ECR via CodeBuild without Docker on the operator's machine; a failing test stops the build.
- [ ] `make deploy IMAGE=<tag>` rolls out the task; a second plan shows no changes.
- [ ] The task has no inbound route: a direct request to its public IP on 8501 times out.
- [ ] `make proxy` opens the app at `http://localhost:8502` and Streamlit's live connection works through the tunnel.
- [ ] `make pause` brings running tasks to 0 and `make resume` back to 1.
- [ ] Deploying an earlier tag rolls back (rehearsed once).
- [ ] Logs appear in CloudWatch with 14-day retention.

## Dependencies and deliverables

**Dependencies:** IAC-03.  
**Deliverables:** `ecr.tf`, `codebuild.tf`, `ecs.tf`, `buildspec.yml`, make targets, guide 06.

## Completion evidence

Build log summary, deployed tag, proxy session check, pause/resume output and the rollback rehearsal.
