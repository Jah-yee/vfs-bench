---
name: workspace-commands
description: The shell commands and task tools available in this workspace.
---

# Available commands

Standard Unix commands, among them:

    cat  head  tail  ls  find  grep  wc  sort  uniq  cut  tr  sed  awk
    diff  tee  xargs  jq  unzip  curl

with pipes, `>` redirection, `$(...)` substitution and `$'...'`.

The task CLIs below are registered with this shell rather than installed
as files; do not inspect them with `which`, `file` or `/usr/bin`.

## canvas

Use `canvas <command> '<JSON arguments>'`. Run `canvas <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `canvas health-check` | `{}` | Check the health and connectivity of the Canvas API |
| `canvas list-courses` | `{include_ended?: bool}` | List all courses for the current user — `include_ended`: Include ended courses |
| `canvas get-course` | `{course_id: number}` | Get detailed information about a specific course — `course_id`: ID of the course |
| `canvas create-course` | `{account_id: number, name: str, course_code?: str, start_at?: str, end_at?: str, license?: str, is_public?: bool, is_public_to_auth_users?: bool, public_syllabus?: bool, public_syllabus_to_auth?: bool, public_description?: str, allow_student_wiki_edits?: bool, allow_wiki_comments?: bool, allow_student_forum_attachments?: bool, open_enrollment?: bool, self_enrollment?: bool, restrict_enrollments_to_course_dates?: bool, term_id?: number, sis_course_id?: str, integration_id?: str, hide_final_grades?: bool, apply_assignment_group_weights?: bool, time_zone?: str, syllabus_body?: str}` | Create a new course in Canvas — `account_id`: ID of the account to create the course in; `name`: Name of the course; `course_code`: Course code (e.g., CS101); `start_at`: Course start date (ISO format); `end_at`: Course end date (ISO format); `license`: Course license; `is_public`: Whether the course is public; `is_public_to_auth_users`: Whether the course is public to authenticated users; `public_syllabus`: Whether the syllabus is public; `public_syllabus_to_auth`: Whether the syllabus is public to authenticated users; `public_description`: Public description of the course; `allow_student_wiki_edits`: Whether students can edit the wiki; `allow_wiki_comments`: Whether wiki comments are allowed; `allow_student_forum_attachments`: Whether students can add forum attachments; `open_enrollment`: Whether the course has open enrollment; `self_enrollment`: Whether the course allows self enrollment; `restrict_enrollments_to_course_dates`: Whether to restrict enrollments to course start/end dates; `term_id`: ID of the enrollment term; `sis_course_id`: SIS course ID; `integration_id`: Integration ID for the course; `hide_final_grades`: Whether to hide final grades; `apply_assignment_group_weights`: Whether to apply assignment group weights; `time_zone`: Course time zone; `syllabus_body`: Course syllabus content |
| `canvas update-course` | `{course_id: number, name?: str, course_code?: str, start_at?: str, end_at?: str, event?: "offer" \| "claim" \| "conclude" \| "delete" \| "undelete", is_public?: bool, is_public_to_auth_users?: bool, public_syllabus?: bool, public_syllabus_to_auth?: bool, public_description?: str, restrict_enrollments_to_course_dates?: bool, time_zone?: str, syllabus_body?: str}` | Update an existing course in Canvas. Use event='offer' to publish, event='claim' to unpublish. — `course_id`: ID of the course to update; `name`: New name for the course; `course_code`: New course code; `start_at`: New start date (ISO format); `end_at`: New end date (ISO format); `event`: Course event - 'offer' to publish, 'claim' to unpublish, 'conclude' to end, 'delete' to delete, 'undelete' to restore; `is_public`: Whether the course is public; `is_public_to_auth_users`: Whether the course is public to authenticated users; `public_syllabus`: Whether the syllabus is public; `public_syllabus_to_auth`: Whether the syllabus is public to authenticated users; `public_description`: Public description of the course; `restrict_enrollments_to_course_dates`: Whether to restrict enrollments to course start/end dates; `time_zone`: Course time zone; `syllabus_body`: Updated syllabus content |
| `canvas list-assignments` | `{course_id: number, include_submissions?: bool}` | List assignments for a course — `course_id`: ID of the course; `include_submissions`: Include submission data |
| `canvas get-assignment` | `{course_id: number, assignment_id: number, include_submission?: bool}` | Get detailed information about a specific assignment — `course_id`: ID of the course; `assignment_id`: ID of the assignment; `include_submission`: Include user's submission data |
| `canvas create-assignment` | `{course_id: number, name: str, description?: str, due_at?: str, points_possible?: number, submission_types?: list[str], allowed_extensions?: list[str], published?: bool}` | Create a new assignment in a Canvas course — `course_id`: ID of the course; `name`: Name of the assignment; `description`: Assignment description/instructions; `due_at`: Due date (ISO format); `points_possible`: Maximum points possible; `submission_types`: Allowed submission types; `allowed_extensions`: Allowed file extensions for submissions; `published`: Whether the assignment is published |
| `canvas update-assignment` | `{course_id: number, assignment_id: number, name?: str, description?: str, due_at?: str, points_possible?: number, published?: bool}` | Update an existing assignment — `course_id`: ID of the course; `assignment_id`: ID of the assignment to update; `name`: New name for the assignment; `description`: New assignment description; `due_at`: New due date (ISO format); `points_possible`: New maximum points; `published`: Whether the assignment is published |
| `canvas list-assignment-groups` | `{course_id: number}` | List assignment groups for a course — `course_id`: ID of the course |
| `canvas get-submission` | `{course_id: number, assignment_id: number, user_id?: number}` | Get submission details for an assignment — `course_id`: ID of the course; `assignment_id`: ID of the assignment; `user_id`: ID of the user (optional, defaults to self) |
| `canvas submit-assignment` | `{course_id: number, assignment_id: number, submission_type: "online_text_entry" \| "online_url" \| "online_upload", body?: str, url?: str, file_ids?: list[number]}` | Submit work for an assignment — `course_id`: ID of the course; `assignment_id`: ID of the assignment; `submission_type`: Type of submission; `body`: Text content for text submissions; `url`: URL for URL submissions; `file_ids`: File IDs for file submissions |
| `canvas submit-grade` | `{course_id: number, assignment_id: number, user_id: number, grade: number \| str, comment?: str}` | Submit a grade for a student's assignment (teacher only) — `course_id`: ID of the course; `assignment_id`: ID of the assignment; `user_id`: ID of the student; `grade`: Grade to submit (number or letter grade); `comment`: Optional comment on the submission |
| `canvas list-files` | `{course_id: number, folder_id?: number}` | List files in a course or folder — `course_id`: ID of the course; `folder_id`: ID of the folder (optional) |
| `canvas get-file` | `{file_id: number}` | Get information about a specific file — `file_id`: ID of the file |
| `canvas list-folders` | `{course_id: number}` | List folders in a course — `course_id`: ID of the course |
| `canvas list-pages` | `{course_id: number}` | List pages in a course — `course_id`: ID of the course |
| `canvas get-page` | `{course_id: number, page_url: str}` | Get content of a specific page — `course_id`: ID of the course; `page_url`: URL slug of the page |
| `canvas list-calendar-events` | `{start_date?: str, end_date?: str}` | List calendar events — `start_date`: Start date (ISO format); `end_date`: End date (ISO format) |
| `canvas get-upcoming-assignments` | `{limit?: number}` | Get upcoming assignment due dates — `limit`: Maximum number of assignments to return |
| `canvas get-dashboard` | `{}` | Get user's dashboard information |
| `canvas get-dashboard-cards` | `{}` | Get dashboard course cards |
| `canvas get-course-grades` | `{course_id: number}` | Get grades for a course — `course_id`: ID of the course |
| `canvas get-user-grades` | `{}` | Get all grades for the current user |
| `canvas get-user-profile` | `{}` | Get current user's profile |
| `canvas update-user-profile` | `{name?: str, short_name?: str, bio?: str, title?: str, time_zone?: str}` | Update current user's profile — `name`: User's name; `short_name`: User's short name; `bio`: User's bio; `title`: User's title; `time_zone`: User's time zone |
| `canvas enroll-user` | `{course_id: number, user_id: number, role?: str, enrollment_state?: str}` | Enroll a user in a course — `course_id`: ID of the course; `user_id`: ID of the user to enroll; `role`: Role for the enrollment (StudentEnrollment, TeacherEnrollment, etc.); `enrollment_state`: State of the enrollment (active, invited, etc.) |
| `canvas list-modules` | `{course_id: number}` | List all modules in a course — `course_id`: ID of the course |
| `canvas get-module` | `{course_id: number, module_id: number}` | Get details of a specific module — `course_id`: ID of the course; `module_id`: ID of the module |
| `canvas list-module-items` | `{course_id: number, module_id: number}` | List all items in a module — `course_id`: ID of the course; `module_id`: ID of the module |
| `canvas get-module-item` | `{course_id: number, module_id: number, item_id: number}` | Get details of a specific module item — `course_id`: ID of the course; `module_id`: ID of the module; `item_id`: ID of the module item |
| `canvas mark-module-item-complete` | `{course_id: number, module_id: number, item_id: number}` | Mark a module item as complete — `course_id`: ID of the course; `module_id`: ID of the module; `item_id`: ID of the module item |
| `canvas list-discussion-topics` | `{course_id: number}` | List all discussion topics in a course — `course_id`: ID of the course |
| `canvas get-discussion-topic` | `{course_id: number, topic_id: number}` | Get details of a specific discussion topic — `course_id`: ID of the course; `topic_id`: ID of the discussion topic |
| `canvas post-to-discussion` | `{course_id: number, topic_id: number, message: str}` | Post a message to a discussion topic — `course_id`: ID of the course; `topic_id`: ID of the discussion topic; `message`: Message content |
| `canvas list-announcements` | `{course_id: number}` | List all announcements in a course — `course_id`: ID of the course |
| `canvas create-announcement` | `{course_id: number, title: str, message: str, is_announcement?: bool, published?: bool, delayed_post_at?: str, attachment?: dict}` | Create a new announcement in a course — `course_id`: ID of the course; `title`: Title of the announcement; `message`: Content/message of the announcement; `is_announcement`: Mark as announcement (default: true); `published`: Whether the announcement is published; `delayed_post_at`: Delayed posting time (ISO format); `attachment`: File attachment for the announcement |
| `canvas list-quizzes` | `{course_id: number}` | List all quizzes in a course — `course_id`: ID of the course |
| `canvas get-quiz` | `{course_id: number, quiz_id: number}` | Get details of a specific quiz — `course_id`: ID of the course; `quiz_id`: ID of the quiz |
| `canvas create-quiz` | `{course_id: number, title: str, quiz_type?: str, time_limit?: number, published?: bool, description?: str, due_at?: str}` | Create a new quiz in a course — `course_id`: ID of the course; `title`: Title of the quiz; `quiz_type`: Type of the quiz (e.g., graded); `time_limit`: Time limit in minutes; `published`: Is the quiz published; `description`: Description of the quiz; `due_at`: Due date (ISO format) |
| `canvas start-quiz-attempt` | `{course_id: number, quiz_id: number}` | Start a new quiz attempt. Returns a quiz_submission object with 'id' field (the quiz_submission_id) and 'validation_token' needed for submitting answers. May return 500 error but still create submission (will auto-retry). Returns 409 if attempt already exists (will return existing). — `course_id`: ID of the course; `quiz_id`: ID of the quiz |
| `canvas submit-quiz-answers` | `{course_id: number, quiz_id: number, submission_id: number, validation_token?: str, answers: list[{question_id: number, answer?: any, answer_id?: number, match?: list[{answer_id?: number, match_id?: number}]}]}` | Submit answers for a quiz attempt. Use the 'id' from canvas_start_quiz_attempt as submission_id, NOT the quiz_id or any other ID. — `course_id`: ID of the course; `quiz_id`: ID of the quiz; `submission_id`: The quiz_submission ID from canvas_start_quiz_attempt response (the 'id' field, NOT 'submission_id' field); `validation_token`: REQUIRED: Validation token from canvas_start_quiz_attempt response. Without this, you'll get 403 'invalid token' error; `answers`: Array of answers to quiz questions; `answers.question_id`: ID of the question; `answers.answer`: Answer value - can be string, number, boolean, or array depending on question type; `answers.answer_id`: ID of the answer choice (for multiple choice); `answers.match`: Matching pairs for matching questions |
| `canvas list-quiz-questions` | `{course_id: number, quiz_id: number, quiz_submission_id?: number, quiz_submission_attempt?: number, use_submission_endpoint?: bool}` | List all questions in a quiz. Students: First call canvas_start_quiz_attempt to get quiz_submission_id, then use that ID (NOT quiz_id) with use_submission_endpoint=true. — `course_id`: ID of the course; `quiz_id`: ID of the quiz; `quiz_submission_id`: For students: The 'id' field from canvas_start_quiz_attempt response (NOT the quiz_id or submission_id field); `quiz_submission_attempt`: Optional: The attempt number (required if quiz_submission_id is specified for courses API); `use_submission_endpoint`: Optional: Use /quiz_submissions/:id/questions endpoint instead of courses API (recommended for students) |
| `canvas get-quiz-question` | `{course_id: number, quiz_id: number, question_id: number}` | Get details of a specific quiz question — `course_id`: ID of the course; `quiz_id`: ID of the quiz; `question_id`: ID of the question |
| `canvas create-quiz-question` | `{course_id: number, quiz_id: number, question_name: str, question_text: str, question_type: "multiple_choice_question" \| "true_false_question" \| "short_answer_question" \| "fill_in_multiple_blanks_question" \| "multiple_answers_question" \| "multiple_dropdowns_question" \| "matching_question" \| "numerical_question" \| "calculated_question" \| "essay_question" \| "file_upload_question" \| "text_only_question", points_possible: number, position?: number, correct_comments?: str, incorrect_comments?: str, neutral_comments?: str, answers?: list[{text?: str, weight?: number, comments?: str}]}` | Add a new question to a quiz — `course_id`: ID of the course; `quiz_id`: ID of the quiz; `question_name`: Name/title of the question; `question_text`: The question text (HTML supported); `question_type`: Type of question; `points_possible`: Points for this question; `position`: Position in the quiz; `correct_comments`: Comments shown for correct answers; `incorrect_comments`: Comments shown for incorrect answers; `neutral_comments`: General comments; `answers`: Array of answer choices; `answers.text`: Answer text; `answers.weight`: Weight (100 for correct, 0 for incorrect); `answers.comments`: Comments for this answer |
| `canvas update-quiz-question` | `{course_id: number, quiz_id: number, question_id: number, question_name?: str, question_text?: str, points_possible?: number, correct_comments?: str, incorrect_comments?: str, answers?: list[{text?: str, weight?: number, comments?: str}]}` | Update an existing quiz question — `course_id`: ID of the course; `quiz_id`: ID of the quiz; `question_id`: ID of the question to update; `question_name`: New name/title of the question; `question_text`: New question text; `points_possible`: New points value; `correct_comments`: New comments for correct answers; `incorrect_comments`: New comments for incorrect answers; `answers`: Updated answer choices |
| `canvas delete-quiz-question` | `{course_id: number, quiz_id: number, question_id: number}` | Delete a question from a quiz — `course_id`: ID of the course; `quiz_id`: ID of the quiz; `question_id`: ID of the question to delete |
| `canvas upload-file-from-path` | `{file_path: str, course_id?: number, folder_id?: number}` | Upload a file from local filesystem to Canvas — `file_path`: Absolute path to the local file; `course_id`: ID of the course (optional); `folder_id`: ID of the folder to upload to (optional) |
| `canvas submit-assignment-with-file` | `{course_id: number, assignment_id: number, file_path: str, comment?: str}` | Submit an assignment with a local file upload — `course_id`: ID of the course; `assignment_id`: ID of the assignment; `file_path`: Absolute path to the file to submit; `comment`: Optional submission comment |
| `canvas list-rubrics` | `{course_id: number}` | List rubrics for a course — `course_id`: ID of the course |
| `canvas get-rubric` | `{course_id: number, rubric_id: number}` | Get details of a specific rubric — `course_id`: ID of the course; `rubric_id`: ID of the rubric |
| `canvas list-conversations` | `{}` | List user's conversations |
| `canvas get-conversation` | `{conversation_id: number}` | Get details of a specific conversation — `conversation_id`: ID of the conversation |
| `canvas create-conversation` | `{recipients: list[str], body: str, subject?: str}` | Create a new conversation — `recipients`: Recipient user IDs or email addresses; `body`: Message body; `subject`: Message subject |
| `canvas list-notifications` | `{}` | List user's notifications |
| `canvas get-syllabus` | `{course_id: number}` | Get course syllabus — `course_id`: ID of the course |
| `canvas delete-course` | `{course_id: number, event?: "delete" \| "conclude" = "delete"}` | Delete or conclude a course — `course_id`: ID of the course to delete; `event`: Action to take: 'delete' removes the course entirely, 'conclude' makes it read-only |
| `canvas delete-assignment` | `{course_id: number, assignment_id: number}` | Delete an assignment — `course_id`: ID of the course; `assignment_id`: ID of the assignment to delete |
| `canvas delete-announcement` | `{course_id: number, announcement_id: number}` | Delete an announcement — `course_id`: ID of the course; `announcement_id`: ID of the announcement to delete |
| `canvas delete-quiz` | `{course_id: number, quiz_id: number}` | Delete a quiz — `course_id`: ID of the course; `quiz_id`: ID of the quiz to delete |
| `canvas delete-conversation` | `{conversation_id: number}` | Delete a conversation — `conversation_id`: ID of the conversation to delete |
| `canvas unenroll-user` | `{course_id: number, enrollment_id: number}` | Unenroll a user from a course — `course_id`: ID of the course; `enrollment_id`: ID of the enrollment to remove |
| `canvas get-account` | `{account_id: number}` | Get account details — `account_id`: ID of the account |
| `canvas list-account-courses` | `{account_id: number, with_enrollments?: bool, published?: bool, completed?: bool, search_term?: str, sort?: "course_name" \| "sis_course_id" \| "teacher" \| "account_name", order?: "asc" \| "desc"}` | List courses for an account — `account_id`: ID of the account; `with_enrollments`: Include enrollment data; `published`: Only include published courses; `completed`: Include completed courses; `search_term`: Search term to filter courses; `sort`: Sort order; `order`: Sort direction |
| `canvas list-account-users` | `{session_id?: str, account_id?: number, search_term?: str, sort?: "username" \| "email" \| "sis_id" \| "last_login", order?: "asc" \| "desc", page?: number = 1, per_page?: number = 20}` | List users for an account with pagination support and session management. Returns up to 20 users per page. Use session_id to continue previous search or provide new parameters to start fresh. — `session_id`: Session ID to continue previous search (when provided, other parameters except 'page' are ignored); `account_id`: ID of the account (required for new sessions); `search_term`: Search term to filter users; `sort`: Sort order; `order`: Sort direction; `page`: Page number (starts from 1, default: 1); `per_page`: Number of users per page (max: 20, default: 20) |
| `canvas create-user` | `{account_id: number, user: {name: str, short_name?: str, sortable_name?: str, time_zone?: str}, pseudonym: {unique_id: str, password?: str, sis_user_id?: str, send_confirmation?: bool}}` | Create a new user in an account — `account_id`: ID of the account; `user.name`: Full name of the user; `user.short_name`: Short name of the user; `user.sortable_name`: Sortable name (Last, First); `user.time_zone`: User's time zone; `pseudonym.unique_id`: Unique login ID (email or username); `pseudonym.password`: User's password; `pseudonym.sis_user_id`: SIS ID for the user; `pseudonym.send_confirmation`: Send confirmation email |
| `canvas list-sub-accounts` | `{account_id: number}` | List sub-accounts for an account — `account_id`: ID of the parent account |
| `canvas get-account-reports` | `{account_id: number}` | List available reports for an account — `account_id`: ID of the account |
| `canvas create-account-report` | `{account_id: number, report: str, parameters?: dict}` | Generate a report for an account — `account_id`: ID of the account; `report`: Type of report to generate; `parameters`: Report parameters |

## emails

Use `emails <command> '<JSON arguments>'`. Run `emails <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `emails get-emails` | `{folder?: str = "INBOX", page?: int = 1, page_size?: int = 20}` | Get paginated list of emails from specified folder Args: folder: Email folder name (default: INBOX) page: Page number starting from 1 (default: 1) page_size: Number of emails per page (default: 20) |
| `emails read-email` | `{email_id: str}` | Read full content of a specific email Args: email_id: Email ID to read |
| `emails search-emails` | `{query: str, folder?: str = "INBOX", page?: int = 1, page_size?: int = 20}` | Search emails with query string (sorted by date descending) Args: query: Search query (subject, from, body content) folder: Folder to search in (default: INBOX) page: Page number starting from 1 (default: 1) page_size: Number of results per page (default: 20) |
| `emails send-email` | `{to: str, subject: str, body: str, html_body?: str = null, cc?: str = null, bcc?: str = null, attachments?: list[str] = null}` | Send an email with optional HTML body, CC, BCC, and attachments Args: to: Recipient email address(es), comma-separated subject: Email subject body: Plain text body html_body: HTML body content (optional) cc: CC recipients, comma-separated (optional) bcc: BCC recipients, comma-separated (optional) attachments: List of file paths to attach (optional) |
| `emails reply-email` | `{email_id: str, body: str, html_body?: str = null, cc?: str = null, bcc?: str = null, reply_all?: bool = false}` | Reply to an email Args: email_id: ID of email to reply to body: Reply message body (plain text) html_body: Reply message body (HTML, optional) cc: Additional CC recipients (optional) bcc: BCC recipients (optional) reply_all: Whether to reply to all recipients (default: False) |
| `emails forward-email` | `{email_id: str, to: str, body?: str = null, html_body?: str = null, cc?: str = null, bcc?: str = null}` | Forward an email to other recipients Args: email_id: ID of email to forward to: Recipients to forward to body: Additional message body (optional) html_body: Additional HTML message body (optional) cc: CC recipients (optional) bcc: BCC recipients (optional) |
| `emails delete-email` | `{email_id: str}` | Delete an email Args: email_id: Email ID to delete |
| `emails move-email` | `{email_id: str, target_folder: str}` | Move email to another folder Args: email_id: Email ID to move target_folder: Target folder name |
| `emails mark-emails` | `{email_ids: list[str], status: str}` | Mark multiple emails with status (read/unread/important/not_important) Args: email_ids: List of email IDs to mark status: Status to set (read, unread, important, not_important) |
| `emails move-emails` | `{email_ids: list[str], target_folder: str}` | Move multiple emails to another folder with improved ID synchronization Args: email_ids: List of email IDs to move target_folder: Target folder name |
| `emails delete-emails` | `{email_ids: list[str]}` | Delete multiple emails with improved ID synchronization Args: email_ids: List of email IDs to delete |
| `emails get-folders` | `{}` | Get list of available email folders |
| `emails create-folder` | `{folder_name: str}` | Create new email folder Args: folder_name: Name of folder to create |
| `emails delete-folder` | `{folder_name: str}` | Delete email folder Args: folder_name: Name of folder to delete |
| `emails get-mailbox-stats` | `{folder_name?: str = null}` | Get mailbox statistics Args: folder_name: Specific folder name (optional, defaults to all folders) |
| `emails get-unread-count` | `{folder_name?: str = null}` | Get unread message count Args: folder_name: Specific folder name (optional, defaults to all folders) |
| `emails check-connection` | `{}` | Check email server connection status |
| `emails get-email-headers` | `{email_id: str}` | Get complete email headers for technical analysis Args: email_id: Email ID to get headers for |
| `emails save-draft` | `{subject: str, body: str, html_body?: str = null, to?: str = null, cc?: str = null, bcc?: str = null}` | Save email draft Args: subject: Email subject body: Plain text body html_body: HTML body content (optional) to: Recipient email address(es) (optional) cc: CC recipients (optional) bcc: BCC recipients (optional) |
| `emails get-drafts` | `{page?: int = 1, page_size?: int = 20}` | Get list of saved drafts Args: page: Page number starting from 1 (default: 1) page_size: Number of drafts per page (default: 20) |
| `emails update-draft` | `{draft_id: str, subject?: str = null, body?: str = null, html_body?: str = null, to?: str = null, cc?: str = null, bcc?: str = null}` | Update existing draft Args: draft_id: Draft ID to update subject: Email subject (optional) body: Plain text body (optional) html_body: HTML body content (optional) to: Recipient email address(es) (optional) cc: CC recipients (optional) bcc: BCC recipients (optional) |
| `emails delete-draft` | `{draft_id: str}` | Delete draft Args: draft_id: Draft ID to delete |
| `emails export-emails` | `{folder?: str = null, export_path?: str = "emails_export.json", max_emails?: int = null, export_all_folders?: bool = false}` | Export emails to file for backup Args: folder: Specific folder to export (mutually exclusive with export_all_folders) export_path: Path where to save the export file max_emails: Maximum number of emails to export (optional, exports all if not specified) export_all_folders: Export from all folders instead of just one (default: False) |
| `emails import-emails` | `{import_path: str, target_folder?: str = null, preserve_folders?: bool = true}` | Import emails from backup file to IMAP server Args: import_path: Path to import file (.json or .eml) or a directory target_folder: Target folder for imported emails (if preserve_folders=False) preserve_folders: Whether to preserve original folder structure (default: True) |
| `emails download-attachment` | `{email_id: str, attachment_filename: str}` | Download email attachment to configured download path Args: email_id: Email ID containing the attachment attachment_filename: Name of attachment to download |

## memory

Use `memory <command> '<JSON arguments>'`. Run `memory <command> --help` to
get more information.

| Command | Arguments | Description |
|---|---|---|
| `memory create-entities` | `{entities: list[{name: str, entityType: str, observations: list[str]}]}` | Create multiple new entities in the knowledge graph — `entities.name`: The name of the entity; `entities.entityType`: The type of the entity; `entities.observations`: An array of observation contents associated with the entity |
| `memory create-relations` | `{relations: list[{from: str, to: str, relationType: str}]}` | Create multiple new relations between entities in the knowledge graph. Relations should be in active voice — `relations.from`: The name of the entity where the relation starts; `relations.to`: The name of the entity where the relation ends; `relations.relationType`: The type of the relation |
| `memory add-observations` | `{observations: list[{entityName: str, contents: list[str]}]}` | Add new observations to existing entities in the knowledge graph — `observations.entityName`: The name of the entity to add the observations to; `observations.contents`: An array of observation contents to add |
| `memory delete-entities` | `{entityNames: list[str]}` | Delete multiple entities and their associated relations from the knowledge graph — `entityNames`: An array of entity names to delete |
| `memory delete-observations` | `{deletions: list[{entityName: str, observations: list[str]}]}` | Delete specific observations from entities in the knowledge graph — `deletions.entityName`: The name of the entity containing the observations; `deletions.observations`: An array of observations to delete |
| `memory delete-relations` | `{relations: list[{from: str, to: str, relationType: str}]}` | Delete multiple relations from the knowledge graph — `relations`: An array of relations to delete; `relations.from`: The name of the entity where the relation starts; `relations.to`: The name of the entity where the relation ends; `relations.relationType`: The type of the relation |
| `memory read-graph` | `{}` | Read the entire knowledge graph |
| `memory search-nodes` | `{query: str}` | Search for nodes in the knowledge graph based on a query — `query`: The search query to match against entity names, types, and observation content |
| `memory open-nodes` | `{names: list[str]}` | Open specific nodes in the knowledge graph by their names — `names`: An array of entity names to retrieve |

## git

Use `git --help` for Git operations on workspace repositories.

## python3

Execute Python code directly under the agent workspace and return stdout
and stderr. Code can be pasted into a `.py` file and run with `python3`.

Python cannot launch subprocesses or make direct network requests. Run the
documented service commands directly in the shell. Use Python for local
file processing and generating JSON arguments.
