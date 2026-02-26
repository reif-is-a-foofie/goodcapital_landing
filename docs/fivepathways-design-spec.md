# Five Pathways Design Spec — Implementation Reference

Extracted from https://fivepathways.com (Feb 2025)

---

## 1. Font Families

### Custom fonts (via @font-face)

| Alias | Actual Font | Source |
|-------|-------------|--------|
| **Neue** | Helvetica Neue LT Pro | `/_nuxt/fonts/HelveticaNeueLTPro-Roman.7216551.woff2` (400), `HelveticaNeueLTPro-Bd.544b940.woff2` (700) |
| **PPE** | PP Editorial New | `/_nuxt/fonts/PPEditorialNew-Regular.2512cb3.woff2`, `PPEditorialNew-Italic.1d7842d.woff2` |
| **Belle** | La Belle Aurore | `/_nuxt/fonts/LaBelleAurore.07bd0fd.woff2`, `LaBelleAurore.772713e.woff` |

### Usage by element

| Element | font-family |
|---------|-------------|
| **body** | Neue (Helvetica Neue LT Pro) |
| **h1** | PPE (PP Editorial New) |
| **h2** | PPE |
| **h3, h4** | PPE |
| **buttons** | inherit (Neue) |
| **labels** | PPE, italic |
| **.label** | PPE, italic |

### Fallback stack (base)

```
system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif
```

---

## 2. Button CSS — "Schedule a meeting"

### Base `.btn`

```css
.btn {
  border-radius: 999px;
  display: inline-flex;
  position: relative;
}
```

### `.btn__content` (main visible button)

```css
.btn__content {
  align-items: center;
  background-color: #63cfbf;
  border: 1px solid #000;
  border-radius: inherit;
  display: flex;
  height: 4.6rem;
  justify-content: space-between;
  min-height: 4.6rem;
  min-width: 100%;
  padding: 0 2rem;
  position: relative;
  transition: transform 0.5s cubic-bezier(0.19, 1, 0.22, 1);
  z-index: 2;
}
```

### `::after` pseudo-element (shadow/offset layer)

```css
.btn::after {
  background-image: url(/texture.png);
  background-size: cover;
  border: 1px solid #000;
  border-radius: inherit;
  content: "";
  height: 100%;
  left: 0;
  position: absolute;
  top: 0;
  transform: translate3d(0.5rem, 0.5rem, 0);
  transition: transform 0.5s cubic-bezier(0.19, 1, 0.22, 1);
  width: 100%;
  z-index: 1;
}
```

### Hover

```css
.btn:hover .btn__content {
  transform: translate3d(0.5rem, 0.5rem, 0);
}
.btn:hover .btn__arrow {
  transform: translateX(1rem);
}
```

### Light variant

```css
.btn.--light .btn__content {
  background-color: #fffaf5;
}
```

### Button typography

- Font: inherit (Neue)
- Font-size: inherit (body ~1.7–1.8rem)
- No explicit font-weight; text-decoration: none

### Arrow icon

- Height: 1.7rem
- Margin-left: 1.3rem
- Transition: transform 0.75s cubic-bezier(0.19, 1, 0.22, 1)

---

## 3. Page Structure / Layout

### Hero

- Flex column, centered
- `pt-85` (8.5rem) mobile → `s:pt-170` (17rem) desktop
- H1: `text-52` (5.2rem) mobile → `s:text-100` (10rem) desktop, `max-w-[100rem]`, centered
- Subtitle: `text-21` → `s:text-24`, `max-w-[22.5rem]` → `s:max-w-[55rem]`
- Button: `mt-25` below subtitle
- Background: canvas element with `pt-[40%]`, `s:-mt-200` overlap

### Section order

1. Hero (h1, subtitle, CTA)
2. “People are talking” (marquee logos)
3. “Get directions on the road to retirement” (intro + video)
4. “Journeys from the Past” (testimonials carousel)
5. Our Services
6. Products
7. Education / insights
8. Virtual Office
9. Mission
10. Question Jar form
11. Footer

### Grid / layout

- **site-grid**: 12 columns, `column-gap: 2.4rem`
- **site-max**: `max-width: 180rem`, `margin: 0 auto`, `padding: 1.5rem` (mobile) → `10rem` (≥650px)
- Breakpoints: `650px` (s), `769px` (m), `1024px` (l)

### Max-widths

- Hero h1: 100rem
- Hero subtitle: 22.5rem → 55rem
- Content sections: 65rem, 78.6rem, 82rem, etc.

---

## 4. Colors

### Backgrounds

| Name | Hex | RGB |
|------|-----|-----|
| **White (primary)** | #FFFAF5 | rgba(255, 250, 245) |
| **White off-dark** | #FAF5E8 | rgba(250, 245, 232) |
| **Green (button)** | #63cfbf | rgba(99, 207, 191) |
| **Blue** | #E7F2ED | rgba(231, 242, 237) |
| **Blue light** | #ecf3ea | rgba(236, 245, 245) |
| **Blue off-dark** | #ecf4f6 | rgba(236, 244, 246) |
| **Green light** | #eef3e7 | rgba(238, 243, 231) |
| **Yellow** | #fcefcf | rgba(252, 239, 207) |
| **Pink** | #fee3d9 | rgba(254, 227, 217) |
| **Black** | #000 | rgba(0, 0, 0) |

### Text

| Name | Hex | RGB |
|------|-----|-----|
| **Black** | #000 | rgba(0, 0, 0) |
| **Gray** | #504a4a | rgba(80, 74, 74) |
| **Gray light** | #aaaaaa | rgba(170, 170, 170) |
| **White** | #fffaf5 | rgba(255, 250, 245) |
| **Error** | #ff0000 | rgba(255, 0, 0) |

### Borders

- Primary: `#000` (1px solid)
- Gray: `rgba(151,151,151)` / `hsla(0,0%,59%,.4)`

### Section backgrounds

- Hero: transparent / canvas
- Navbar: transparent → `#fffaf5` when scrolled
- “People are talking”: default (white)
- “Get directions”: `bg-white-off-dark` (#FAF5E8)
- Testimonials: white cards on default
- Footer: varies by block

---

## 5. Typography

### Base

- `html`: `font-size: 10px` base, `clamp(5px, 16px, 10*100vw/var(--size))` with `--size: 375` (mobile) / `1800` (desktop)
- `body`: `font-family: Neue`, `font-size: 1.7rem` (mobile) → `1.8rem` (≥650px), `font-weight: 400`, `color: #000`

### Headings

| Class | font-family | font-size (mobile) | font-size (≥650px) | line-height |
|-------|-------------|--------------------|-------------------|-------------|
| **.h1** | PPE | 4.5rem | 10rem | 1 |
| **.h2** | PPE | 3.8rem | 7rem | 1.1 |
| **.h3** | PPE | 2.8rem | 4rem | 1.1 |
| **.label** | PPE | 2.1rem | 2.4rem | 1.4, italic |

### Hero

- H1: `font-2` (PPE), `text-52` → `s:text-100`, `leading-none`
- Subtitle: `text-21` → `s:text-24`

### Body / paragraphs

- `text-21` (2.1rem) → `s:text-24` (2.4rem)
- Line-height: 1.4–1.5 typical

### Utility sizes

- `text-12`: 1.2rem
- `text-14`: 1.4rem
- `text-15`: 1.5rem
- `text-16`: 1.6rem
- `text-17`: 1.7rem
- `text-18`: 1.8rem
- `text-20`: 2rem
- `text-21`: 2.1rem
- `text-24`: 2.4rem
- `text-26`: 2.6rem
- `text-28`: 2.8rem
- `text-42`: 4.2rem
- `text-52`: 5.2rem
- `text-100`: 10rem

### Line-heights

- `leading-none`: 1
- `leading-[1.4]`: 1.4
- `leading-[1.5]`: 1.5
- `leading-[.5]`: 0.5
- `leading-[1.15em]`: 1.15em
- `leading-[2em]`: 2em

### Letter-spacing

- Not explicitly set; uses default.

---

## 6. CSS Files / Sources

- **Framework**: Tailwind v2.2.19 + modern-normalize
- **Delivery**: Inline `<style>` in HTML (Nuxt SSR)
- **Fonts**: Served from `/_nuxt/fonts/`
- **Assets**: `/texture.png` (button shadow), `/arrow.svg`, `/q-mark.png`, `/menu-open.png`, `/quote-side.png`, `/pointing.png`, `/bbb-5-stars.svg`, `/enlighten/crossout.svg`

### Key custom rules (from inline CSS)

- `.site-grid`, `.site-max`, `.site-gutter`
- `.btn`, `.btn__content`, `.btn__arrow`
- `.h1`, `.h2`, `.h3`, `.label`
- `.uline-double`, `.multi-underline` (link underlines)
- `.sh` (sticky header)
- `.media-fill`, `.media-contain`
- `.touch-scroll` (carousel)

---

## Quick Reference — Button Implementation

```css
/* Fonts — use PP Editorial New / Helvetica Neue or equivalents */
@font-face {
  font-family: 'Neue';
  src: url('HelveticaNeueLTPro-Roman.woff2') format('woff2');
  font-weight: 400;
}
@font-face {
  font-family: 'PPE';
  src: url('PPEditorialNew-Regular.woff2') format('woff2');
  font-weight: 400;
}

/* Button */
.btn {
  border-radius: 999px;
  display: inline-flex;
  position: relative;
}
.btn__content {
  background-color: #63cfbf;
  border: 1px solid #000;
  border-radius: inherit;
  padding: 0 2rem;
  height: 4.6rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 100%;
  position: relative;
  z-index: 2;
  transition: transform 0.5s cubic-bezier(0.19, 1, 0.22, 1);
}
.btn::after {
  content: "";
  position: absolute;
  inset: 0;
  background-image: url(/texture.png);
  background-size: cover;
  border: 1px solid #000;
  border-radius: inherit;
  transform: translate(0.5rem, 0.5rem);
  z-index: -1;
}
.btn:hover .btn__content {
  transform: translate(0.5rem, 0.5rem);
}
```

---

*Generated from live page inspection. Font files must be obtained separately (PP Editorial New, La Belle Aurore are commercial). Helvetica Neue LT Pro has similar open alternatives (e.g. Helvetica Neue, system fonts).*
