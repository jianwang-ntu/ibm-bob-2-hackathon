# Cover image

The cover image the lablab submission form asks for.

> **Cover Image:** Use PNG or JPG format with 16:9 aspect ratio.
> — lablab.ai Hackathon Rule Book, *Cover Image and Presentation*

The two canonical surfaces disagree on how hard that is: the Rule Book says
*use* 16:9, the Submission Guidelines say *recommended* 16:9. This is built at
**1920 × 1080**, which is 16:9 exactly, because that is the reading against us.

| | |
|---|---|
| file | `evidence/cover_image.png` |
| size | 1920 × 1080 (`1920 × 9 == 1080 × 16`) |
| build | `python3 make_cover.py` |
| controls | `python3 check_cover.py` |
| mutants | `python3 mutate_cover.py` |

## It is generated, not authored

Every number on the cover is read out of `../slides/evidence/*.json` at build
time — the auditor's own report files and one measured readback of the public
repository — and `check_cover.py` re-derives the same numbers **without
importing the builder**, then looks for them in the shipped pixels.

That is not decoration for this particular entry. The project's whole argument
is that a claim nothing can falsify is not evidence, so a cover whose figures no
control reads would be exactly the failure the tool exists to find.

## Finding a string inside a raster

A PDF carries a text stream, so the slide deck can be checked by extracting its
text. **A PNG carries none.** A number printed on a cover image is normally read
by a human and by nothing else.

So every string is placed at an **integer pixel origin**. That makes its
rasterisation position-independent — measured: the same string rendered at two
different integer origins crops to bit-identical ink — and lets the checker
render the string itself and slide it over the shipped image under zero-mean
normalised cross-correlation. NCC is invariant to the affine intensity map
between the template's white-on-black and the cover's grey-on-a-panel, so a
template never has to be told what colour it was drawn in.

**The bar is exactness, and that was learned by failing.** The first version of
`check_cover.py` accepted NCC ≥ 0.98 and the suite went red — correctly.
Changing one character of a 100-character absence line only moves the score to
0.9952, 0.9939 and 0.9823. A near-miss is not evidence that a string is on the
cover; it is evidence that something *like* it is. True lines score **1.0000**,
so the bar sits at 0.9995 and the separation is recorded in
`evidence/cover_controls.json`.

## Layout is measured, not eyeballed

The first draft was geometrically legal and visually broken: three panel
captions written over each other and a fourth running off the right edge of the
page. `make_cover.py` now measures every string with the real font metrics and
**refuses to write the file** if any text leaves the page, lands on other text,
escapes its own panel or straddles another panel's edge. `check_cover.py` feeds
that checker a deliberately overlapping layout, so a disarmed layout check is
itself caught.

## What the cover does not say

Three absences are drawn on the image and asserted by the control suite, so they
cannot be quietly cut:

- IBM Bob 2.0 has not been used on this project. Access opens at kickoff.
- Nothing in this repository's own audit is `DISCRIMINATING`: 5 of 5 are `WEAK`.
- There is no hosted demo URL: deploying one needs an account this entry
  does not hold.
