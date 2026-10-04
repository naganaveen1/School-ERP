# Design system

The source of truth is `frontend/css/themes.css` for semantic tokens and `frontend/css/design-system.css` for shared components and overrides. Existing Bootstrap classes remain during migration so current screens continue to work.

## Foundations

- Typography: system UI stack; page title 24px, section title 16px, body 14px, helper/caption 12px. Maintain a readable line height and visible hierarchy.
- Spacing: a 4px base scale (`--space-1` through `--space-8`); major page sections use 24px or 32px.
- Color: neutral background/surface/text with one teal action accent. Success, warning, danger, and info mean the same thing everywhere. Do not use color alone to communicate status.
- Shape: 6px controls, 10px cards, restrained borders, subtle shadows.
- Focus: a visible two-pixel ring on interactive controls. Touch targets should approach 44px where space allows.
- Motion: 150–200ms transitions, disabled under `prefers-reduced-motion`.

## Components

The shared stylesheet covers shell, sidebar, header, page header, buttons, inputs, cards, tables, badges, dropdowns, modals, alerts, empty states, and responsive behavior. The shared JavaScript renderer owns shell structure and role navigation. New components should reuse these classes/tokens; avoid new inline colors and spacing.

## Themes

Light, dark, and system mode use semantic variables. Preference is stored as `school-erp-theme`. The `data-theme` attribute on `<html>` is the applied theme; system mode follows `prefers-color-scheme`. Any new chart or screen-specific element must use semantic colors and be inspected in both themes.
