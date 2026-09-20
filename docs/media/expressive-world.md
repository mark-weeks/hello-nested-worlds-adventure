# Expressive world media: provenance and direction

Interface styling is defined in the [visual language](../design/visual-language.md); the [beta scene-art strategy](../design/beta-scene-art.md) distinguishes current assets from the proposed production pipeline.

## Visual direction

Four 1672 × 941 generated PNG plates form a connected journey through seed 382's
orchard, gallery, instrument and chain. They were created on 2026-09-20 with the
built-in image-generation tool. The tool did not return a separately identifiable
model revision. The orchard was generated first; the other three used it as a
visual reference. The outputs were copied unchanged into `static/media/places/`.
Hashes and file sizes are recorded in `static/media/manifest.json`.

The prompt briefs below summarize the actual generation direction; they are not
presented as verbatim transcripts. No third-party reference images were supplied.

| Asset | Canonical place and prompt brief |
|---|---|
| `orchard-v1.png` | Emberlit Orchard Terraces: monumental overgrown terraces, suspended lace of pollen, heat shimmer, copper light and deep teal shadow; an obsidian gallery as a landmark; cinematic ecological science fantasy; no text, characters or interface. |
| `gallery-v1.png` | Broken Ember Gallery: tall basalt ribs, smoke-tinged atmosphere, dusting of dew, flickering light and a woven-light instrument within; use the orchard reference for the same material world. |
| `instrument-v1.png` | Elder River Instrument: ancient damaged woven-light instrument, asymmetric filament ring, frost along its ridges, pressure-responsive exhalation, dark gallery background; retain the same copper/teal world. |
| `chain-v1.png` | Distant River Chain: macro-scale photoreactive helical structure, three interlaced strands, static mapping the surface, deep optical depth; related luminous matter at molecular scale. |

The scene does not overlay the current place’s scale, name or description. One
identity block in the interaction panel holds scale, name, position and a description
derived from current properties and persistent material traces. The original aspect
remains unchanged in world data.

The renderer uses node-derived atmosphere and material colors. New resonators,
energy, polarity, coherent memory and dismantling scars have their own live
presentation. Movement is subtle; reduced-motion preference removes time-driven
movement. Text and ordinary buttons retain the complete interaction.

A plate is used only while its aspect and material/silhouette anchors match.
For example, mending the broken instrument or changing the chain’s bond count
retires that plate from the current view; local rendering or provider enhancement
then describes the changed state. These plates do not constitute exact measured reconstructions. They require art
direction review, particularly recognizability across scales and correspondence
when the underlying place changes substantially. Revising media should create a
new asset version and update the applicable sensory interpretation; it must not
rewrite world birth or historical deltas.

## Recorded score sources

The eleven source performances are from **VSCO 2 Community Edition**, by Sam Gossner /
Versilian Studios and contributors. The project distributes these recordings under
[CC0 1.0](https://github.com/sgossner/VSCO-2-CE/blob/440300901dfe9275fd84e0b7763af1f8443ae62e/LICENSE).
The [official library page](https://versilian-studios.com/vsco-community/) describes
its scope and license. The full license is included as
`static/media/score/VSCO-LICENSE.txt`; exact source URLs and original WAV hashes
are retained in `static/media/score/sources.json`.

Pinned source commit: `440300901dfe9275fd84e0b7763af1f8443ae62e`.
The cello section, violin section, low/high harp, flute, tremolo violin, French
horn, bassoon, marimba, glockenspiel and pizzicato violin recordings are converted
from WAV with FFmpeg/libmp3lame. Added samples use quality 3 VBR; originals use
192 kb/s. Source recordings are CC0; no commercial film score is copied.

`static/score.js` writes eleven distinct forms (see `SCORE_PROFILES` and the pure
`scoreEvents` score), with a shared family motif. Long bowed membrane tides,
vacuum wind chords, a stellar procession, orbital polyrhythms, planetary horn
phrases, regional flute calls, enclosed harp echoes, close material gestures,
molecular hockets, atomic bells and subatomic sparks differ in instrumentation,
timing, register, articulation, silence, pan and reverberation. Sample peaks are
normalized on decode before per-voice dynamics and a master compressor. Atomic
partials and subatomic sparks also use sine synthesis.

Material and current properties change the form: object material/finish/fracture,
room lighting/ceiling/air, molecular bonds/geometry/reactivity, atomic ionization
and resonance, particle spin/coherence, and cosmic rotation/density/drift/hum.
A scale change fades old voices and starts the new language in 80ms; state changes
keep the transport and adopt the next direction at a phrase boundary. Listening
requires a gesture; mute and volume use one shared control per client.

The samples and all four plates ship locally, so testing this presentation does
not depend on a model key, external media provider, or per-visit generation cost.
Artistic acceptance and professional listening evaluation remain separate from
successful sample decoding and state-transition tests.
