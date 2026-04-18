# VR Black-Blink Bug Report — ESP32Camera Godot Project

**Date:** 2026-04-17  
**Status:** OPEN — v-sync fix applied, problem persists  
**Headset:** Meta Quest 2 via Oculus Link (USB)  
**Oculus App:** 72 Hz, Auto resolution @ 1.0x (3616×1856) — also tried lower  
**Godot:** 4.6, GL Compatibility renderer, D3D12 backend on Windows  
**OpenXR:** enabled at startup (`xr/openxr/enabled=true`)

---

## Symptom

VR view **blinks black** continuously while wearing headset. User describes it as
"being moved around the world back to origin all the time." This happens
regardless of whether the ESP32-CAM stream is connected or not (i.e., it's not a
stream texture issue — the world itself is flashing).

---

## Project Structure

```
Projects/ESP32-CAM-PlatformIO/Godot/
├── project.godot          — config: GL Compat, D3D12, OpenXR, Jolt physics
├── main.tscn              — scene tree (see below)
├── vr_main.gd             — OpenXR init script on root node
├── camera_stream.gd       — MJPEG stream consumer on Screen quad
├── servo_controller.gd    — head-to-servo UDP bridge
├── fullscreen_stream.gdshader — fullscreen clip-space quad shader
└── openxr_action_map.tres — default action map
```

### Scene Tree (main.tscn)

```
Main (Node3D)  [script: vr_main.gd]
├── WorldEnvironment
│   └── Environment: background_mode=1 (solid color), Color(0.03, 0.03, 0.05)
├── XROrigin3D
│   ├── XRCamera3D
│   │   └── Screen (MeshInstance3D, QuadMesh)  [script: camera_stream.gd]
│   │       └── material: ShaderMaterial → fullscreen_stream.gdshader
│   ├── LeftHand (XRController3D, tracker="left_hand")
│   └── RightHand (XRController3D, tracker="right_hand")
└── ServoController (Node)  [script: servo_controller.gd]
```

---

## What Has Been Tried (and Failed)

### 1. V-sync fix + session lifecycle signals (applied in this session)

`vr_main.gd` was rewritten to:
- Always disable v-sync via `DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)` on both init paths
- Match `Engine.physics_ticks_per_second` to headset refresh rate
- Connect `session_begun`, `session_visible`, `session_focussed`, `session_stopping`, `pose_recentered` signals
- Pause processing on visible state, unpause on focused state
- Type interface as `OpenXRInterface` for full API access

**Result:** Blinking persists.

### 2. Reduced Oculus render resolution

User lowered resolution below 1.0x in Oculus desktop app.

**Result:** No change.

---

## Remaining Hypotheses (ranked by likelihood)

### H1: Fullscreen shader POSITION override conflicts with stereo rendering (HIGH)

The `fullscreen_stream.gdshader` overrides `POSITION` in the vertex shader:
```glsl
POSITION = vec4(VERTEX.xy * 2.0, 0.0, 1.0);
```
This maps the quad to NDC clip space (-1..1), completely bypassing the 3D view
and projection matrices. In stereo XR rendering, each eye gets a different
projection matrix with asymmetric FOV. Overriding POSITION to fixed NDC means:

- The same image is rendered identically to both eyes (wrong parallax)
- The quad Z=0 with `depth_test_disabled` may **fight** with the OpenXR compositor's depth expectations
- The XR runtime may detect an "invalid" frame and alternate it with a reprojected/black frame

**Per Godot docs** (XR full screen effects page), the correct approach for XR fullscreen quads:
- Use a 2×2 QuadMesh (not 1×1 default)
- Use `skip_vertex_transform` render mode
- Apply `PROJECTION_MATRIX` offset to inner vertices for asymmetric FOV correction
- Use subdivision on the quad to have inner vs. edge vertices

The current shader does NOT use `skip_vertex_transform` and does NOT account for
`PROJECTION_MATRIX`. This is the most likely root cause.

### H2: Screen quad parented to XRCamera3D causes double-transform (MEDIUM)

The Screen MeshInstance3D is a **child of XRCamera3D**. The XR runtime moves
XRCamera3D every frame based on head tracking. The shader overrides POSITION to
fixed NDC, so the quad's 3D transform is ignored — but the engine may still
process the transform, and the interaction between a rapidly-moving parent and a
shader-overridden child may cause frame coherency issues.

### H3: CanvasLayer overlay in VR (LOW-MEDIUM)

`camera_stream.gd` creates a `CanvasLayer` (layer=100) with a `Label` child for
status overlays. CanvasLayer renders in 2D screen space. In XR mode, 2D canvas
rendering behavior is undefined/problematic. If visible=true during startup 
(before stream connects), this may cause rendering conflicts.

### H4: `Image.load_jpg_from_buffer()` + `ImageTexture.update()` every frame stalls GPU (LOW)

JPEG decode runs on the main thread. If a frame takes too long, the OpenXR
compositor will show a black frame. But user says blinking happens even without
stream connected, so this is secondary.

### H5: D3D12 backend + GL Compatibility + OpenXR incompatibility (LOW)

`project.godot` specifies:
```
rendering_device/driver.windows="d3d12"
renderer/rendering_method="gl_compatibility"
```
GL Compatibility doesn't use a RenderingDevice, so the d3d12 setting should be
irrelevant. However, the combination may have edge cases. Godot docs recommend
**Mobile** renderer for desktop VR, not GL Compatibility.

---

## Recommended Investigation Order

### Step 1: Test without the Screen quad entirely
Remove or hide the Screen MeshInstance3D node. Run with just the empty XR scene
(origin + camera + environment). If blinking stops → the shader or the quad is
the cause.

### Step 2: Fix the shader for XR stereo rendering
Replace the current `fullscreen_stream.gdshader` with an XR-aware version
following the Godot XR full screen effects docs:

```glsl
shader_type spatial;
render_mode depth_test_disabled, skip_vertex_transform, unshaded, cull_disabled;

uniform sampler2D stream_texture : source_color, filter_linear;

void vertex() {
    vec2 vert_pos = VERTEX.xy;
    if (length(vert_pos) < 0.99) {
        vec4 offset = PROJECTION_MATRIX * vec4(0.0, 0.0, 1.0, 1.0);
        vert_pos += (offset.xy / offset.w);
    }
    POSITION = vec4(vert_pos, 1.0, 1.0);
}

void fragment() {
    vec2 uv = vec2(1.0 - UV.x, 1.0 - UV.y);
    ALBEDO = texture(stream_texture, uv).rgb;
}
```
**NOTE:** This requires the QuadMesh to be 2×2 size with subdivisions (e.g.,
subdivide_width=1, subdivide_depth=1) so there are inner vertices for the
projection offset to apply to.

### Step 3: Remove CanvasLayer from XR
Replace the 2D CanvasLayer overlay with a `Label3D` or `SubViewport`-based
UI panel in 3D space, as CanvasLayer is not designed for XR.

### Step 4: Try Mobile renderer
Change `renderer/rendering_method` from `gl_compatibility` to `mobile` in
project.godot. Mobile renderer is Godot's officially recommended renderer for
desktop VR.

### Step 5: Test with Vulkan instead of D3D12
Remove the `rendering_device/driver.windows="d3d12"` line to let Godot default
to Vulkan, which has the most mature OpenXR integration.

---

## Files Reference

| File | Lines | Key concern |
|------|-------|-------------|
| `vr_main.gd` | 1–100 | XR init, v-sync, session lifecycle (already fixed) |
| `fullscreen_stream.gdshader` | 1–17 | POSITION override without skip_vertex_transform or PROJECTION_MATRIX — **primary suspect** |
| `main.tscn` | 1–46 | Scene tree, QuadMesh default 1×1 no subdivisions |
| `camera_stream.gd` | 1–415 | CanvasLayer overlay, stream processing, _apply_frame texture update |
| `project.godot` | 1–30 | GL Compat + D3D12 + OpenXR + Jolt |

---

## Environment Details

- **OS:** Windows
- **GPU:** Unknown (user did not report, but Oculus offered 3616×1856 at 1.0x which suggests decent hardware)
- **Oculus Link:** USB, 72 Hz selected
- **SteamVR:** Unknown if installed/active (OpenXR runtime could be Oculus or SteamVR)
- **Godot version:** 4.6

---

## Key Question for User

> Does the blinking happen even if you remove/hide the Screen quad entirely?
> (Run with just the empty VR scene — origin, camera, dark background.)
> This isolates whether it's a shader/rendering issue vs. an OpenXR runtime issue.
