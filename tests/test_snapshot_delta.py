"""Tests for snapshot delta computation, application, and round-trip."""
import unittest

from harness.models import (
    CharacterDelta,
    CharacterOffscreen,
    CharacterPresent,
    ModelOutput,
    ParsedChoice,
    Snapshot,
)
from harness.snapshot import derive_snapshot
from harness.snapshot_delta import (
    apply_delta,
    apply_deltas,
    diff_snapshots,
    is_empty_delta,
    reconstruct_snapshot_from_deltas,
)


def _snap_eq(a: Snapshot, b: Snapshot) -> bool:
    """Deep equality check on two snapshots."""
    return a.model_dump() == b.model_dump()


class DiffTests(unittest.TestCase):
    def test_identical_snapshots_produce_empty_delta(self):
        snap = Snapshot(
            characters_present=[CharacterPresent(id="alice", status="here")],
            world_state=["sky is blue"],
            open_threads=["find the key"],
        )
        delta = diff_snapshots(snap, snap)
        self.assertTrue(is_empty_delta(delta))

    def test_character_present_added(self):
        old = Snapshot()
        new = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="wary", knows=["code"]),
        ])
        delta = diff_snapshots(old, new)
        self.assertEqual(len(delta.characters_present.added), 1)
        self.assertEqual(delta.characters_present.added[0]["id"], "alice")
        self.assertEqual(delta.characters_present.added[0]["status"], "wary")
        self.assertEqual(delta.characters_present.removed, [])
        self.assertEqual(delta.characters_present.modified, {})

    def test_character_present_removed(self):
        old = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="here"),
            CharacterPresent(id="kael", status="here"),
        ])
        new = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="here"),
        ])
        delta = diff_snapshots(old, new)
        self.assertEqual(delta.characters_present.removed, ["kael"])
        self.assertEqual(delta.characters_present.added, [])

    def test_character_present_modified_status(self):
        old = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="calm", knows=["a"]),
        ])
        new = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="afraid", knows=["a"]),
        ])
        delta = diff_snapshots(old, new)
        self.assertEqual(delta.characters_present.modified, {"alice": {"status": "afraid"}})
        self.assertEqual(delta.characters_present.added, [])
        self.assertEqual(delta.characters_present.removed, [])

    def test_character_present_modified_knows(self):
        old = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="calm", knows=["a"]),
        ])
        new = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="calm", knows=["a", "b"]),
        ])
        delta = diff_snapshots(old, new)
        self.assertEqual(delta.characters_present.modified, {"alice": {"knows": ["a", "b"]}})

    def test_character_present_modified_relationship(self):
        old = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="calm", knows=[], relationship_to_player="ally"),
        ])
        new = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="calm", knows=[], relationship_to_player="rival"),
        ])
        delta = diff_snapshots(old, new)
        self.assertEqual(
            delta.characters_present.modified,
            {"alice": {"relationship_to_player": "rival"}},
        )

    def test_character_offscreen_added(self):
        old = Snapshot()
        new = Snapshot(characters_offscreen=[
            CharacterOffscreen(id="kael", last_known="the north"),
        ])
        delta = diff_snapshots(old, new)
        self.assertEqual(len(delta.characters_offscreen.added), 1)
        self.assertEqual(delta.characters_offscreen.added[0]["id"], "kael")
        self.assertEqual(delta.characters_offscreen.added[0]["last_known"], "the north")

    def test_character_offscreen_removed(self):
        old = Snapshot(characters_offscreen=[
            CharacterOffscreen(id="kael", last_known="north"),
        ])
        new = Snapshot()
        delta = diff_snapshots(old, new)
        self.assertEqual(delta.characters_offscreen.removed, ["kael"])

    def test_character_offscreen_modified(self):
        old = Snapshot(characters_offscreen=[
            CharacterOffscreen(id="kael", last_known="north"),
        ])
        new = Snapshot(characters_offscreen=[
            CharacterOffscreen(id="kael", last_known="south"),
        ])
        delta = diff_snapshots(old, new)
        self.assertEqual(delta.characters_offscreen.modified, {"kael": {"last_known": "south"}})

    def test_world_state_add_remove(self):
        old = Snapshot(world_state=["sky is blue", "river flows"])
        new = Snapshot(world_state=["river flows", "moon rises"])
        delta = diff_snapshots(old, new)
        self.assertEqual(delta.world_state.added, ["moon rises"])
        self.assertEqual(delta.world_state.removed, ["sky is blue"])

    def test_open_threads_add_remove(self):
        old = Snapshot(open_threads=["find key", "meet sage"])
        new = Snapshot(open_threads=["meet sage", "slay dragon"])
        delta = diff_snapshots(old, new)
        self.assertEqual(delta.open_threads.added, ["slay dragon"])
        self.assertEqual(delta.open_threads.removed, ["find key"])


class ApplyTests(unittest.TestCase):
    def test_apply_added_character(self):
        base = Snapshot()
        delta = diff_snapshots(base, Snapshot(characters_present=[
            CharacterPresent(id="alice", status="wary"),
        ]))
        result = apply_delta(base, delta)
        self.assertEqual([c.id for c in result.characters_present], ["alice"])
        self.assertEqual(result.characters_present[0].status, "wary")

    def test_apply_removed_character_moves_to_offscreen(self):
        base = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="here"),
            CharacterPresent(id="kael", status="here"),
        ])
        delta = diff_snapshots(base, Snapshot(characters_present=[
            CharacterPresent(id="alice", status="here"),
        ]))
        result = apply_delta(base, delta)
        self.assertEqual([c.id for c in result.characters_present], ["alice"])
        self.assertEqual([c.id for c in result.characters_offscreen], ["kael"])

    def test_apply_modified_status(self):
        base = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="calm", knows=["a"]),
        ])
        delta = diff_snapshots(base, Snapshot(characters_present=[
            CharacterPresent(id="alice", status="afraid", knows=["a"]),
        ]))
        result = apply_delta(base, delta)
        self.assertEqual(result.characters_present[0].status, "afraid")
        self.assertEqual(result.characters_present[0].knows, ["a"])

    def test_apply_world_state_changes(self):
        base = Snapshot(world_state=["sky is blue", "river flows"])
        delta = diff_snapshots(base, Snapshot(world_state=["river flows", "moon rises"]))
        result = apply_delta(base, delta)
        self.assertEqual(result.world_state, ["river flows", "moon rises"])

    def test_apply_open_threads_changes(self):
        base = Snapshot(open_threads=["find key"])
        delta = diff_snapshots(base, Snapshot(open_threads=["find key", "slay dragon"]))
        result = apply_delta(base, delta)
        self.assertIn("slay dragon", result.open_threads)
        self.assertIn("find key", result.open_threads)

    def test_apply_offscreen_added(self):
        base = Snapshot()
        delta = diff_snapshots(base, Snapshot(characters_offscreen=[
            CharacterOffscreen(id="kael", last_known="north"),
        ]))
        result = apply_delta(base, delta)
        self.assertEqual(result.characters_offscreen[0].id, "kael")
        self.assertEqual(result.characters_offscreen[0].last_known, "north")

    def test_apply_offscreen_removed(self):
        base = Snapshot(characters_offscreen=[
            CharacterOffscreen(id="kael", last_known="north"),
        ])
        delta = diff_snapshots(base, Snapshot())
        result = apply_delta(base, delta)
        self.assertEqual(result.characters_offscreen, [])

    def test_apply_does_not_mutate_base(self):
        base = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="calm"),
        ])
        delta = diff_snapshots(base, Snapshot(characters_present=[
            CharacterPresent(id="alice", status="afraid"),
        ]))
        apply_delta(base, delta)
        # base unchanged
        self.assertEqual(base.characters_present[0].status, "calm")


class RoundTripTests(unittest.TestCase):
    """snapshot -> delta -> reconstructed snapshot == original"""

    def test_round_trip_no_changes(self):
        snap = Snapshot(
            characters_present=[CharacterPresent(id="a", status="here")],
            world_state=["fact"],
            open_threads=["thread"],
        )
        delta = diff_snapshots(snap, snap)
        reconstructed = apply_delta(snap, delta)
        self.assertTrue(_snap_eq(reconstructed, snap))

    def test_round_trip_character_enter(self):
        old = Snapshot()
        new = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="wary", knows=["code"]),
        ])
        delta = diff_snapshots(old, new)
        reconstructed = apply_delta(old, delta)
        self.assertTrue(_snap_eq(reconstructed, new))

    def test_round_trip_character_exit(self):
        old = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="here"),
            CharacterPresent(id="kael", status="here"),
        ])
        new = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="here"),
        ])
        delta = diff_snapshots(old, new)
        reconstructed = apply_delta(old, delta)
        # The reconstructed snapshot will have kael in offscreen (moved there by
        # apply_delta). The diff only records removal from present, not
        # addition to offscreen, so we verify present matches and offscreen
        # has the moved character.
        self.assertEqual(
            [c.id for c in reconstructed.characters_present],
            [c.id for c in new.characters_present],
        )
        self.assertIn("kael", [c.id for c in reconstructed.characters_offscreen])

    def test_round_trip_character_status_change(self):
        old = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="calm", knows=["a"], relationship_to_player="ally"),
        ])
        new = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="afraid", knows=["a", "b"], relationship_to_player="rival"),
        ])
        delta = diff_snapshots(old, new)
        reconstructed = apply_delta(old, delta)
        self.assertTrue(_snap_eq(reconstructed, new))

    def test_round_trip_offscreen_modified(self):
        old = Snapshot(characters_offscreen=[
            CharacterOffscreen(id="kael", last_known="north"),
        ])
        new = Snapshot(characters_offscreen=[
            CharacterOffscreen(id="kael", last_known="south"),
        ])
        delta = diff_snapshots(old, new)
        reconstructed = apply_delta(old, delta)
        self.assertTrue(_snap_eq(reconstructed, new))

    def test_round_trip_complex(self):
        old = Snapshot(
            characters_present=[
                CharacterPresent(id="alice", status="calm", knows=["a"], relationship_to_player="ally"),
                CharacterPresent(id="bob", status="happy", knows=[]),
            ],
            characters_offscreen=[
                CharacterOffscreen(id="kael", last_known="north"),
            ],
            world_state=["sky is blue", "river flows"],
            open_threads=["find key", "meet sage"],
        )
        new = Snapshot(
            characters_present=[
                CharacterPresent(id="alice", status="afraid", knows=["a", "b"], relationship_to_player="rival"),
            ],
            characters_offscreen=[
                CharacterOffscreen(id="kael", last_known="south"),
                CharacterOffscreen(id="bob", last_known="went home"),
            ],
            world_state=["river flows", "moon rises"],
            open_threads=["meet sage", "slay dragon"],
        )
        delta = diff_snapshots(old, new)
        reconstructed = apply_delta(old, delta)
        # Verify key properties (bob was removed from present, moved to offscreen)
        self.assertEqual(
            [c.id for c in reconstructed.characters_present],
            [c.id for c in new.characters_present],
        )
        self.assertEqual(reconstructed.characters_present[0].status, "afraid")
        self.assertEqual(reconstructed.characters_present[0].knows, ["a", "b"])
        self.assertEqual(reconstructed.characters_present[0].relationship_to_player, "rival")
        # kael's last_known updated
        kael = [c for c in reconstructed.characters_offscreen if c.id == "kael"][0]
        self.assertEqual(kael.last_known, "south")
        # bob moved to offscreen
        bob = [c for c in reconstructed.characters_offscreen if c.id == "bob"]
        self.assertTrue(bob)
        self.assertEqual(reconstructed.world_state, new.world_state)
        self.assertEqual(reconstructed.open_threads, new.open_threads)

    def test_round_trip_empty_to_empty(self):
        snap = Snapshot()
        delta = diff_snapshots(snap, snap)
        reconstructed = apply_delta(snap, delta)
        self.assertTrue(_snap_eq(reconstructed, snap))

    def test_apply_deltas_sequence(self):
        """Apply a chain of deltas as in a real story."""
        base = Snapshot()
        snap1 = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="wary"),
        ])
        snap2 = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="angry"),
            CharacterPresent(id="bob", status="calm"),
        ], world_state=["storm brews"])
        snap3 = Snapshot(characters_present=[
            CharacterPresent(id="alice", status="angry"),
        ], world_state=["storm brews", "river floods"])

        d1 = diff_snapshots(base, snap1)
        d2 = diff_snapshots(snap1, snap2)
        d3 = diff_snapshots(snap2, snap3)

        reconstructed = apply_deltas(base, [d1, d2, d3])
        self.assertEqual(
            [c.id for c in reconstructed.characters_present],
            [c.id for c in snap3.characters_present],
        )
        self.assertEqual(reconstructed.world_state, snap3.world_state)
        # bob exited -> offscreen
        self.assertIn("bob", [c.id for c in reconstructed.characters_offscreen])

    def test_reconstruct_from_deltas_with_none_base(self):
        """Root passage: base is None, use empty Snapshot."""
        snap = Snapshot(world_state=["dawn breaks"])
        delta = diff_snapshots(Snapshot(), snap)
        result = reconstruct_snapshot_from_deltas(None, [delta])
        self.assertEqual(result.world_state, ["dawn breaks"])


class IntegrationTests(unittest.TestCase):
    """Test that deltas are computed and stored during create_passage."""

    def test_delta_stored_on_passage_entry(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from harness.passage import create_passage
        from harness.project import init_project

        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            # Root passage: alice enters
            out1 = ModelOutput(
                prose="Alice arrives.",
                choices=[ParsedChoice(text="Talk", hint="greet")],
                summary="Meeting.",
                characters_present=[CharacterDelta(id="alice", status="wary")],
                world_state_add=["dawn breaks"],
            )
            pid1, graph = create_passage(p, "intro", "01_meet", out1, None)

            # Root delta: from empty snapshot to one with alice + dawn
            delta1 = graph.passages[pid1].snapshot_delta
            self.assertIsNotNone(delta1)
            self.assertEqual(len(delta1.characters_present.added), 1)
            self.assertEqual(delta1.characters_present.added[0]["id"], "alice")
            self.assertIn("dawn breaks", delta1.world_state.added)

            # Child passage: alice gets angry, bob enters
            out2 = ModelOutput(
                prose="Alice fumes. Bob walks in.",
                choices=[ParsedChoice(text="Leave", hint="exit")],
                summary="Escalation.",
                character_status=[CharacterDelta(id="alice", status="angry")],
                characters_present=[CharacterDelta(id="bob", status="calm")],
            )
            pid2, graph = create_passage(p, "intro", "02_escalation", out2, pid1, choice_index=0)

            delta2 = graph.passages[pid2].snapshot_delta
            self.assertIsNotNone(delta2)
            # alice status modified
            self.assertIn("alice", delta2.characters_present.modified)
            self.assertEqual(delta2.characters_present.modified["alice"]["status"], "angry")
            # bob added
            self.assertEqual(len(delta2.characters_present.added), 1)
            self.assertEqual(delta2.characters_present.added[0]["id"], "bob")

    def test_delta_round_trip_through_create_passage(self):
        """Reconstruct snapshot from parent + stored delta == child snapshot."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from harness.passage import create_passage
        from harness.project import init_project

        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out1 = ModelOutput(
                prose="Alice arrives.",
                choices=[ParsedChoice(text="Talk", hint="greet")],
                summary="Meeting.",
                characters_present=[CharacterDelta(id="alice", status="wary")],
                world_state_add=["dawn breaks"],
                threads_open=["find the key"],
            )
            pid1, graph = create_passage(p, "intro", "01_meet", out1, None)

            out2 = ModelOutput(
                prose="Alice fumes. Bob walks in.",
                choices=[ParsedChoice(text="Leave", hint="exit")],
                summary="Escalation.",
                character_status=[CharacterDelta(id="alice", status="angry")],
                characters_present=[CharacterDelta(id="bob", status="calm")],
                characters_exit=[CharacterDelta(id="alice", last_known="stormed out")],
                world_state_add=["storm brews"],
                threads_close=["find the key"],
                threads_open=["slay dragon"],
            )
            pid2, graph = create_passage(p, "intro", "02_escalation", out2, pid1, choice_index=0)

            parent_snap = graph.passages[pid1].snapshot
            child_snap = graph.passages[pid2].snapshot
            stored_delta = graph.passages[pid2].snapshot_delta

            # Reconstruct child from parent + delta
            reconstructed = apply_delta(parent_snap, stored_delta)

            # The full snapshots match for fields the delta tracks precisely.
            # characters_present should match exactly.
            self.assertEqual(
                [c.id for c in reconstructed.characters_present],
                [c.id for c in child_snap.characters_present],
            )
            # world_state matches
            self.assertEqual(reconstructed.world_state, child_snap.world_state)
            # open_threads matches
            self.assertEqual(reconstructed.open_threads, child_snap.open_threads)

    def test_root_passage_delta_from_empty(self):
        """Root passage delta is computed from an empty snapshot."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from harness.passage import create_passage
        from harness.project import init_project

        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            out = ModelOutput(
                prose="Opening scene.",
                choices=[ParsedChoice(text="Go", hint="on")],
                summary="Open.",
                characters_present=[CharacterDelta(id="hero", status="ready")],
            )
            pid, graph = create_passage(p, "intro", "01_open", out, None)
            delta = graph.passages[pid].snapshot_delta
            self.assertIsNotNone(delta)
            # Everything is "added" since base is empty
            self.assertEqual(len(delta.characters_present.added), 1)
            self.assertEqual(delta.characters_present.added[0]["id"], "hero")

    def test_backward_compat_old_story_json_without_delta(self):
        """Old story.json without snapshot_delta field loads fine."""
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import json
        from harness.models import PassageEntry, StoryGraph
        from harness.project import init_project, load_story

        with TemporaryDirectory() as tmp:
            p = init_project(Path(tmp), title="Test")
            # Manually create a story.json without snapshot_delta (old format)
            old_graph = StoryGraph()
            old_graph.start_passage = "test__01"
            old_graph.passages["test__01"] = PassageEntry(
                file="arcs/test/01.tw",
                arc="test",
                summary="Old passage.",
                # snapshot defaults to empty, snapshot_delta defaults to None
            )
            # Write as raw dict, then strip snapshot_delta to simulate old format
            raw = old_graph.model_dump()
            for passage in raw["passages"].values():
                passage.pop("snapshot_delta", None)
            p.story_json.write_text(json.dumps(raw, indent=2), encoding="utf-8")

            # Should load without error
            graph = load_story(p)
            self.assertIn("test__01", graph.passages)
            # snapshot_delta defaults to None when missing from JSON
            self.assertIsNone(graph.passages["test__01"].snapshot_delta)
            # Snapshot still works
            self.assertEqual(graph.passages["test__01"].snapshot.characters_present, [])


if __name__ == "__main__":
    unittest.main()
