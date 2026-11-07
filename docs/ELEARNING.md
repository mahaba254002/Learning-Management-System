# E-learning: courses, files, quizzes and registration

This guide covers the course pages, file uploads, online quizzes, deadlines, notifications and course registration windows.

## Course pages

**My courses** shows each subject or unit as a card. Students see their own courses; teachers see the ones they teach; admins see **Course pages** for all. Search by name and sort by name or next deadline (students) or class (staff).

A course page groups materials, assignments and quizzes under week or topic headings. A teacher types the heading in **Week or topic** when adding a material or an assessment. Items with the same heading appear together. Items with no heading appear under *General*.

## Files

- Teachers can attach a file to a material and a question paper or brief to any assessment.
- Teachers choose whether students may hand in files and which types: PDF, Word, PowerPoint, Excel or images (PNG/JPG). With nothing ticked, students answer with text or a link as before.
- Each file can be up to 10 MB. Skynet checks the file's contents match its type, so a renamed program is refused.
- Who can open a file:
  - **Students:** a material's file once it is published; a question paper once the work is published and, for quizzes, open.
  - **Teachers:** a student's file once it is handed in. Drafts stay private.
- Files open through short-lived links (about 5 minutes). A copied link stops working, so it can't be passed around.

## Online quizzes

Create a quiz from **Coursework**. Under *How students answer*, choose **Online quiz** and set a closing time, and optionally an opening time. Save it, then open **Questions, rules & results**.

**Questions:**
- *One correct answer*, *Several correct answers* or *True or false*.
- Each question has marks and an optional time limit (10 seconds to 1 hour).
- A *several correct answers* question scores only if the student picks exactly the correct options.
- The quiz is out of the total of its question marks.
- Questions can't be changed once any student has started.

**Rules:**

| Rule | What it does |
|---|---|
| Time for the whole quiz | Each attempt ends after this many minutes, or at the closing time if sooner. |
| Attempts per student | Default 1. With more, the best score counts. |
| No going back | One question at a time; earlier questions can't be reopened. |
| Per-question time limit | When the time runs out the quiz moves on by itself. Any timed question turns on *one at a time, no going back*. |
| Shuffle questions / options | Each student gets a different order (true/false options are not shuffled). |
| Hide scores and answers until the quiz closes | Stops answers being shared while others are still taking it. |
| Record when students leave the page | Counts how often a student switches tab or app. It flags; it can't block. |

The server keeps every clock:
- A late answer is refused.
- A question whose time ran out moves on even if the student closed the page.
- An attempt still open when time is up is handed in automatically.

The browser clock can't be used to cheat.

**Results** lists every student's attempts, best score and page-leaving count, with each attempt's answers. **Allow another attempt** gives one student one more attempt. A reason is required and kept on the audit trail (for example *power cut during the quiz*).

The best score is written to the student's marks for that assessment, so it appears in Scores and the Excel marksheet like any other CAT or assignment. Students see it in *Grades* once you release results, as usual.

**When students see their answers:**
- **Score:** right after handing in, unless *hide until close* is on.
- **Correct answers:** after their last attempt, or after the quiz closes when *hide until close* is on.

## Paper quizzes

To use a quiz written in Word or PDF:
1. Create a normal assignment or CAT.
2. Upload the paper as its **Question paper**.
3. Tick the file types students should hand in.

Students download the paper and upload their answers before the deadline, and the teacher marks them in Scores.

## Deadlines and notifications

- **Upcoming deadlines** on the student dashboard lists work due in the next 30 days and anything missed or overdue in the last 14 days.
- **Closing soon** on the teacher dashboard lists published work closing in the next 14 days.
- **The bell** in the top bar shows new work, new materials, released marks and registration decisions. It also lists work due within 48 hours that the student hasn't done. Notifications are free (no SMS).

## Course registration windows

Use this when students choose optional units themselves.

1. **Admin:** go to **Course registration**, then **Open a registration window**. Set:
   - opening and closing times;
   - the fewest and most units, and optionally the fewest and most credits (credits come from the course catalogue);
   - optionally the term or semester;
   - the classes (no classes ticked means every class).
2. **Students:** go to **Course registration** and tick units. Only units set as *individual registration* in their own class are listed. Choices can change until the window closes, and prerequisites are checked straight away.
3. **Approving:**
   - Choices wait as *Waiting for approval*. The admin, or staff with the *Approve course registration choices* right, ticks them and approves.
   - Declining needs a note, which the student sees.
   - A choice that fails entry rules at approval stays selected, with the reason.
   - Approved units give the student access to the course; the student is notified either way.

A student can drop an approved unit while the window is open, unless they already have marks in it.

## Switching features on and off

The platform admin can switch **Online quizzes** and **Course registration windows** off per school, under the school's package. File uploads follow *Learning materials* and *Coursework*.

## Platform setup (file storage)

Files are stored in Cloudflare R2. The free tier is 10 GB and has no download fees. **Platform → File storage** shows each school's use. Without the settings below, uploads are off and teachers see "File uploads are not set up yet".

1. In Cloudflare, go to **R2**, then **Create bucket** (for example `skynet-files`). Keep it **private**; don't enable public access.
2. Go to **R2 → Manage API tokens → Create API token**. Give it *Object Read & Write* on that bucket only. Copy the *Access Key ID* and *Secret Access Key*.
3. On the Render API service, add:

| Variable | Value |
|---|---|
| `STORAGE_BACKEND` | `r2` |
| `R2_ACCOUNT_ID` | your Cloudflare account ID (in the R2 overview) |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | from step 2 |
| `R2_BUCKET` | the bucket name |

4. Redeploy. No CORS setup is needed: uploads pass through the API, and downloads are plain signed links.

`STORAGE_BACKEND=local` saves files in a folder. It is for development only and is refused outside development.

**Backups** include file details (names, sizes, who uploaded what), not the files themselves. The files stay in R2.
