# Walk me through this checkout bug

The most common ScreenMind workflow: hand Claude a screen recording and ask what happened.

## The situation

You hit a flaky bug in checkout — the cart total dropped to $0 and then an error dialog popped up. You captured a 12-second screen recording at `~/Desktop/checkout-bug.mov`. Instead of re-describing every click, you want Claude to trace the sequence itself.

## What you say to Claude

```text
I recorded the checkout bug at ~/Desktop/checkout-bug.mov. Walk me through what
happened — I want to know when the price dropped and when the error showed up.
```

## What ScreenMind does

```text
screenmind_watch(
  file_path="~/Desktop/checkout-bug.mov",
  focus="walk me through the bug"
)
```

ScreenMind extracts frames at 2fps (recording is under 15s), runs scene detection, dedups via SSIM, runs OCR on each kept frame, and writes a `report.md` to the session directory.

## Sample report

```markdown
# ScreenMind Report — session 2026-05-19-1847-checkout-bug

Source: /Users/alex/Desktop/checkout-bug.mov
Duration: 12.4s | Resolution: 2880x1800 | Extracted: 24 frames | Kept: 5

## Timeline

### Frame 01 — t=0.5s

Path: `~/.screenmind/sessions/2026-05-19-1847-checkout-bug/frame_001.png`
OCR: "Cart (2 items) | Crewneck Tee — $24.00 | Cotton Socks — $16.00 |
Subtotal $40.00 | [Checkout]"

### Frame 02 — t=3.1s — scene change

Path: `~/.screenmind/sessions/2026-05-19-1847-checkout-bug/frame_002.png`
OCR: "Shipping address | 1247 Mission St, San Francisco CA 94103 |
Standard shipping (5-7 days) — Free | [Continue to payment]"

### Frame 03 — t=4.2s — OCR delta 71%

Path: `~/.screenmind/sessions/2026-05-19-1847-checkout-bug/frame_003.png`
OCR: "Order summary | Subtotal $0.00 | Shipping Free | Tax $0.00 |
Total $0.00 | [Place order]"

### Frame 04 — t=5.3s — scene change

Path: `~/.screenmind/sessions/2026-05-19-1847-checkout-bug/frame_004.png`
OCR: "Something went wrong | We couldn't process your order. Error code
CHK_422_LINE_ITEMS_MISSING. Please try again or contact support. [OK]"

### Frame 05 — t=11.8s

Path: `~/.screenmind/sessions/2026-05-19-1847-checkout-bug/frame_005.png`
OCR: "Cart (0 items) | Your cart is empty | [Continue shopping]"
```

## What Claude does next

Claude scans the OCR diff and picks the two frames where things actually changed — frame 03 (price collapsed to $0) and frame 04 (error dialog). It reads both with the `Read` tool to confirm the visuals match the OCR, then summarizes behaviorally: "At 4.2s the subtotal flipped from $40.00 to $0.00 while still on the order summary page. The `CHK_422_LINE_ITEMS_MISSING` error appeared 1.1 seconds later. By 11.8s the cart was empty — the failed order cleared it."

## Why this beats screenshots

A screenshot tells Claude what one moment looks like. A ScreenMind report tells Claude what changed and when. You get a causal trace — "the price dropped, then the error fired" — instead of five static "I see a UI" descriptions. And Claude only loads the frames that matter, so the context cost stays small even on long recordings.
