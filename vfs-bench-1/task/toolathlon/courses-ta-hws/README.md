# Courses TA homework

Find every file belonging to Assignment 3 of "Operating Systems Fundamentals",
rename them all to `Name-College-StudentID-OS-HW3` using the college/student-ID
correspondence table, sort them into `os_hw3/C`, `os_hw3/Rust` and
`os_hw3/Python`, and delete the original code files — including those from other
courses and other assignments.

The task has two halves. The renaming rule is strict about capitalization and
spacing ("do not arbitrarily add or remove words"), and every file has to be
*found* first — Assignment 3's C submissions are scattered across the tree, and
the grader expects exactly 33 C files.

The deletion clause requires removing files the task never enumerates,
including ones outside the course.

```bash
uv run python agent/run_agent.py toolathlon/courses-ta-hws --tools vfs
uv run python agent/run_agent.py toolathlon/courses-ta-hws --tools mcp
```
