Detailed plan for the Krita-ComfyUI script "Image enhance"

1) Architecture and modules
- Main dialog (PyQt) handling configuration, prompts, and execution.
- ComfyUI client (HTTP/JSON) to send a workflow, inject the image, and retrieve the output.
- Workflow manager: load by name, inject parameters (by name or ID), replace the "Load Image" node.
- Krita utilities: extract selected rectangles, export to temporary files, insert layers, apply a gradient mask.
- Configuration storage (server, paths, prompts, parameter lists) in a JSON file (Krita user directory).

2) User interface
- Text fields: server address, output folder path, global workflow name, face workflow name.
- Prompts: 1 "global prompt" field, 4 "face prompt 1..4" fields; keep current value (optional: in-session history).
- Variable parameters: two tables (global, face) with columns "Parameter name" and "Value"; Add/Remove buttons; simple validation (non-empty).
- Log area (QTextEdit read-only, monospace) + "Clear" button.
- Buttons: "Browse output", "Image enhance" (primary action), optional "Test connection".

3) Data preparation
- On "Image enhance" click: verify a document is open and non-empty.
- Get all rectangular selections from the active view; sort by ascending X (left to right) to order faces.
- Export the full image to a temporary PNG for the global workflow.
- For each rectangle, extract the corresponding portion to a temporary PNG (keep width/height and original position).
- Check ComfyUI output folder accessibility and build expected paths to collect results.

4) ComfyUI call: global workflow
- Load the global workflow by name (JSON file) from the configured workflows folder.
- Find the "Load Image" node (by name, otherwise by user-provided ID if needed) and inject the exported global image path.
- Inject the global prompt into the text node explicitly named "Prompt" (or by ID if name lookup fails).
- Apply user parameters: for each "Parameter name = Value", navigate the JSON and replace the targeted key (e.g. `Seed.value`, `CFG.value`, `15` if ID). Log replacements and flag missing targets.
- Send the request to ComfyUI (POST /prompt or equivalent), get the task ID, and poll until the output is available (or timeout).
- Once ready, locate the generated file in the configured output folder, load it into Krita as a new layer named "Global enhance" with 80% opacity.

5) ComfyUI call: face loop
- Choose the prompt per face: index 0 -> prompt 1, index 1 -> prompt 2, index 2 -> prompt 3, index >= 3 -> prompt 4.
- For each face:
  - Load the face workflow, inject the cropped image into "Load Image" (name or ID) and the selected prompt into the text node named "Prompt" (or by ID if needed).
  - Apply face parameters (same replacement logic as global).
  - Send the workflow to ComfyUI, wait for the output, retrieve the generated file.
  - Insert the image as a layer "Face enhance #n" positioned at the same offset as the source rectangle.
  - Apply a gradient mask on edges: fade width = 10% of the smallest dimension (min(w, h) * 0.1), linear gradient to transparent on each edge.
  - Set the layer opacity to 80%.

6) Parameter handling (name/ID)
- Data model: list of dicts `{ "target": "Seed.value", "value": "1452" }`.
- Injection: split `target` by "."; if the first segment is numeric, target a node ID; otherwise target by node name; apply the value on the final key.
- Error handling: if the key does not exist, log a warning without crashing; basic type validation (int/float if convertible).

7) Logging and errors
- Write every step to the log area: start/end global, start/end face n, parameter replacements, ComfyUI success/errors, output paths.
- If ComfyUI fails (HTTP error, timeout, missing output), show a message and exit the loop cleanly; keep the logs.
- "Clear log" resets the area; keep an internal buffer for possible unit tests.

8) Cleanup and persistence
- Remove temporary exported files after inserting layers.
- Save preferences (server, output folder, workflow names, prompts, parameters) when closing the dialog or after a successful run.
- Default path in Krita user directory (e.g. `~/.krita/comfy_config.json`).

9) Manual validation points
- No selection: only the global workflow runs; script should succeed.
- 1 to 3 faces: matching prompts used; layers inserted and masked.
- >=4 faces: face prompt 4 reused; verify the 10% fade on each face.
- Missing parameter target: warning log, no exception.
- ComfyUI timeout: clear message in the log, no Krita crash.
