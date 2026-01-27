# Krita plugins in this repository

## Contents
- **`comfy/`** — ComfyUI Image Enhance plugin. It sends the current image (and optional regions) to ComfyUI workflows, then re-inserts the results as new layers in Krita. Includes UI, config storage, HTTP client, workflow handling, and a short manual in `comfy/Manual.html`.
- **`select_face/`** — Helper script for face selection (WIP, does not work well).
- **`.desktop` files** — `comfy.desktop` and `select_face.desktop` register the plugins in Krita’s Scripts menu.
- **`temp/`, `comfy/input`, `comfy/output`** — Temporary working folders used during processing.

## Before you run it
Install the custom ComfyUI nodes required by the default workflow `comfy/workflows/Universal.json`. You can skip this if you plan tu use your own workflow.

### ComfyUI Impact Pack
For ImpactConditionalBranch, ImpactImageInfo, ImpactCompare and ImpactLogicalOperators nodes

### ComfyUI_TiledKSampler
For BNK_TiledKSampler node

### DZ_Face_Detailer
For DZ_Face_Detailer node

## Usage
1) Open Krita menu **Settings** -> **Dockers**.
2) Enable **ComfyUI Workflow**. The docker appears in the right panel (tool options area); you can drag it if needed.
3) Go to Tools -> Scripts -> ComfyUI Image Enhance.
4) In the dialog, set the ComfyUI server URL (see the manual).
5) Optionally select regions in your image (simple rectangle selections); they will be enhanced separately.
6) Click “Go” (global + regions) or “Regions” (regions only). Results appear as new layers in Krita, with fading borders.

## Things to know
- During the enhancing process, the Krita UI responds less frequently to user input, this is normal but will be fixed when possible.
- After some time using the comfy plugin, there will be a large amount of images in your comfyui output folder, so remember to clean the folder from time to time.
