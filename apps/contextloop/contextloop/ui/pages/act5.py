"""Act 5: Activate. The governed at-risk list goes back into the (mock) CRM and to Slack, diff-based, with an audit trail."""
from __future__ import annotations

import httpx
import pandas as pd
import streamlit as st

from contextloop.activation import sync
from contextloop.ui import common


def _client() -> httpx.Client:
    return httpx.Client(timeout=30)


def render() -> None:
    common.header("Act 5", "Activate", "An answer on a screen changes nothing. The at-risk list and next steps go back into the CRM "
                  "and the channel where the account teams already work.")
    if not common.require_warehouse():
        return
    st.markdown(common.badge("Mock CRM", "warn", "info") + "<small>A local stand-in for Salesforce (FastAPI). Synthetic data; no real "
                "CRM is touched.</small>", unsafe_allow_html=True)
    gov = common.recording("governed", "G1") or st.session_state.get("live-governed-G1")
    ai_answer = (gov or {}).get("answer")
    try:
        with _client() as c:
            plan = sync.plan(c, ai_answer)
    except httpx.HTTPError as exc:
        st.error(f"The mock CRM isn't reachable ({exc}). Is the mock-salesforce container running?")
        return
    counts = plan.counts
    a, b, c_ = st.columns(3)
    a.metric("Updates planned", counts["update"] + counts["clear"])
    b.metric("Unchanged", counts["unchanged"])
    c_.metric("Source model", "marts.account_risk")
    st.subheader("Dry run: what the sync would change")
    rows = [{"account": ch.account_name, "change": ch.kind, "fields": ", ".join(ch.changed_fields) or "—",
             "drivers (new)": ch.after.get("Delivery_Risk_Drivers__c"), "next step (new)": ch.after.get("Next_Step__c"),
             "next step source": ch.after.get("Next_Step_Source__c")} for ch in plan.changes]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("Next steps marked **AI-drafted** come from the governed agent's structured answer; the account list and drivers "
               "always come from the dbt model, never from an agent's free text.")
    left, right = st.columns(2)
    if left.button("Sync to Salesforce", type="primary", icon=":material/cloud_upload:", disabled=counts["update"] + counts["clear"] == 0):
        with _client() as c:
            result = sync.apply(c, plan)
        st.success(f"Synced: {result['written']} records written (sync {result['sync_id']}). Run the dry run again: nothing changes.")
        st.rerun()
    if right.button("Reset the mock CRM (for rehearsals)", icon=":material/restart_alt:"):
        with _client() as c:
            c.post(f"{sync.CRM_URL}/reset")
        st.rerun()
    with _client() as c:
        flagged = c.get(f"{sync.CRM_URL}/accounts", params={"flagged_only": True}).json()
        audit = c.get(f"{sync.CRM_URL}/audit").json()
    st.subheader("CRM records now")
    if flagged:
        st.dataframe(pd.DataFrame(flagged)[["Name", "OwnerName", "Delivery_Risk__c", "Delivery_Risk_Drivers__c", "Next_Step__c",
                                            "Next_Step_Source__c", "Risk_Updated_At__c"]], hide_index=True, use_container_width=True)
    else:
        st.info("No account carries a delivery-risk flag yet.")
    with st.expander(f"Audit log ({len(audit)} writes)", expanded=bool(audit)):
        if audit:
            st.dataframe(pd.DataFrame([{"at": x["at"], "account": x["account_name"], "fields": ", ".join(x["changes"]),
                                        "source_model": x["source_model"], "sync": x["sync_id"]} for x in audit]),
                         hide_index=True, use_container_width=True)
    st.subheader("Slack")
    msg = sync.slack_message()
    st.code(msg["text"], language="markdown")
    if st.button("Post to Slack", icon=":material/forum:"):
        res = sync.post_slack(msg)
        st.success("Posted to Slack.") if res["posted"] else st.info(res.get("reason") or f"Slack returned {res.get('status')}")
    st.markdown("---\n**Back to the COO's question:** the answer is now in the CRM records the account teams open every day, "
                "with the drivers and a next step, and it updates on every sync.")
    common.nav_buttons("act5")
