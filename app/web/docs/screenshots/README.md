# Before / after: design system adoption (issue #27)

Captured with `npm run screenshots` (Playwright 1.56, mock mode with MSW, reduced motion), resized to 560 px wide
JPEG. "Before" is `main` at 9e0ba92; "after" is this branch. Full-size PNGs of every screen are in
[`../../screenshots/`](../../screenshots/). In mobile full-page captures the bottom tab bar (`position: fixed`)
is drawn where the viewport ended; on a phone it stays at the bottom edge.

| Screen | Before | After |
| --- | --- | --- |
| Home (desktop, Tamil) | ![](before/desktop-01-home-ta.jpg) | ![](after/desktop-01-home-ta.jpg) |
| Lesson with a hint (mobile, Tamil) | ![](before/mobile-03-learn-brahmi-hint-ta.jpg) | ![](after/mobile-03-learn-brahmi-hint-ta.jpg) |
| Restore (desktop, Tamil) | ![](before/desktop-04-restore-ta.jpg) | ![](after/desktop-04-restore-ta.jpg) |
| Restore (mobile, Tamil) | ![](before/mobile-04-restore-ta.jpg) | ![](after/mobile-04-restore-ta.jpg) |
| Review queue (mobile) | ![](before/mobile-09-review-en.jpg) | ![](after/mobile-09-review-en.jpg) |
| About (mobile) | ![](before/mobile-10-about-en.jpg) | ![](after/mobile-10-about-en.jpg) |

New states (after only):

| Decided by rules + tutor-team explanation | 409 on a second review | Dark mode home | Dark mode restore |
| --- | --- | --- | --- |
| ![](after/desktop-11-learn-rules-en.jpg) | ![](after/mobile-12-review-409-en.jpg) | ![](after/mobile-13-home-dark-en.jpg) | ![](after/mobile-14-restore-dark-en.jpg) |
