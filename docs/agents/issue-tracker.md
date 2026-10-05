# Issue tracker: Local Markdown

The user chose local files without GitHub publication. Specs live at `.scratch/<feature-slug>/spec.md`; implementation tickets are one file each at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered with blockers first.

Read the complete ticket and any appended comments before working. Record blocking edges by ticket number and title, and triage state in the ticket's Status field. This feature uses `ready-for-agent`, `claimed`, and `resolved`; a specification-ready ticket still waits until its blockers are resolved.

When a skill requests publication, save the local file rather than creating a remote issue. Preserve parent specs and do not close or modify parent issues when publishing tickets. Append implementation outcomes under Comments or Answer, and avoid duplicate tickets.
