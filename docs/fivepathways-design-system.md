# Five Pathways (fivepathways.com) Design System

> Extracted via Puppeteer from live site. Browser MCP was unavailable in session.

## Hero Section

| Property | Value |
|----------|-------|
| Background color | `rgba(0, 0, 0, 0)` (transparent; canvas/gradient likely used) |
| Background image | `none` |
| Text color | `rgb(0, 0, 0)` / `#000000` |
| Button background | `rgba(0, 0, 0, 0)` (transparent) |
| Button text | `rgb(0, 0, 0)` / `#000000` |
| Button border | `0px none` |
| Button border-radius | `0px` |
| Button padding | `0px 16px` |

## Buttons

| Property | Value |
|----------|-------|
| border-radius | `0px` |
| padding | `0px 16px` |
| background | `rgba(0, 0, 0, 0)` (transparent) |
| color | `rgb(0, 0, 0)` / `#000000` |
| border | `0px none rgb(0, 0, 0)` |
| font-family | `Neue` |

*Note: Buttons use underline styling (`.uline-double`). Menu toggle uses `rounded-[.25rem]`, `bg-white`, `border`.*

## Typography

| Element | Font Family | Font Size |
|---------|-------------|-----------|
| Body | Neue | 14.4px |
| H1 | PPE | 80px |
| H2 | PPE | 19.2px |
| Buttons | Neue | (inherited) |

## Section Backgrounds & Layout

| Section | Background | Display | Flex Direction |
|---------|------------|---------|----------------|
| 1 (Hero area) | transparent | flex | column |
| 2 | `rgb(250, 245, 232)` / `#FAF5E8` | block | row |
| 3 | transparent | block | row |
| 4 | transparent | flex | row |
| 5 | transparent | flex | column |
| 6 | `rgb(238, 243, 231)` / `#EEF3E7` | block | row |

**Section colors (hex):**
- Warm beige: `#FAF5E8`
- Light sage: `#EEF3E7`

## Navbar

| Property | Value |
|----------|-------|
| Background | `rgba(0, 0, 0, 0)` (transparent) |
| Text color | `rgb(0, 0, 0)` / `#000000` |
| Height | 131px |
| Border | `0px solid` |
| Border-bottom | `0px solid` |

*From HTML: `.sh` uses `text-black`, `py-20 s:py-40`. Menu toggle: `rounded-[.25rem]`, `bg-white`.*

## Summary (Design Tokens)

```json
{
  "colors": {
    "text": "#000000",
    "sectionBeige": "#FAF5E8",
    "sectionSage": "#EEF3E7"
  },
  "fonts": {
    "body": "Neue",
    "heading": "PPE"
  },
  "fontSizes": {
    "body": "14.4px",
    "h1": "80px",
    "h2": "19.2px"
  },
  "buttons": {
    "padding": "0px 16px",
    "borderRadius": "0px",
    "border": "none"
  },
  "navbar": {
    "height": "131px"
  }
}
```
