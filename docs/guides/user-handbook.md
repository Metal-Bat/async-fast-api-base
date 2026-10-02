# Using requests and approvals

Audience: requesters, reviewers and administrators. Status: implemented backend behavior.
Reviewed: 2026-10-02. Screen names below describe tasks; this repository does not yet provide
the finished user interface, so button positions and screenshots are not specified.

[Documentation home](../Home.md) · [Frontend implementation](frontend-journey.md)

## What this system does

You fill in a request, send it for processing, and follow its progress. A workflow decides which
people or automated steps must act next. For example, a purchase request may need two managers
to approve it before it is finished.

| Word | Plain-language meaning |
| --- | --- |
| Request type | The kind of case you want to start, such as a purchase request. |
| Form | The questions and values needed for a request or review. |
| Draft | Work you have saved but have not submitted. |
| Workflow | The agreed sequence of decisions and automated steps. |
| Task / work item | One piece of work offered or assigned to a person. |
| Available work | Tasks you are currently eligible to take. The API calls this a cartable. |
| Claim | Reserve an available task for yourself so another person cannot also complete it. |
| Version | A saved edition of a form or workflow. A running request keeps its chosen edition. |
| Permission | An administrator's grant allowing an action. A group membership alone is not every permission. |

## Before you begin

Ask your administrator for an account and access to the request type you need. The administrator
must publish the form and workflow and configure the request type first. Installation does not
automatically create a complete purchase-approval workflow. Some request types also require a
specific registered application or release.

Sign in with your account. If you cannot sign in, check your credentials and contact the
administrator. Password recovery currently directs users to administrator-assisted recovery;
requesting help does not promise an email will be sent. A temporarily locked account should not
be retried continuously.

## Start and submit a request

1. Open the request type provided by your administrator.
2. Fill in the form. Keep selected option values associated with their displayed labels; do not
   replace a stored value with a translated label.
3. Save the draft. Check that saving succeeded before leaving the page. A draft can be incomplete;
   submission applies the full required-field and business checks.
4. Add attachments if the form supports them. An uploaded file is not necessarily attached to a
   request until the attachment operation succeeds.
5. Review the information, then submit once. Submission freezes that submission and starts the
   configured workflow. A quick workflow may already have moved beyond “submitted” when the
   response arrives.
6. Open the request again to see its current state. Submitting successfully does not mean the
   request has been approved.

If a save reports that someone changed the record, keep your unsaved text, refresh the latest
version, and compare the changes before saving again. Do not overwrite the newer version blindly.
If submission times out, check the request before starting a new one; the original may have succeeded.

## Review someone else's request

1. Open your available work list. An empty list can mean there is no eligible work for you now.
2. Claim a task. Another reviewer may have claimed it first; if so, refresh your list.
3. Open the task's review view. You may see only the fields needed for your role.
4. Review the information and save any permitted edits. Saving does not complete the task.
5. Choose one of the actions the task actually offers. Depending on its configuration, these
   may include approve, reject or return for correction. Some actions require a comment.
6. Confirm the action and wait for success. The workflow may create another person's task next.

An approval on one task is not necessarily the final approval of the entire request. AI may
prepare a recommendation, but a configured human approval still needs an eligible person to act.
If you cannot continue a claimed task, use release when available so another eligible person can take it.

## Correct a returned request

When the workflow supports corrections, a reviewer can return work with field or row feedback.
Open the correction task offered to you, claim it when required, read the feedback, and edit the
permitted fields. Mark individual feedback items resolved when the action is available, then use
the task's offered action to resubmit. This creates an audited correction round; it does not unlock
the original frozen submission. Not every workflow includes a correction route.

## Understand progress

Request state and task state answer different questions. Request states describe the whole case;
task states describe a person's work. A process can be waiting while its request remains running.

| What you see | Meaning / next action |
| --- | --- |
| Draft request | Saved and still editable by its requester. |
| Submitted or running request | Accepted for processing; wait for or complete required work. |
| Waiting process | A human, timer, event or background operation must complete before progress continues. |
| Open task | Available to eligible people, but not yet claimed. |
| Claimed / in-progress task | Reserved for its current reviewer. |
| Completed request | The workflow reached its end. Interpret approval/rejection using its business outcome, not this word alone. |
| Failed request | Processing needs investigation; tell support the request identifier. Do not create duplicates to bypass it. |
| Cancelled request | Processing was stopped. Available cancellation actions depend on the current state and your authority. |

Pinning, marking read, archiving or watching a task changes personal organization; it is not an
approval or cancellation. Refresh progress when returning to a page. Notifications can help, but
the request's current state is the authority.

## Common problems

| Problem | What to do |
| --- | --- |
| A field needs correction | Read the field message, correct the value and submit again. |
| Your session expired | Sign in again, then reload the record before acting. |
| You lack permission / cannot find a record | Check the account, group and request assignment with the administrator. A link does not grant access. |
| A task changed or was taken | Refresh. Do not repeatedly submit the old action. |
| A file cannot be downloaded | Use the authorized account; private files are not public share links. |
| The service is unavailable | Preserve your edits. Check whether the last action succeeded before retrying. |

When contacting support, include what you were doing, the time, the displayed error and its
request/correlation identifier. Do not send passwords, access tokens or unnecessary personal data.

## For administrators

Provision user permissions, reviewer assignments and work-group membership; publish compatible
forms/workflows; activate request types; and test the whole journey with ordinary accounts.
Verify any required registered client and its supported form design. Publishing a new edition
does not silently replace the editions used by active cases.

Technical setup is in the [README](../../README.md). Operations and recovery are in the
[safeguards guide](../operations/bpms-safeguards.md). The implemented core journey is exercised by
the [purchase regression](../testing/full-workflow-regression.md); the broader
[roadmap](../roadmap/full-workflow.md) includes work not yet combined into that test.
