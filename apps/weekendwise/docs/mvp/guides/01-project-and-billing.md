# Setup guide 01 — Google Cloud project, billing, APIs, and budget

**Related story:** [MVP-01](../stories/MVP-01-project-billing-guardrails.md)
**Who runs it:** the demo owner (needs a Google account that can create projects and use a billing account)
**Time:** about 30–45 minutes, plus any wait for billing or permission approval
**Result:** a dedicated `weekendwise-demo` project with billing linked, six APIs enabled, a monthly budget with alerts, and a private `.env` record

> **Provisioning is automated.** Create, change, and delete these resources only with Terraform; see [how-to 00](00-provision-with-terraform.md) (IAC-01, IAC-02). This guide is kept as a console reference for understanding and inspecting what Terraform created. Making changes here by hand causes drift.

These console steps describe exactly what `make bootstrap` automates, so you can inspect each item or understand a failure. Console labels change from time to time; if a label differs, look for the closest match and note it in the [reviewer log](#step-9--reviewer-walkthrough).

> ⚠️ **Cost warning.** Linking a billing account lets the project incur charges. A budget **only sends alerts; it does not stop spending.** Keep usage small and shut the project down when the demo is no longer needed (Step 10).

---

## Step 0 — Check you have what you need (5 min)

| You need | How to check |
|---|---|
| A Google account you control (personal or work) | You can sign in at [console.cloud.google.com](https://console.cloud.google.com). |
| Permission to create projects | Personal accounts can by default. Work accounts may need the **Project Creator** role from an admin. |
| A billing account you are allowed to use | Open **☰ Navigation menu → Billing**. You should see at least one billing account. To link it you need **Billing Account User** on it (or be its administrator). |
| Permission to create budgets | Needs **Billing Account Administrator** or **Billing Account Costs Manager** on the billing account. |
| A budget amount you are comfortable with | Example: **$20/month**. |

If any check fails, stop and ask the account/billing admin for the role before continuing. New Google Cloud users may be offered a free trial with credits; check the current terms on the sign-up page rather than relying on this guide.

Open a private notes file now. You will fill in `.env` in Step 7.

---

## Step 1 — Create the dedicated project (5 min)

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. In the top bar, click the **project picker** (the drop-down next to the Google Cloud logo).
3. Click **New project**.
4. Fill in the form:
   - **Project name:** `WeekendWise Demo`
   - **Project ID:** click **Edit** and enter `weekendwise-demo` (or `weekendwise-demo-<suffix>` if taken). 6–30 characters, lowercase letters, numbers, and hyphens, starting with a letter. **It can't be changed later.**
   - **Organization / Location:** keep the default (your organization, or *No organization* for a personal account).
5. Click **Create** and wait for the notification (under a minute).
6. Open the project picker again and **select the new project**. Confirm its ID appears in the top bar.

✍️ Write down the **project ID** (not the display name).

---

## Step 2 — Link billing (5 min)

1. With the new project selected, open **☰ Navigation menu → Billing**.
2. If you see *"This project has no billing account"*, click **Link a billing account**.
3. Choose the billing account you're allowed to use and click **Set account**.
4. Confirm the Billing page now shows the project linked to that account.

Alternative path: **Billing → Account management → My projects** tab → find the project → **⋮ Actions → Change billing**.

🔒 Do **not** record the billing account ID or payment details in the repository.

---

## Step 3 — Choose the region (5 min)

The region isn't a single project setting; it's a value you choose once and reuse for every later resource (Vertex AI, Cloud Run, Firestore, Artifact Registry).

1. Start with the candidate **`us-central1`**.
2. Confirm the Gemini and text-embedding models you plan to use (Guide 02) are available there: see [Generative AI on Vertex AI locations](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations), or open **☰ → Vertex AI → Model Garden** and check the model's supported regions.
3. Confirm Cloud Run and Firestore support the same region (both support `us-central1` at the time of writing; recheck the product location pages).
4. If any of these isn't available, choose another region that supports all of them.

✍️ Write down the **region**.

---

## Step 4 — Enable only the required APIs (5–10 min)

1. With the project selected, open **☰ → APIs & Services → Library**.
2. For each API below: search the name, open it, click **Enable**, wait for it to finish, then go back to the Library.

| Search for | Service name | Used by |
|---|---|---|
| Vertex AI API | `aiplatform.googleapis.com` | MVP-02 (Gemini + embeddings) |
| Cloud Firestore API | `firestore.googleapis.com` | MVP-04, MVP-05 |
| Cloud Run Admin API | `run.googleapis.com` | MVP-03 |
| Cloud Build API | `cloudbuild.googleapis.com` | MVP-03 |
| Artifact Registry API | `artifactregistry.googleapis.com` | MVP-03 |
| Cloud Logging API | `logging.googleapis.com` | MVP-09 (often already on) |

3. If the console asks to enable a dependent API while enabling one of these (for example, Vertex AI can prompt for related services), accept it. Don't enable anything else "just in case."
4. Open **☰ → APIs & Services → Enabled APIs & services** and confirm all six are listed.

New projects may have a few APIs on by default (for example, BigQuery or Cloud Storage). Leave them as they are. They cost nothing unless used, and this MVP doesn't use them.

<details>
<summary>Optional: enable the same APIs from Cloud Shell</summary>

Click the **Cloud Shell** icon (`>_`) in the top bar, then run:

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable aiplatform.googleapis.com firestore.googleapis.com \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  logging.googleapis.com
gcloud services list --enabled
```
</details>

---

## Step 5 — Create the monthly budget and alerts (10 min)

1. Open **☰ → Billing → Budgets & alerts** (pick the same billing account if asked).
2. Click **Create budget**.
3. **Scope** page:
   - **Name:** `weekendwise-demo-monthly`
   - **Time range:** *Monthly*
   - **Projects:** select **only** your WeekendWise project (not "All projects").
   - **Services:** *All services*.
   - **Credits / Savings:** **uncheck** discounts, promotions, and other credits so alerts reflect real usage even while credits cover the bill.
   - Click **Next**.
4. **Amount** page:
   - **Budget type:** *Specified amount*
   - **Target amount:** your limit, `20` (the demo maximum)
   - Click **Next**.
5. **Actions** page:
   - Thresholds: set **50%**, **80%**, and **100%**, each triggered on **Actual**. Optionally add **100% Forecasted** for an early warning.
   - Notifications: keep **Email alerts to billing admins and users** checked. To alert a different address, use **Link Monitoring email notification channels** and add it.
6. Click **Finish**.
7. Confirm the budget appears in the list with the right amount and project.

> Reminder: this budget sends emails. It does **not** cap or stop spending. Later stories reduce risk with Cloud Run min instances = 0, a low max instance count, and app-level limits on model calls.

---

## Step 6 — Confirm access, without keys (3 min)

1. Open **☰ → IAM & Admin → IAM**.
2. Confirm your account has **Owner** (or the roles needed to create service accounts and grant roles in later stories).
3. Note who will set up the Cloud Run runtime identity (MVP-03) and the ingestion identity (MVP-04). Usually that's you.
4. **Do not** create or download a service-account key. Later stories use attached identities and Application Default Credentials instead.

---

## Step 7 — Record the setup privately (3 min)

1. In the repository root, copy the template:
   ```bash
   cp .env.example .env
   ```
2. Fill in `GCP_PROJECT_ID`, `GCP_REGION`, and `BUDGET_USD`. Leave the model IDs empty until Guide 02.
3. Confirm `.env` is listed in `.gitignore`. Never commit `.env`, keys, billing account IDs, or payment details.

---

## Step 8 — Verify (5 min)

Tick each item:

- [ ] The project picker shows the intended **project ID**.
- [ ] **Billing** shows the project linked to the intended billing account.
- [ ] **Enabled APIs & services** lists Vertex AI, Cloud Firestore, Cloud Run Admin, Cloud Build, Artifact Registry, and Cloud Logging, and nothing extra that you enabled.
- [ ] **Budgets & alerts** shows `weekendwise-demo-monthly`, scoped to this project only, with 50/80/100% thresholds.
- [ ] Alert emails go to the right person (check **Actions** on the budget).
- [ ] `.env` contains project ID, region, and budget amount, and is not tracked by git.
- [ ] No service-account key was created (**IAM & Admin → Service Accounts → Keys** shows none for the project).

---

## Step 9 — Reviewer walkthrough

MVP-01 is done only after someone who **did not write this guide** follows it (or audits the result) without needing help.

1. Give the reviewer this guide and view access to the project's Billing and APIs pages.
2. The reviewer checks every Step 8 item and records:

| Step | Passed? | Notes (unclear wording, label differences, missing permission) |
|---|---|---|
| 0 Prerequisites | | |
| 1 Project | | |
| 2 Billing | | |
| 3 Region | | |
| 4 APIs | | |
| 5 Budget | | |
| 6 Access, no keys | | |
| 7 Private record | | |
| 8 Verify | | |

3. Fix any gaps they found in this guide, then mark the story's acceptance criteria as done.

---

## Step 10 — Clean up when the demo is over

Do these only once you're sure the project contains nothing else you need.

- **Stop charges quickly:** **Billing → Account management → My projects** → project row → **⋮ Actions → Disable billing**. Billable services stop working.
- **Delete the project:** **☰ → IAM & Admin → Settings** → **Shut down** → type the project ID → **Shut down**. The project is scheduled for deletion and can be restored for about 30 days.
- **Delete the budget:** **Billing → Budgets & alerts** → select `weekendwise-demo-monthly` → **Delete**.
- Review **Billing → Reports** for a few days afterward; charges already incurred may still appear.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "You don't have permission to create projects" | Organization policy or missing Project Creator role | Ask the org admin, or use an account without org restrictions |
| "Project ID already exists" | IDs are global | Add a suffix, e.g. `weekendwise-demo-ab12` |
| Project quota reached | Account has hit its project limit | Shut down unused projects or request more quota |
| No billing account listed | Missing Billing Account User role | Ask the billing admin to grant it |
| API won't enable; asks for billing | Billing not linked yet | Complete Step 2 first |
| **Budgets & alerts** not visible or read-only | Missing billing admin/costs manager role | Ask the billing admin, or have them create the budget |
| Model not available in region | Regional availability varies | Pick another region in Step 3 and reuse it everywhere |

## Completion evidence for MVP-01

- A private note (your `.env` or deployment notes) with project ID and region; no billing identifiers.
- A screenshot or confirmation that the budget and its thresholds are visible in Cloud Billing.
- The completed reviewer table from Step 9.
