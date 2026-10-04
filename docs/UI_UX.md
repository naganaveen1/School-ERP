# UI and UX audit

The frontend contains static HTML pages for admin, principal, teacher, student, and parent roles. Pages load shared CSS and JavaScript, but each also contains its own tables, cards, forms, and inline styling. `components.renderLayout()` supplies the navigation on role pages.

## Current experience after the foundation and SaaS continuation

- Login has a new two-panel layout, no visible demo credentials, and an optional school workspace slug with dynamic school branding.
- Navigation is role-specific and generated centrally. The shared renderer supplies SVG decorations, a theme selector, focus states and responsive drawer behavior.
- The new platform dashboard uses API metrics, a school table, plan management, onboarding forms, subscription controls and audit activity. The school subscription page shows plans and invoices and starts the separate provider checkout.
- Most older ERP pages still contain their own Bootstrap markup, duplicated inline styling and uneven loading, empty and error states. Those workflows need a full visual and functional pass.
- The platform dashboard was inspected without page-wide overflow at 360, 390, 412, 768, 1024 and 1280 pixels. School settings and subscription were inspected at 360 pixels in dark mode. The remaining school pages have not all been checked at these widths.
- Shared notification rendering now escapes dynamic content, but older page-specific interpolations still need a security review.

## Direction

Use a quiet education product identity: warm neutral page background, white surfaces, ink text, and a restrained deep teal accent. Keep the existing static HTML architecture and shared renderer while introducing consistent tokens, focus styles, controls, tables, cards, and mobile behavior. Let each dashboard prioritize actions and information for its role, with metrics sourced from the API. Use one icon set rather than emoji for the application shell.

## Screen inventory and review queue

| Role | Screens |
| --- | --- |
| Public | Login, forgot password, index redirect |
| Platform | Dashboard, schools, plans, subscriptions, activity, onboarding |
| School billing | Subscription status, payable plans, invoices, checkout |
| Admin | Dashboard, users, students/details, teachers/details, parents, academic years, departments, classes, sections, subjects, timetable, fees, notices, reports, audit logs, settings |
| Principal | Dashboard, students, teachers, attendance, performance, leave requests, complaints, notices, reports |
| Teacher | Dashboard, my classes, students, timetable, attendance, assignments, submissions, study materials, exams, marks, leave, profile |
| Student | Dashboard, timetable, attendance, assignments/details, study materials, exams, results, fees, notices, events, leave, documents, profile |
| Parent | Dashboard, children/profile, attendance, assignments, results, fees, notices, events, leave, messages, documents |

## Acceptance checks

For every screen: keyboard navigation and visible focus, appropriate landmarks/headings, valid labels and feedback, no horizontal page overflow, usable tables and forms on mobile, meaningful loading/empty/error states, and no fake data. The shared styling pass is only the foundation; each workflow needs visual and functional QA before declaring the redesign complete.
