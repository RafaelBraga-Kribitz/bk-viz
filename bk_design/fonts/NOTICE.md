# Typeface attribution

`BKribitz` and `BKribitz Mono` are this site's typefaces: **modified, renamed
cuts of Geist and Geist Mono**, under the SIL Open Font License 1.1.

| Face | Files | Derived from | Upstream licence |
| --- | --- | --- | --- |
| BKribitz 400, 400 italic, 500, 600, 700, 800, 900 | `BKribitz-*.woff2` | [Geist](https://github.com/vercel/geist-font) — Vercel, in collaboration with basement.studio | SIL OFL 1.1 — `OFL-Geist.txt` |
| BKribitz Mono 400, 500, 700 | `BKribitzMono-*.woff2` | [Geist Mono](https://github.com/vercel/geist-font) — as above | SIL OFL 1.1 — `OFL-Geist.txt` |

Geist declares no Reserved Font Name.

## What was changed

1. **Glyphs added to every face**: Greek, mathematical operators, superior
   and inferior operators and letters, double-struck sets, arrows and
   currency signs that Geist does not draw, built from each face's own
   measurements.
2. **A slashed zero** drawn into BKribitz as the default `0`, and into its
   tabular, fraction, superior and inferior zeros. BKribitz Mono's zero is
   Geist Mono's, already slashed.
3. **Subsetted** to Latin, Latin Extended-A/B, Greek, punctuation, super-
   and subscripts, currency, letterlike and number forms, arrows, maths and
   brackets.
4. **Renamed** to BKribitz and BKribitz Mono, as SIL OFL 1.1 clause 3 asks
   of a Modified Version, so that a locally installed Geist can never be
   substituted for them.

Geist's own outlines, spacing, kerning and OpenType features are otherwise
untouched. The site ships the ten subsetted woff2 files listed above; they
are built outside this repository.

The licence is reproduced in this folder (`OFL-Geist.txt`).
