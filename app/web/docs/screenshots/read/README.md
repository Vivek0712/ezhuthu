# Upload + OCR screenshots (mock mode, MSW)

Restore page after the Upload + OCR change: `1-upload` (photo tab, default), `2-reading` (the experimental reading of the
"weathered stone" sample, editable lines with confidence), `3-epidoc` (a DHARMA EpiDoc file, `<supplied>` shown as
gaps). Mock mode: every photo gets the same canned reading, and the mock's EpiDoc parsing is rougher than the server's
(`src/ezhuthu/agent/reader.py`). Captured with Playwright, reduced motion, then downscaled.
