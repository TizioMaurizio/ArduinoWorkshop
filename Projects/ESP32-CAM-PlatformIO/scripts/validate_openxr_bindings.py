#!/usr/bin/env python3
"""Validate OpenXR action map bindings against the OpenXR specification.

Checks each interaction profile's bindings for:
1. Invalid paths (not in the spec for that profile)
2. Duplicate action bindings on the same input path (same action set)
3. Action type mismatches (e.g. Vector2 action bound to a click path)
"""

import re
import sys
from pathlib import Path
from collections import defaultdict

# OpenXR spec: valid component paths per interaction profile
# Source: OpenXR 1.1 specification, Chapter 6.4
VALID_PATHS = {
    "/interaction_profiles/khr/simple_controller": {
        "/user/hand/left/input/select/click",
        "/user/hand/left/input/menu/click",
        "/user/hand/left/input/grip/pose",
        "/user/hand/left/input/aim/pose",
        "/user/hand/left/output/haptic",
        "/user/hand/right/input/select/click",
        "/user/hand/right/input/menu/click",
        "/user/hand/right/input/grip/pose",
        "/user/hand/right/input/aim/pose",
        "/user/hand/right/output/haptic",
        # Palm pose extension
        "/user/hand/left/input/palm_ext/pose",
        "/user/hand/right/input/palm_ext/pose",
        # Godot uses grip_surface as alias — allow but warn
        "/user/hand/left/input/grip_surface/pose",
        "/user/hand/right/input/grip_surface/pose",
    },
    "/interaction_profiles/oculus/touch_controller_profile": {
        # Left hand
        "/user/hand/left/input/x/click",
        "/user/hand/left/input/x/touch",
        "/user/hand/left/input/y/click",
        "/user/hand/left/input/y/touch",
        "/user/hand/left/input/menu/click",
        "/user/hand/left/input/squeeze/value",
        "/user/hand/left/input/trigger/value",
        "/user/hand/left/input/trigger/touch",
        "/user/hand/left/input/thumbstick",
        "/user/hand/left/input/thumbstick/click",
        "/user/hand/left/input/thumbstick/touch",
        "/user/hand/left/input/thumbrest/touch",
        "/user/hand/left/input/grip/pose",
        "/user/hand/left/input/aim/pose",
        "/user/hand/left/output/haptic",
        # Right hand
        "/user/hand/right/input/a/click",
        "/user/hand/right/input/a/touch",
        "/user/hand/right/input/b/click",
        "/user/hand/right/input/b/touch",
        "/user/hand/right/input/system/click",  # may be reserved
        "/user/hand/right/input/squeeze/value",
        "/user/hand/right/input/trigger/value",
        "/user/hand/right/input/trigger/touch",
        "/user/hand/right/input/thumbstick",
        "/user/hand/right/input/thumbstick/click",
        "/user/hand/right/input/thumbstick/touch",
        "/user/hand/right/input/thumbrest/touch",
        "/user/hand/right/input/grip/pose",
        "/user/hand/right/input/aim/pose",
        "/user/hand/right/output/haptic",
        # Palm pose extension
        "/user/hand/left/input/palm_ext/pose",
        "/user/hand/right/input/palm_ext/pose",
    },
    "/interaction_profiles/microsoft/motion_controller": {
        # Left
        "/user/hand/left/input/menu/click",
        "/user/hand/left/input/squeeze/click",
        "/user/hand/left/input/trigger/value",
        "/user/hand/left/input/thumbstick",
        "/user/hand/left/input/thumbstick/click",
        "/user/hand/left/input/trackpad",
        "/user/hand/left/input/trackpad/click",
        "/user/hand/left/input/trackpad/touch",
        "/user/hand/left/input/grip/pose",
        "/user/hand/left/input/aim/pose",
        "/user/hand/left/output/haptic",
        # Right
        "/user/hand/right/input/menu/click",
        "/user/hand/right/input/squeeze/click",
        "/user/hand/right/input/trigger/value",
        "/user/hand/right/input/thumbstick",
        "/user/hand/right/input/thumbstick/click",
        "/user/hand/right/input/trackpad",
        "/user/hand/right/input/trackpad/click",
        "/user/hand/right/input/trackpad/touch",
        "/user/hand/right/input/grip/pose",
        "/user/hand/right/input/aim/pose",
        "/user/hand/right/output/haptic",
        # Extensions
        "/user/hand/left/input/palm_ext/pose",
        "/user/hand/right/input/palm_ext/pose",
        "/user/hand/left/input/grip_surface/pose",
        "/user/hand/right/input/grip_surface/pose",
    },
}

# Action types from OpenXR/Godot
ACTION_TYPE_NAMES = {0: "Bool", 1: "Float", 2: "Vector2", 3: "Pose", 4: "Haptic"}

# Which binding path suffixes are compatible with which action types
PATH_TYPE_COMPAT = {
    "/click": {0, 1},       # Bool or Float
    "/touch": {0, 1},       # Bool or Float
    "/value": {0, 1},       # Float (Bool via conversion)
    "/force": {0, 1},       # Float
    "/pose":  {3},           # Pose
    "/haptic": {4},          # Haptic
}
# Bare paths (no suffix after the component name) = Vector2
# e.g., /input/thumbstick, /input/trackpad


def parse_tres(filepath):
    """Parse the .tres file and extract actions, bindings, and profiles."""
    text = Path(filepath).read_text(encoding="utf-8")

    # Parse all sub_resources
    actions = {}      # id -> {name, type, localized_name}
    bindings = {}     # id -> {action_id, path}
    profiles = {}     # id -> {path, binding_ids}

    # Extract actions
    for m in re.finditer(
        r'\[sub_resource type="OpenXRAction" id="([^"]+)"\]\s*'
        r'resource_name = "([^"]+)"\s*'
        r'localized_name = "([^"]+)"\s*'
        r'(?:action_type = (\d+)\s*)?',
        text
    ):
        aid, name, loc_name, atype = m.groups()
        actions[aid] = {
            "name": name,
            "localized_name": loc_name,
            "type": int(atype) if atype else 0,  # default = Bool
        }

    # Extract bindings
    for m in re.finditer(
        r'\[sub_resource type="OpenXRIPBinding" id="([^"]+)"\]\s*'
        r'action = SubResource\("([^"]+)"\)\s*'
        r'binding_path = "([^"]+)"',
        text
    ):
        bid, action_id, path = m.groups()
        bindings[bid] = {"action_id": action_id, "path": path}

    # Extract profiles
    for m in re.finditer(
        r'\[sub_resource type="OpenXRInteractionProfile" id="([^"]+)"\]\s*'
        r'interaction_profile_path = "([^"]+)"\s*'
        r'bindings = \[([^\]]*)\]',
        text
    ):
        pid, profile_path, binding_refs = m.groups()
        binding_ids = re.findall(r'SubResource\("([^"]+)"\)', binding_refs)
        profiles[pid] = {"path": profile_path, "binding_ids": binding_ids}

    return actions, bindings, profiles


def check_path_type_compat(binding_path, action_type):
    """Check if a binding path is compatible with an action type."""
    # Haptic output
    if "/output/haptic" in binding_path:
        return action_type == 4

    # Check known suffixes
    for suffix, compat_types in PATH_TYPE_COMPAT.items():
        if binding_path.endswith(suffix):
            return action_type in compat_types

    # Bare path (e.g., /input/thumbstick, /input/trackpad) = Vector2
    # But also usable for Bool/Float via conversion
    return action_type in {0, 1, 2}


def main():
    tres_path = Path(__file__).parent.parent / "Godot" / "openxr_action_map.tres"
    if not tres_path.exists():
        print(f"ERROR: {tres_path} not found")
        sys.exit(1)

    actions, bindings, profiles = parse_tres(tres_path)
    errors = []
    warnings = []

    print(f"Parsed: {len(actions)} actions, {len(bindings)} bindings, {len(profiles)} profiles\n")

    for pid, profile in profiles.items():
        ppath = profile["path"]
        pname = ppath.split("/")[-1]
        print(f"--- Profile: {pname} ({pid}) ---")
        print(f"    Path: {ppath}")
        print(f"    Bindings: {len(profile['binding_ids'])}")

        valid_paths = VALID_PATHS.get(ppath)
        path_to_actions = defaultdict(list)

        for bid in profile["binding_ids"]:
            b = bindings.get(bid)
            if not b:
                errors.append(f"  [{pname}] Binding {bid} referenced but not defined!")
                continue

            action = actions.get(b["action_id"])
            if not action:
                errors.append(f"  [{pname}] Action {b['action_id']} in binding {bid} not defined!")
                continue

            bpath = b["path"]
            aname = action["name"]
            atype = action["type"]

            # Check 1: valid path for this profile
            if valid_paths is not None:
                if bpath not in valid_paths:
                    errors.append(
                        f"  [{pname}] INVALID PATH: '{bpath}' for action '{aname}' "
                        f"(not in OpenXR spec for {pname})"
                    )

            # Check 2: type compatibility
            if not check_path_type_compat(bpath, atype):
                errors.append(
                    f"  [{pname}] TYPE MISMATCH: action '{aname}' is {ACTION_TYPE_NAMES.get(atype, '?')} "
                    f"but bound to '{bpath}'"
                )

            # Track for duplicate detection
            path_to_actions[bpath].append((aname, atype, bid))

        # Check 3: duplicate actions on same path
        for bpath, action_list in path_to_actions.items():
            if len(action_list) > 1:
                names = [f"'{a[0]}' ({ACTION_TYPE_NAMES.get(a[1], '?')})" for a in action_list]
                msg = (
                    f"  [{pname}] DUPLICATE BINDING: {len(action_list)} actions on '{bpath}': "
                    + ", ".join(names)
                )
                # Pose duplicates on aim/pose are the most dangerous
                if "/aim/pose" in bpath:
                    warnings.append(msg + "  [poses — usually OK, runtime picks one]")
                elif any(a[1] != action_list[0][1] for a in action_list):
                    warnings.append(msg + "  [mixed types — runtime may convert]")
                else:
                    warnings.append(msg + "  [same type — higher priority wins]")

        print()

    # Summary
    print("=" * 60)
    if errors:
        print(f"\n*** {len(errors)} ERROR(S) FOUND ***")
        for e in errors:
            print(e)
    else:
        print("\nNo errors found in binding paths.")

    if warnings:
        print(f"\n--- {len(warnings)} warning(s) ---")
        for w in warnings:
            print(w)

    if not errors:
        print("\n✓ All binding paths are valid for their profiles.")
        print("  If thumbstick still doesn't work, the issue is NOT in the action map file.")
        print("  Consider: Quest Link version, Godot OpenXR runtime, or driver issue.")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
