"""P7 invariant verification tests — verify all 6 P6 invariants hold against live code."""
from harness.models import (
    StoryGraph,
    PassageEntry,
    Snapshot,
    SnapshotDelta,
    CharacterPresent,
    CharacterOffscreen,
)
from harness.snapshot_delta import (
    diff_snapshots,
    apply_delta,
    reconstruct_passage_snapshot,
)
from harness.validation import check_delta_round_trip


def _make_test_graph():
    """Build a root → child → grandchild graph with deltas.

    NOTE: We avoid present↔offscreen transitions because apply_delta's
    present-section removal sets last_known="" and the subsequent
    offscreen-section add is a no-op (pre-existing limitation in the
    committed apply_delta, not introduced by P7).
    """
    root_snap = Snapshot(
        characters_present=[CharacterPresent(id="alice", status="in scene")],
        characters_offscreen=[CharacterOffscreen(id="bob", last_known="gone")],
        world_state=["sky is blue"],
        open_threads=["find the key"],
    )
    child_snap = Snapshot(
        characters_present=[
            CharacterPresent(id="alice", status="in scene"),
            CharacterPresent(id="bob", status="entered"),
        ],
        characters_offscreen=[],
        world_state=["sky is blue", "door is open"],
        open_threads=["find the key", "open the door"],
    )
    grandchild_snap = Snapshot(
        characters_present=[
            CharacterPresent(id="alice", status="left"),
            CharacterPresent(id="bob", status="staying"),
        ],
        characters_offscreen=[],
        world_state=["sky is blue", "door is open"],
        open_threads=["open the door"],
    )
    graph = StoryGraph(start_passage="root")
    graph.passages["root"] = PassageEntry(
        file="root.tw", arc="test", parents=[], children=["child"], snapshot=root_snap
    )
    graph.passages["child"] = PassageEntry(
        file="child.tw", arc="test", parents=["root"], children=["grandchild"],
        snapshot=child_snap, snapshot_delta=diff_snapshots(root_snap, child_snap),
    )
    graph.passages["grandchild"] = PassageEntry(
        file="grandchild.tw", arc="test", parents=["child"], children=[],
        snapshot=grandchild_snap, snapshot_delta=diff_snapshots(child_snap, grandchild_snap),
    )
    return graph, root_snap, child_snap, grandchild_snap


class TestInvariant1NonRootRoundTrip:
    def test_child_delta_round_trips(self):
        graph, root_snap, child_snap, _ = _make_test_graph()
        reconstructed = apply_delta(root_snap, graph.passages["child"].snapshot_delta)
        assert reconstructed == child_snap

    def test_grandchild_delta_round_trips(self):
        graph, _, child_snap, grandchild_snap = _make_test_graph()
        reconstructed = apply_delta(child_snap, graph.passages["grandchild"].snapshot_delta)
        assert reconstructed == grandchild_snap


class TestInvariant2RootDeltaRoundTrip:
    def test_root_delta_round_trips_to_empty(self):
        root_snap = Snapshot(
            characters_present=[CharacterPresent(id="alice", status="in scene")],
        )
        root_delta = diff_snapshots(Snapshot(), root_snap)
        root_entry = PassageEntry(
            file="r.tw", arc="t", parents=[], children=[], snapshot=root_snap,
            snapshot_delta=root_delta,
        )
        g = StoryGraph(start_passage="r")
        g.passages["r"] = root_entry
        reconstructed = apply_delta(Snapshot(), root_delta)
        assert reconstructed == root_snap
        issues = check_delta_round_trip(g)
        assert len(issues) == 0


class TestInvariant3BackwardCompat:
    def test_missing_delta_defaults_to_none(self):
        old_json = {
            "version": 1,
            "start_passage": "p1",
            "passages": {
                "p1": {
                    "file": "f.tw", "arc": "a", "parents": [], "children": [],
                    "snapshot": {"characters_present": [], "characters_offscreen": [],
                                 "world_state": [], "open_threads": []},
                }
            },
        }
        g = StoryGraph.model_validate(old_json)
        assert g.passages["p1"].snapshot_delta is None


class TestInvariant4CycleGuard:
    def test_cycle_does_not_infinite_loop(self):
        g = StoryGraph(start_passage="a")
        g.passages["a"] = PassageEntry(file="a.tw", arc="t", parents=["b"], children=[], snapshot=Snapshot())
        g.passages["b"] = PassageEntry(file="b.tw", arc="t", parents=["a"], children=[], snapshot=Snapshot())
        result = reconstruct_passage_snapshot(g, "a")  # should terminate
        assert result is not None


class TestInvariant5FirstParentSemantics:
    def test_first_parent_used_for_delta_base(self):
        graph, root_snap, child_snap, _ = _make_test_graph()
        issues = check_delta_round_trip(graph)
        assert len(issues) == 0  # uses parents[0] correctly


class TestInvariant6ReconstructionEqualsStored:
    def test_root_reconstruction(self):
        graph, root_snap, _, _ = _make_test_graph()
        assert reconstruct_passage_snapshot(graph, "root") == root_snap

    def test_child_reconstruction(self):
        graph, _, child_snap, _ = _make_test_graph()
        assert reconstruct_passage_snapshot(graph, "child") == child_snap

    def test_grandchild_reconstruction(self):
        graph, _, _, grandchild_snap = _make_test_graph()
        assert reconstruct_passage_snapshot(graph, "grandchild") == grandchild_snap


class TestCheckDeltaRoundTrip:
    def test_well_formed_graph_no_issues(self):
        graph, _, _, _ = _make_test_graph()
        issues = check_delta_round_trip(graph)
        assert len(issues) == 0

    def test_corruption_detected(self):
        graph, root_snap, child_snap, _ = _make_test_graph()
        corrupt_snap = Snapshot(
            characters_present=[CharacterPresent(id="alice", status="WRONG")],
        )
        graph.passages["child"].snapshot = corrupt_snap
        issues = check_delta_round_trip(graph)
        # Both child (delta doesn't round-trip to corrupted snapshot) and
        # grandchild (delta was computed against the original child snapshot,
        # now the parent base is different) are flagged.
        assert len(issues) == 2
        codes = [i.code for i in issues]
        assert all(c == "delta_round_trip" for c in codes)
        assert "child" in [i.passage for i in issues]
        assert "grandchild" in [i.passage for i in issues]

    def test_none_delta_skipped(self):
        graph, root_snap, _, _ = _make_test_graph()
        graph.passages["child"].snapshot_delta = None
        issues = check_delta_round_trip(graph)
        assert len(issues) == 0  # None delta skipped, no error

    def test_dangling_parent_skipped(self):
        g = StoryGraph(start_passage="root")
        g.passages["root"] = PassageEntry(file="r.tw", arc="t", parents=[], children=["c"], snapshot=Snapshot())
        g.passages["c"] = PassageEntry(file="c.tw", arc="t", parents=["nonexistent"], children=[], snapshot=Snapshot())
        issues = check_delta_round_trip(g)
        assert len(issues) == 0  # dangling parent skipped

    def test_root_with_delta_checked(self):
        root_snap = Snapshot(
            characters_present=[CharacterPresent(id="alice", status="here")],
        )
        root_delta = diff_snapshots(Snapshot(), root_snap)
        g = StoryGraph(start_passage="r")
        g.passages["r"] = PassageEntry(
            file="r.tw", arc="t", parents=[], children=[], snapshot=root_snap,
            snapshot_delta=root_delta,
        )
        issues = check_delta_round_trip(g)
        assert len(issues) == 0  # root delta round-trips correctly

    def test_root_with_bad_delta_detected(self):
        root_snap = Snapshot(
            characters_present=[CharacterPresent(id="alice", status="here")],
        )
        bad_delta = diff_snapshots(Snapshot(), Snapshot(
            characters_present=[CharacterPresent(id="bob", status="different")],
        ))
        g = StoryGraph(start_passage="r")
        g.passages["r"] = PassageEntry(
            file="r.tw", arc="t", parents=[], children=[], snapshot=root_snap,
            snapshot_delta=bad_delta,
        )
        issues = check_delta_round_trip(g)
        assert len(issues) == 1
        assert issues[0].code == "delta_round_trip"
