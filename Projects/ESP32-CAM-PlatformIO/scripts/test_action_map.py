"""
Validate the OpenXR action map .tres file for the Oculus Touch controller profile.

Checks:
1. Profile exists: /interaction_profiles/oculus/touch_controller
2. The "primary" action (Vector2 thumbstick) is defined with action_type=2
3. The profile has bindings for primary → thumbstick (both hands)
4. No invalid binding paths for Oculus Touch (grip_surface, system/click)
5. All referenced sub_resource IDs in bindings exist in the file
"""

import re
import sys
from pathlib import Path

TRES_PATH = Path(__file__).resolve().parents[1] / "Godot" / "openxr_action_map.tres"

# Valid Oculus Touch binding paths (subset — focus on what we use)
VALID_OCULUS_TOUCH_PATHS = {
    "/user/hand/left/input/aim/pose",
    "/user/hand/right/input/aim/pose",
    "/user/hand/left/input/grip/pose",
    "/user/hand/right/input/grip/pose",
    "/user/hand/left/input/menu/click",
    "/user/hand/left/input/x/click",
    "/user/hand/left/input/x/touch",
    "/user/hand/left/input/y/click",
    "/user/hand/left/input/y/touch",
    "/user/hand/right/input/a/click",
    "/user/hand/right/input/a/touch",
    "/user/hand/right/input/b/click",
    "/user/hand/right/input/b/touch",
    "/user/hand/left/input/trigger/value",
    "/user/hand/right/input/trigger/value",
    "/user/hand/left/input/trigger/touch",
    "/user/hand/right/input/trigger/touch",
    "/user/hand/left/input/squeeze/value",
    "/user/hand/right/input/squeeze/value",
    "/user/hand/left/input/thumbstick",
    "/user/hand/right/input/thumbstick",
    "/user/hand/left/input/thumbstick/click",
    "/user/hand/right/input/thumbstick/click",
    "/user/hand/left/input/thumbstick/touch",
    "/user/hand/right/input/thumbstick/touch",
    "/user/hand/left/input/thumbrest/touch",
    "/user/hand/right/input/thumbrest/touch",
    "/user/hand/left/output/haptic",
    "/user/hand/right/output/haptic",
}

# Paths known to be INVALID for oculus/touch_controller
INVALID_OCULUS_TOUCH_PATHS = {
    "grip_surface",
    "system/click",
    "system/touch",
    "select/click",
}


def parse_sub_resources(text: str) -> dict[str, dict[str, str]]:
    """Parse [sub_resource ...] blocks into {id: {key: value}} dicts."""
    resources = {}
    current_id = None
    current = {}

    for line in text.splitlines():
        m = re.match(r'\[sub_resource type="(\w+)" id="(\w+)"\]', line)
        if m:
            if current_id:
                resources[current_id] = current
            current_id = m.group(2)
            current = {"_type": m.group(1)}
            continue
        if current_id and "=" in line:
            key, _, val = line.partition("=")
            current[key.strip()] = val.strip().strip('"')

    if current_id:
        resources[current_id] = current

    return resources


def extract_sub_resource_refs(text: str) -> list[str]:
    """Extract SubResource("id") references from a string."""
    return re.findall(r'SubResource\("(\w+)"\)', text)


def main() -> int:
    if not TRES_PATH.exists():
        print(f"FAIL: Action map not found at {TRES_PATH}")
        return 1

    text = TRES_PATH.read_text(encoding="utf-8")
    resources = parse_sub_resources(text)
    errors = []
    warnings = []

    # --- Test 1: Find all OpenXRAction resources and the "primary" action ---
    actions = {rid: r for rid, r in resources.items() if r["_type"] == "OpenXRAction"}
    primary_action_id = None
    for rid, r in actions.items():
        if r.get("resource_name") == "primary":
            primary_action_id = rid
            action_type = r.get("action_type", "?")
            if action_type != "2":
                errors.append(
                    f"'primary' action (id={rid}) has action_type={action_type}, "
                    f"expected 2 (Vector2)"
                )
            else:
                print(f"OK: 'primary' action found (id={rid}) with action_type=2 (Vector2)")
            break

    if not primary_action_id:
        errors.append("'primary' action not found in action map")

    # --- Test 2: Find Oculus Touch profile ---
    profiles = {
        rid: r
        for rid, r in resources.items()
        if r["_type"] == "OpenXRInteractionProfile"
    }
    oculus_profile_id = None
    for rid, r in profiles.items():
        if "oculus/touch_controller" in r.get("interaction_profile_path", ""):
            oculus_profile_id = rid
            print(f"OK: Oculus Touch profile found (id={rid})")
            break

    if not oculus_profile_id:
        errors.append(
            "No interaction profile with path 'oculus/touch_controller' found"
        )
        for rid, r in profiles.items():
            print(f"  Found profile: {r.get('interaction_profile_path', '?')} (id={rid})")

    # --- Test 3: Check profile is in the top-level interaction_profiles list ---
    resource_line = [l for l in text.splitlines() if l.startswith("interaction_profiles")]
    if resource_line:
        top_refs = extract_sub_resource_refs(resource_line[0])
        if oculus_profile_id and oculus_profile_id not in top_refs:
            errors.append(
                f"Oculus Touch profile (id={oculus_profile_id}) not in "
                f"top-level interaction_profiles list"
            )
        else:
            print("OK: Oculus Touch profile is in top-level interaction_profiles")

    # --- Test 4: Check bindings in Oculus Touch profile ---
    if oculus_profile_id:
        profile_res = resources[oculus_profile_id]
        binding_refs_raw = profile_res.get("bindings", "")
        binding_ids = extract_sub_resource_refs(binding_refs_raw)

        has_primary_left = False
        has_primary_right = False

        for bid in binding_ids:
            binding = resources.get(bid)
            if not binding:
                errors.append(f"Binding id={bid} referenced but not defined")
                continue

            action_ref = binding.get("action", "")
            action_id_match = re.search(r'SubResource\("(\w+)"\)', action_ref)
            action_id = action_id_match.group(1) if action_id_match else "?"
            path = binding.get("binding_path", "")

            # Check for invalid paths
            for invalid in INVALID_OCULUS_TOUCH_PATHS:
                if invalid in path:
                    errors.append(
                        f"Invalid binding path for Oculus Touch: '{path}' "
                        f"(contains '{invalid}') — binding id={bid}"
                    )

            # Check for primary thumbstick binding
            if action_id == primary_action_id:
                if "left" in path and "thumbstick" in path and "/click" not in path and "/touch" not in path:
                    has_primary_left = True
                    print(f"OK: primary → {path} (left thumbstick)")
                if "right" in path and "thumbstick" in path and "/click" not in path and "/touch" not in path:
                    has_primary_right = True
                    print(f"OK: primary → {path} (right thumbstick)")

        if not has_primary_left:
            errors.append("Missing binding: primary → left/input/thumbstick")
        if not has_primary_right:
            errors.append("Missing binding: primary → right/input/thumbstick")

        print(f"OK: {len(binding_ids)} total bindings in Oculus Touch profile")

    # --- Test 5: Check all binding IDs exist ---
    all_binding_ids = set()
    for rid, r in profiles.items():
        refs = extract_sub_resource_refs(r.get("bindings", ""))
        for ref in refs:
            if ref not in resources:
                errors.append(f"Profile {rid}: references binding {ref} which doesn't exist")
            all_binding_ids.add(ref)

    # --- Summary ---
    print()
    if warnings:
        for w in warnings:
            print(f"WARN: {w}")
    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        print(f"\n{len(errors)} error(s) found")
        return 1
    else:
        print("ALL TESTS PASSED — action map looks correct")
        return 0


if __name__ == "__main__":
    sys.exit(main())
