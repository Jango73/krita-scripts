# Universal workflow - ASCII path scenarios

Source: `comfy/workflows/Universal.json` (current state)

Assumed defaults for all unspecified toggles:
- `Img2img` (65) = `false`
- `Scale input` (92) = `false`
- `Refine stage 1` (30) = `false`
- `Refine stage 2` (36) = `false`
- `Face detailer` (63) = `false`
- Therefore:
  - `113 = OR(112, Face detailer) = false`
  - `119 = AND(113, Initial stage) = false` when `Initial stage=true`
  - `114` selects `ff_value` in both scenarios below.

Legend:
- `-->` active selected branch
- `-x->` branch not selected by condition

## Scenario 1
`Keep original size input` (115) = `false`
`Initial stage` (117) = `true`
All other toggles = default values above.

```text
IMAGE side feeding img2img encoder path

[Input 40]
   --> [Cond-Original-Size-Input 103, cond=115=false]
       -x-> tt: Input direct (214)
       --> ff: Scaled Input via [ImageScale 42] (215)
   --> [Cond-Half-1 95, cond=Scale input 92=false]
       -x-> tt: ScaleBy path (188)
       --> ff: from 103 (216)
   --> [VAEEncode 41] --> latent(184)

LATENT core

[EmptyLatentImage 21] --(143)--> [Cond-Img2img 66, cond=Img2img 65=false] <--(184)-- [VAEEncode 41]
                                   --> selected: ff = EmptyLatent (145/198/241)

[Cond-Img2img 66] --(145)--> [KSampler 3] --(240)--> [Cond-Initial-Stage 118, cond=Initial stage 117=true]
[Cond-Img2img 66] ------------------------(241)----> [Cond-Initial-Stage 118]
                                                     --> selected: tt = KSampler output

[KSampler path image detour]
[Cond-Initial-Stage 118] --(31)--> [VAEDecode 16] --> [ImageUpscaleWithModel 15] --> [VAEEncode 24] --(232)-> [114.tt]
[Cond-Initial-Stage 118] -----------------------------------------------(233)-------------------------> [114.ff]

[Cond-Initial-Upscale 119 = false] --> [Cond-Original-Size 114] selects ff (= from 118)

Final gate before downstream samplers/decoders:
[Cond-Img2img 66] --(198)--> [Cond-Original-Size 97, cond=115=false]
[Cond-Original-Size 114] --(234)--> [Cond-Original-Size 97]
                                   --> selected: ff = from 114 = from 118 = KSampler output
```

## Scenario 2
`Keep original size input` (115) = `true`
`Initial stage` (117) = `true`
All other toggles = default values above.

```text
IMAGE side feeding img2img encoder path

[Input 40]
   --> [Cond-Original-Size-Input 103, cond=115=true]
       --> tt: Input direct (214)
       -x-> ff: Scaled Input via [ImageScale 42] (215)
   --> [Cond-Half-1 95, cond=Scale input 92=false]
       -x-> tt: ScaleBy path (188)
       --> ff: from 103 (216) = Input direct
   --> [VAEEncode 41] --> latent(184)

LATENT core

[EmptyLatentImage 21] --(143)--> [Cond-Img2img 66, cond=Img2img 65=false] <--(184)-- [VAEEncode 41]
                                   --> selected: ff = EmptyLatent (145/198/241)

[Cond-Img2img 66] --(145)--> [KSampler 3] --(240)--> [Cond-Initial-Stage 118, cond=Initial stage 117=true]
[Cond-Img2img 66] ------------------------(241)----> [Cond-Initial-Stage 118]
                                                     --> selected: tt = KSampler output

[Cond-Initial-Upscale 119 = false] --> [Cond-Original-Size 114] selects ff (= from 118)

Final gate before downstream samplers/decoders:
[Cond-Img2img 66] --(198)--> [Cond-Original-Size 97, cond=115=true]
[Cond-Original-Size 114] --(234)--> [Cond-Original-Size 97]
                                   --> selected: tt = from 66 = EmptyLatent

Resulting difference vs Scenario 1:
- Scenario 1 (`115=false`): node 97 takes the branch that carries node 118/KSampler result.
- Scenario 2 (`115=true`): node 97 takes node 66 branch, bypassing node 118/114 output at this gate.
```
