import asyncio

from harness.project import init_project, load_config
from harness.server import app as server_app


def test_fresh_project_is_detected_and_initialization_populates_author_intent(tmp_path, monkeypatch):
    paths = init_project(tmp_path)
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)

    assert asyncio.run(server_app.project_status()) == {
        "is_empty": True,
        "passage_count": 0,
        "has_premise": False,
    }
    result = asyncio.run(server_app.init_story(server_app.StoryInitRequest(
        title="The Tide Archive",
        premise="A cartographer searches for a vanished island.",
        tone="Melancholic",
        themes="Memory and duty",
        world_overview="An archipelago governed by tides.",
        opening_situation="The harbor closes at dusk.",
        story_points="- Find the missing chart\n- Cross the storm",
    )))

    assert result["status"] == "initialized"
    assert asyncio.run(server_app.project_status())["has_premise"] is True
    assert load_config(paths).story_title == "The Tide Archive"
    assert "vanished island" in paths.premise_md.read_text(encoding="utf-8")


def test_initialization_bootstraps_a_bare_project_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(server_app, "_PROJECT_ROOT", tmp_path)

    result = asyncio.run(server_app.init_story(server_app.StoryInitRequest(
        title="Bare Directory Story",
        premise="A story created entirely from the browser wizard.",
    )))

    assert result["status"] == "initialized"
    assert (tmp_path / "story.json").is_file()
    assert (tmp_path / ".harness" / "config.yaml").is_file()
    graph = asyncio.run(server_app.get_graph())
    assert graph["passages"] == {}
    assert graph["arcs"] == {}
