# Cinematic storyboard: Earth System Trend Detective (7 slides)

Design goal: one continuous "motion picture" instead of seven separate pages. A few **persistent elements**
stay on screen and morph between slides, while each slide's content arrives in staggered layers.
Built into the web slides (`docs/index.html`, live at https://bishreldev.github.io/earth-system-trend-detective/).
A "PowerPoint" note under each slide explains how to get the same effect with Morph/Push if the deck is ever
rebuilt in PowerPoint.

## Look and feel

| Element | Choice |
| --- | --- |
| Canvas | 16:9 (1920 × 1080), near-black navy `#0b0f17`, high contrast, lots of negative space |
| Signature image | **Mongolia's temperature stripes**: 45 vertical bars, one per year 1981-2025, coloured by the country-average temperature difference from 1981-2010 (blue cooler, red warmer). Real NASA POWER / MERRA-2 data. Style inspired by Ed Hawkins' "warming stripes". |
| Headline font | Archivo, expanded width (125%), heavy weight, uppercase for the title |
| Kicker font | Small caps-style uppercase with wide tracking (0.3em), accent orange `#ff6b4a` |
| Body font | Inter, regular/semibold, 26-34 px on the canvas |
| Accent colours | Orange `#ff6b4a` (warming, calls to action), teal `#2dd4bf` (water/wind), gold `#fbbf24` |
| Grid | Rule of thirds: vertical lines at x = 640 and 1280, horizontal at y = 360 and 720. Text anchors on the left third, visuals fill the right two thirds. |

## Persistent (morphing) elements

1. **Title → logo.** The huge "EARTH SYSTEM TREND DETECTIVE" title on slide 1 shrinks and glides to the top-left
   corner, where it stays as a small logo for slides 2-7.
2. **Stripes.** Full-bleed backdrop on slide 1, dimmed and slowly panning (parallax) on slides 2-4 and 6,
   collapsing into a horizontal **timeline band** on slide 5, and zooming back out to full-bleed on slide 7.

## Slide by slide

### 1 · Cold open: the title card
- **Visual:** the stripes wipe in from left to right (1981 → 2025), under a dark left-to-right shade so the text stays readable.
- **Layout:** title block on the left third; tagline under it; team block on the lower-left third line; a one-line
  explanation of the stripes in the bottom-right corner (negative space everywhere else).
- **Motion:** stripes wipe (1.6 s) → title fades in while its letter spacing tightens from wide to normal (a classic film-title move) → tagline and team rise in.
- **PowerPoint:** put a rectangle the same colour as the background over the stripes and animate it with a *Wipe* exit; title uses *Fade* + *Grow/Shrink* on character spacing.

### 2 · The case
- **Visual:** stripes dimmed to 10%, shifted slightly left (the camera has started moving).
- **Layout:** the question as a big headline across the top two thirds; two cards ("Why it's hard", "Why it matters in Mongolia") side by side below the lower third line.
- **Motion:** *Push* from the right; title morphs into the corner logo; cards rise in one after the other.
- **PowerPoint:** *Morph* transition. Duplicate slide 1, shrink the title into the corner on the copy, keep the same object names so Morph pairs them.

### 3 · The tool
- **Visual:** the real app screenshot, tilted in 3D, swings flat as it slides in (a "product reveal").
- **Layout:** four numbered steps (What? Where? When? Is it real?) on the left third; screenshot fills the right two thirds.
- **Motion:** screenshot rotates from 18° to flat; steps appear one by one.
- **PowerPoint:** *Morph*; place the screenshot **off the right edge of the slide** on slide 2 and in position on slide 3, so Morph flies it in.

### 4 · Detective tools (interactive)
- **Visual:** the live trend map of Mongolia (hover any cell) and the "what is changing" scanner.
- **Layout:** map on the left 60% (its centre sits on the left third line), scanner card on the right third.
- **Motion:** map "focuses" in (slight zoom-out plus blur to sharp, like a lens pull); scanner slides in from the right.
- **Interaction:** buttons switch the variable; **▶ Year by year** plays the 1981-2025 animation.
- **PowerPoint:** *Push* from right; use *Zoom* entrance on the map image.

### 5 · The evidence: the timeline
- **Visual:** the stripes collapse from the backdrop into a horizontal **timeline band** across the middle of the slide (the morph).
- **Timeline without clutter:** only five year labels (1981, 1990, 2000, 2010, 2025) and three callout pins (coldest year, hottest year, latest year). A glowing scan line pans across the band from 1981 to 2025 while a year readout follows it. Hovering any stripe shows its year and value.
- **Layout:** headline top-left; band between the two horizontal third lines; three big statistics count up along the bottom third; data-source chips under them.
- **Motion:** band morph (1.1 s) → scan line pans (2.6 s) → pins drop in → numbers count up.
- **PowerPoint:** *Morph*. Group the stripes on slide 4 full-size, and on slide 5 resize the same group into the band. For the scan line, place a thin line **just off the left edge** on slide 5a and **just off the right edge** on a duplicate 5b, then Morph between them for a horizontal pan.

### 6 · The twist: not evenly
- **Visual:** big interactive chart, two views: **Seasons at 5 sites** and **Warm Arctic vs Ulaanbaatar**.
- **Layout:** short story text on the left third (three lines max); chart on the right two thirds.
- **Motion:** *Push*; chart rises in; stripes return to the dim backdrop.
- **PowerPoint:** *Push*; build the two charts on two slides and use Morph between them for the toggle.

### 7 · Closing: pull back
- **Visual:** the stripes zoom back out to full-bleed (the camera pulls back to the opening shot).
- **Layout:** closing line on the left third; next steps; "Try it" card with the app and code links on the right third; credits and the AI note along the bottom.
- **Motion:** *Zoom out* of the stripes; text staggers in; call-to-action button glows once.
- **PowerPoint:** *Morph* from slide 6 with the stripes group enlarged back to full slide size; end with *Fade through black*.

## Timing (for a live pitch)

About 20-30 seconds per slide, 3 minutes in total. Every motion is under 3 seconds, so the presenter never waits for an animation. Motion is switched off automatically for viewers who set "reduce motion" in their system settings.
