"""Supply a complete deterministic observation before Duck requests a tool."""

from arc3.scene import render_scene


SCENE_GUIDANCE = """

Complete scene observations:
- Every user turn includes SCENE_V1, a complete lossless encoding of the current
  visible board. Read it directly before deciding whether more inspection is needed.
- You may read the supplied scene in full. Restrictions on printing full boards
  concern redundant Python tool output, not reading this supplied observation.
- Repeated adjacent rows and columns are compressed only when their entire
  contents are identical. The row/column ranges preserve original coordinates;
  they are not inferred game tiles. Convert any target back to original row/col.
- Components describe observed geometry only. Background, HUD, targets, controls,
  and rules are hypotheses for you to test; the renderer assigns none of them.
- Changes are relative to the previous model-turn observation, which may span
  several real actions. They are not evidence for one action when a batch ran.
- The complete current snapshot remains authoritative. Python is available for
  calculations, small crops, hypotheses, search and actions. You do not need to
  spend an inspection call rebuilding the scene already provided.
"""


class SceneObservationMixin:
    """Mixin preceding ToolAgent; no modification of control instances."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scene_previous_grid = None
        self._scene_previous_level = None
        self._scene_observations = 0
        self._scene_chars = 0
        self._system_prompt += SCENE_GUIDANCE

    def _build_user_prompt(self, action_num, *, current_frame=None, **kwargs):
        prompt = super()._build_user_prompt(
            action_num, current_frame=current_frame, **kwargs
        )
        prompt = prompt.replace(
            "Only letter-coded board views and lightweight metadata are exposed; raw numeric color IDs are not available.",
            "The supplied scene includes letter-coded cells, color IDs and exact original coordinates; Python retains its usual board views.",
        )
        if current_frame is None:
            raise ValueError("Scene agent requires an observable current frame")
        grid = tuple(tuple(row) for row in current_frame.grid)
        previous = self._scene_previous_grid
        level_note = ""
        if self._scene_previous_level != current_frame.level:
            previous = None
            level_note = "New level observation; infer or recheck the goal and rules.\n"
        scene = render_scene(grid, previous=previous)
        self._scene_previous_grid = grid
        self._scene_previous_level = current_frame.level
        self._scene_observations += 1
        self._scene_chars += len(scene)
        return prompt + "\n\n" + level_note + scene


def scene_delivery_problems(rows):
    """Validate actual user-message evidence, not an intended environment flag."""
    problems = []
    for row in rows:
        arm = row["trial_id"]
        label = f"{arm}/{row['game_id']}"
        scene = arm in ("C", "T")
        image = arm != "T"
        for field in ("scene_observations", "scene_chars", "scene_delivered_messages"):
            if (int(row.get(field, 0)) > 0) != scene:
                problems.append(f"{label}: unexpected {field}={row.get(field)}")
        images = int(row.get("scene_image_messages", 0))
        texts = int(row.get("scene_text_only_messages", 0))
        if scene:
            observations = int(row.get("scene_observations", 0))
            delivered = int(row.get("scene_delivered_messages", 0))
            expected_modality = images if image else texts
            if not (observations == delivered == expected_modality):
                problems.append(
                    f"{label}: incomplete per-turn delivery "
                    f"observations={observations}, delivered={delivered}, "
                    f"expected_modality={expected_modality}"
                )
        if image and not (images > 0 and texts == 0):
            problems.append(f"{label}: expected image-only turns, saw {images}/{texts}")
        if not image and not (images == 0 and texts > 0):
            problems.append(f"{label}: expected text-only turns, saw {images}/{texts}")
    return problems
