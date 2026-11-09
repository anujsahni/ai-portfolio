# ------------------------------------------------------------ Bedrock guardrail (IAC-05)
#
# Screens text going into and coming out of Claude. The app calls it on its own (ApplyGuardrail)
# before and after each model call (MVP-08), so the same rules apply however the model is called.
#   input:  prompt-attack filter (instructions hidden in notes or questions)
#   output: email addresses and phone numbers are masked
#   both:   a denied topic, so the assistant won't judge or rank individual employees
# Creating a guardrail is free; each check is billed per 1,000 characters (fractions of a cent here).

resource "aws_bedrock_guardrail" "main" {
  name                      = "${var.name_prefix}-guardrail"
  description               = "DealPulse: prompt-attack filter, contact-detail masking, no judging employees"
  blocked_input_messaging   = "DealPulse can't use this text: it looks like an instruction aimed at the assistant, or asks it to judge a person. Rephrase the question about the deal."
  blocked_outputs_messaging = "DealPulse withheld this answer because it broke a safety rule. The score and evidence are still shown."

  content_policy_config {
    filters_config {
      type            = "PROMPT_ATTACK"
      input_strength  = "HIGH"
      output_strength = "NONE" # prompt attacks are only checked on input
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      type   = "EMAIL"
      action = "ANONYMIZE"
    }
    pii_entities_config {
      type   = "PHONE"
      action = "ANONYMIZE"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "Evaluating employees"
      type       = "DENY"
      definition = "Judging, ranking or rating an individual employee's or sales rep's performance, ability or job security, or recommending discipline, firing or compensation changes for a person."
      examples = [
        "Which of my reps is the worst performer?",
        "Should I fire Marcus based on his pipeline?",
        "Rank my account executives from best to worst.",
        "Is Elena a weak salesperson?",
      ]
    }
  }
}

resource "aws_bedrock_guardrail_version" "main" {
  guardrail_arn = aws_bedrock_guardrail.main.guardrail_arn
  description   = "Managed by Terraform; a new version is published when the guardrail changes"

  lifecycle {
    replace_triggered_by = [aws_bedrock_guardrail.main]
  }
}
