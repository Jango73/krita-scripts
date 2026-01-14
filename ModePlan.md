# Plan: Simple/Advanced modes for Comfy plugin

## Goals
- Add a Simple/Advanced mode toggle with simple-only controls (Enhance, Random Seed).
- Keep Advanced as current behavior; Simple hides prompts/parameters by default with Show/Hide.
- Provide mode-specific defaults (simple vs advanced), without persisting mode state on toggle.
- Save/load parameter sets with all parameters, both modes, and slider values; loading sets switches mode.
- Add new placeholders derived from the simple sliders and apply them to defaults.

## Scope and files
- UI and behavior: `comfy/workflow_pane.py`
- Defaults and config persistence: `comfy/config_manager.py`
- Controller wiring and placeholder resolution: `comfy/comfyui_enhancer.py`
- Parameter set persistence: `comfy/parameter_set_manager.py`
- (Optional) docs update if needed: `comfy/Manual.html`

## Detailed steps

### 1) Defaults and config structure (config_manager.py)
- Keep current defaults as **advanced** defaults (no behavior change).
- Add **simple** defaults: same list as advanced but with:
  - Global/Region: `Seed = "{seed}"`, `Steps = "{steps}"`, `CFG = "{classifier-free-guidance}"`, `Denoise = "{denoise}"`.
- Add config keys for:
  - `params_global_simple`, `params_region_simple`
  - `params_global_advanced`, `params_region_advanced`
  - `mode` ("simple"|"advanced")
  - `enhance_value`, `random_seed`
- Load behavior:
  - If legacy `params_global/params_region` exist, treat as advanced values.
  - Populate missing simple defaults from the new simple lists.

### 2) Workflow pane UI changes (workflow_pane.py)
- Add a **mode toggle** button just above the “Parameter sets” group.
- Add a **simple controls** row (visible in both modes, but requested to be hidden in Advanced):
  - Enhance slider (0–100), default 20.
  - Random Seed slider (0–10000), default 0.
- Add a **Show/Hide** button (simple mode only) to toggle visibility of:
  - “Prompts” group
  - “Workflow parameters” group
  - Initial state in simple mode: hidden
- Expose getters/setters for:
  - current mode
  - simple slider values
  - advanced/simple parameter tables
- Switching mode:
  - No state persistence; keep current values in UI.
  - Only change visibility and which defaults are applied on reset.

### 3) Parameter set persistence (parameter_set_manager.py + workflow_pane.py)
- Save sets with:
  - `mode`
  - `prompts`
  - `params_simple` (global/regions)
  - `params_advanced` (global/regions)
  - `enhance_value`, `random_seed`
- Load behavior:
  - Restore prompts and all params.
  - Restore slider values.
  - Switch UI mode to the stored mode.
- Backward compatibility:
  - Old sets (without mode/simple data) default to advanced.

### 4) Controller wiring + placeholders (comfyui_enhancer.py)
- Populate UI from config:
  - Set mode, advanced params, simple params, sliders.
- Persist state on run:
  - Save current mode, both parameter sets, slider values, prompts.
- Add placeholder context:
  - `seed = random_seed`
  - `steps = round(5 + ((enhance/100) * 25))`
  - `classifier-free-guidance = 0`
  - `denoise = enhance/100`
- Ensure placeholders resolve for both global and region runs.

### 5) Manual update (if needed)
- Note new Simple/Advanced modes, Show/Hide, and new placeholders in `comfy/Manual.html`.

## Acceptance checklist
- Mode toggle works; Advanced unchanged.
- Simple shows sliders and hides prompts/parameters by default with Show/Hide.
- Simple defaults use the new placeholders; advanced defaults unchanged.
- Parameter sets store both modes and slider values; loading a set switches the mode.
- Placeholder values resolve with the correct formula.
