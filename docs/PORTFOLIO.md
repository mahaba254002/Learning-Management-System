# Rollcall — engineering portfolio

## Problem and approach

Learning records are often split between attendance registers, shared documents and separate assignment channels. Rollcall explores a single workflow where students can follow learning activity and staff can manage it within institution boundaries.

The project implements four distinct roles across a shared application and database. The educational aim is clearer access to materials, deadlines and feedback. This is an intended benefit, not a measured impact claim: no adoption, learning-outcome or time-saving study is included in this repository.

## Engineering decisions to discuss

- **Institution isolation:** server-side scope checks plus composite database relationships, rather than trusting a role-specific interface to protect records.
- **Teaching authority:** subject assignments and class supervision are different permissions. A teacher does not automatically gain access to every student at an institution.
- **Submission integrity:** private drafts, final receipts, deadline policies and optimistic version checks protect the learning workflow against accidental overwrites.
- **Record preservation:** enrollment withdrawal retains history; institution and account status changes invalidate older sessions.
- **Reproducible evaluation:** deterministic sample relationships and isolated tests make scenarios repeatable without exposing actual learner data.
- **Accessible presentation:** responsive layouts, semantic headings, keyboard focus and clearly labelled role entry points. Formal accessibility conformance has not been independently established.

## Suggested five-minute project walkthrough

1. Explain the problem and the four roles from the home page.
2. Show an institution’s class and subject assignments.
3. As a teacher, show a published resource, assessment and attendance view.
4. As a student, show the corresponding material, submission workflow and personal progress.
5. Explain one tenant-isolation test and one rejected submission scenario.
6. Close with the current limitations and the research question you want to pursue.

Use a disposable development dataset for demonstrations. Share access privately; never put account passwords into an application, slide deck or public repository.

## Positioning in a master’s application

Describe your own contributions precisely and explain the decisions you can defend. Disclose assistance and collaboration according to the institution’s rules. Support statements with source files, test results and a reproducible demonstration rather than claims of production scale or educational impact.

Potential research directions include usability for low-connectivity schools, understandable access controls, equitable access to digital coursework and the relationship between feedback visibility and learner engagement. A credible next study would define participants, consent, privacy protections, accessibility needs and outcome measures before collecting learner data.

This project can demonstrate implementation ability and a basis for further research. Scholarship selection depends on the full application; this repository does not establish eligibility or guarantee an award.
