---
id: incident-escalation
title: Incident Escalation
owner: Engineering Operations
effective: 2026-01-01
---

# Incident Escalation

This policy is the escalation process for production incidents and security events. Engineering Operations owns the process. Security joins when personal data is involved. It is effective 2026-01-01.

## Severity levels

Sev1 means confirmed exposure of customer or employee personal data, the product is unavailable for all users, or there is a safety risk. Page the incident commander immediately, open a bridge within 15 minutes, and post a status update every 30 minutes until the incident is resolved. Notify Security and Legal in the same hour when personal data is involved.

Sev2 means a major feature is broken and a workaround exists, or a significant group of users is affected. Acknowledge the incident within 1 hour and update the channel every hour.

Sev3 means limited impact and an acceptable workaround. Triage the incident on the next business day.

## Escalation process

Use this escalation process for every declared incident. Declare it in the #incidents channel or in IncidentDesk and include the impact, the start time, and what changed. The first responder is the incident commander until a named commander takes over. The incident commander assigns a communications lead and a subject owner. Raise the severity if the impact grows. Do not downgrade a Sev1 without Security agreement when data is involved. Do not put customer data, secrets, or passwords in the channel. Store evidence in the approved vault and link to it.

## After the incident

Sev1 and Sev2 incidents get a blameless review within 5 business days. The subject owner tracks action items. A Sev3 review is optional. Reviews look for system fixes, not individual blame.

## Safety first

For a physical emergency, contact local emergency services before any internal escalation. Then tell the manager and Workplace Safety. This incident process does not replace that call.
