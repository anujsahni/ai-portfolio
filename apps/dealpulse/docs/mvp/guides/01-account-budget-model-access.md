# 01 — AWS account, budget and Bedrock model access

A console reference for checking what DealPulse needs at the account level. Terraform creates the budget ([guide 00](00-provision-with-terraform.md)); the steps here are the few things only the account owner can do. AWS console labels change over time; if a label below doesn't match, search for the service name.

## 1. Sign in

DealPulse's `make` commands use the AWS profile in `AWS_PROFILE` (default: `default`).

```bash
aws sts get-caller-identity          # shows the account and who you are
make tools                           # checks tools and sign-in together
```

Short-lived sign-in (`aws sso login --profile <name>`) is safer than an IAM user's long-lived access keys. Both work; switching later needs no code change.

## 2. Budget

Created by `make bootstrap`: `<prefix>-monthly`, $60/month, alerts at 50/80/100% actual and 100% forecast, counting only resources tagged `app=dealpulse`. Check it in **Billing and Cost Management → Budgets** or with `make verify`. A budget **alerts only**; it never stops spending.

## 3. Bedrock model access

DealPulse uses two models in `us-east-1`:

| Model | Used for | How it's called |
|---|---|---|
| **Claude Opus 5.5** (`anthropic.claude-opus-5-5`) | Deal briefs and follow-up answers | Through Bedrock's **Messages endpoint** `https://bedrock-mantle.us-east-1.api.aws/anthropic/v1/messages` (Anthropic's Python SDK: `AnthropicBedrockMantle`). IAM action: `bedrock-mantle:CreateInference`. The older `Converse`/`InvokeModel` APIs cover Claude Opus 4.6 and earlier. |
| **Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`) | Turning text into vectors | Directly (on-demand) |

### Check access (read-only, free)

```bash
aws bedrock get-foundation-model-availability --region us-east-1 --model-id anthropic.claude-opus-5-5
aws bedrock get-foundation-model-availability --region us-east-1 --model-id amazon.titan-embed-text-v2:0
```

Look for `"authorizationStatus": "AUTHORIZED"` and `"agreementAvailability": {"status": "AVAILABLE"}`.

### First-time Anthropic access (owner action, once per account)

An account that has never used Anthropic models on Bedrock must submit Anthropic's **use-case form** first. It asks for your company name, website, industry and intended use, and is submitted in the account owner's name, so DealPulse's scripts don't fill it in.

1. Open the **Amazon Bedrock console** in **US East (N. Virginia)**.
2. Go to **Model catalog**, filter by provider **Anthropic**, and open **Claude Opus 5.5**.
3. Choose the option to request access or **submit use case details**, complete the form and submit. Approval is usually immediate.
4. Confirm from the terminal: `aws bedrock get-use-case-for-model-access --region us-east-1` returns the form instead of "You have not filled out the request form."

The first call to the model then accepts Anthropic's AWS Marketplace offer for the account automatically (this needs the `aws-marketplace:Subscribe` permission, which the operator has). Afterwards `agreementAvailability` shows `AVAILABLE`. There's no subscription fee; you pay per token.

#### Checking Claude access from the terminal

```bash
eval "$(aws configure export-credentials --format env)"
curl -sS https://bedrock-mantle.us-east-1.api.aws/anthropic/v1/messages \
  --aws-sigv4 "aws:amz:us-east-1:bedrock-mantle" -u "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" \
  ${AWS_SESSION_TOKEN:+-H "x-amz-security-token: $AWS_SESSION_TOKEN"} \
  -H "content-type: application/json" -H "anthropic-version: 2026-10-21" \
  -d '{"model":"anthropic.claude-opus-5-5","max_tokens":32,"messages":[{"role":"user","content":"Reply: ok"}]}'
```

A working account returns a message; a blocked one returns `permission_error … is not available for this account`.

## Common problems

| Message | Meaning | Fix |
|---|---|---|
| `You have not filled out the request form` | Anthropic use-case form not submitted | Step 3 above |
| `ValidationException … on-demand throughput isn't supported` | Called the bare model ID | Use the inference profile `us.anthropic.claude-opus-5-5` |
| `AccessDeniedException … aws-marketplace` | The caller can't accept the Marketplace offer | Make the first call as the operator (not the app role) |
| `ResourceNotFoundException` for a model | Wrong region | Use `us-east-1` |
| `… is not available for this account` for **every** Claude model, including ones open to all customers (Opus 4.8, Sonnet 5) | The account has no AWS Marketplace agreement with Anthropic yet, and Bedrock won't create one on first call. Seen on this account right after the use-case form was submitted (2026-11-09). | Wait 15–30 minutes and retry. Then: in the Bedrock console's model catalog, open the model and accept the offer if a button is shown; check Billing → Payment preferences has a valid payment method (Marketplace purchases need one); otherwise open an AWS Support case (Billing / Account) quoting the request ID. |
