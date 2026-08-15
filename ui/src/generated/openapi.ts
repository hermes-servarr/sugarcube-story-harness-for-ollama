export interface paths {
    "/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Spa */
        get: operations["spa__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/arcs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Arcs
         * @description All arc names with their passages, derived from story.json + arcs/ dirs.
         */
        get: operations["get_arcs_api_arcs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/benchmarks/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Benchmark Runs */
        get: operations["benchmark_runs_api_benchmarks_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/benchmarks/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Benchmark Run */
        get: operations["benchmark_run_api_benchmarks_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/benchmarks/runs/{run_id}/comparison": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Benchmark Run Comparison */
        get: operations["benchmark_run_comparison_api_benchmarks_runs__run_id__comparison_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/capability-cards": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Capability Cards */
        get: operations["get_capability_cards_api_capability_cards_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/characters": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Characters */
        get: operations["get_characters_api_characters_get"];
        put?: never;
        /** Create Character */
        post: operations["create_character_api_characters_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/characters/{char_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Character */
        get: operations["get_character_api_characters__char_id__get"];
        put?: never;
        /** Save Character */
        post: operations["save_character_api_characters__char_id__post"];
        /** Delete Character Endpoint */
        delete: operations["delete_character_endpoint_api_characters__char_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/characters/{char_id}/generate-keywords": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Generate Character Keywords */
        post: operations["generate_character_keywords_api_characters__char_id__generate_keywords_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/characters/{char_id}/keywords": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Set Character Keywords Endpoint */
        post: operations["set_character_keywords_endpoint_api_characters__char_id__keywords_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/commit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Commit
         * @description Parse + commit a passage. Returns new passage_id and pending facts.
         */
        post: operations["commit_api_commit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/compile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Compile Endpoint */
        post: operations["compile_endpoint_api_compile_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/config": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Config */
        get: operations["get_config_api_config_get"];
        put?: never;
        /** Update Config */
        post: operations["update_config_api_config_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/debug/calls": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Debug Calls
         * @description Recent Ollama generation calls — model, prompt variant, options, status.
         *
         *     Lets you confirm exactly which model + prompt served each call. In-memory,
         *     newest first, resets on server restart.
         */
        get: operations["debug_calls_api_debug_calls_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/debug/calls/clear": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Debug Calls Clear */
        post: operations["debug_calls_clear_api_debug_calls_clear_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/drafts/{draft_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Latest Typed Draft */
        get: operations["get_latest_typed_draft_api_drafts__draft_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/drafts/{draft_id}/{revision}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Typed Draft */
        get: operations["get_typed_draft_api_drafts__draft_id___revision__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/drafts/{draft_id}/{revision}/commit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Commit Typed
         * @description Commit the exact persisted compile artifact; no raw output is accepted.
         */
        post: operations["commit_typed_api_drafts__draft_id___revision__commit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/drafts/{draft_id}/{revision}/compile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Compile Typed Draft
         * @description Compile one exact immutable draft without mutating its persisted revision.
         */
        post: operations["compile_typed_draft_api_drafts__draft_id___revision__compile_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/drafts/{draft_id}/{revision}/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Edit Typed Draft
         * @description Validate a human edit as a new immutable revision of the same plan.
         */
        post: operations["edit_typed_draft_api_drafts__draft_id___revision__edit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/drafts/{draft_id}/{revision}/facts/{fact_key}/decision": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Decide Typed Fact
         * @description Accept or reject an exact proposal from one committed draft revision.
         */
        post: operations["decide_typed_fact_api_drafts__draft_id___revision__facts__fact_key__decision_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/drafts/{draft_id}/{revision}/playtest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Playtest Typed Draft
         * @description Queue isolated browser evaluation for one exact immutable draft revision.
         */
        post: operations["playtest_typed_draft_api_drafts__draft_id___revision__playtest_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/drafts/{draft_id}/{revision}/reject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reject Typed Draft */
        post: operations["reject_typed_draft_api_drafts__draft_id___revision__reject_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/drafts/{draft_id}/{revision}/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Validate Typed Draft
         * @description Promote a compiled human edit to the explicit validated state.
         */
        post: operations["validate_typed_draft_api_drafts__draft_id___revision__validate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/encounters": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Encounters */
        get: operations["get_encounters_api_encounters_get"];
        /** Update Encounters */
        put: operations["update_encounters_api_encounters_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/experience-profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Experience Profile */
        get: operations["get_experience_profile_api_experience_profile_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/experience-profile/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Experience Profile */
        post: operations["preview_experience_profile_api_experience_profile_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/experience-profile/revisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Experience Profile Revision */
        post: operations["create_experience_profile_revision_api_experience_profile_revisions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/extract-entities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Extract Entities Endpoint
         * @description Second-pass NER + theme extraction on a passage's prose.
         */
        post: operations["extract_entities_endpoint_api_extract_entities_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/facts/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve Fact */
        post: operations["approve_fact_api_facts_approve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/generate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Generate
         * @description Call Ollama, parse output, return for human review. Does NOT commit.
         */
        post: operations["generate_api_generate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/generate-story-points": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Generate Story Points
         * @description Ask Ollama to produce structured act beats from a premise.
         */
        post: operations["generate_story_points_api_generate_story_points_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/generations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Generations
         * @description Recent persisted generations (newest first), prompt/prose truncated.
         *
         *     Unlike /api/debug/calls this survives server restarts — raw outputs live in
         *     .harness/cache/generations/.
         */
        get: operations["get_generations_api_generations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/generations/{gen_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Generation
         * @description Full persisted record for one generation, including raw output + prompt.
         */
        get: operations["get_generation_api_generations__gen_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/graph": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Graph */
        get: operations["get_graph_api_graph_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/init-story": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Init Story
         * @description Populate premise.md, story_points.md, and create character/lore stubs
         *     from the init wizard form. Safe to call on an existing project — only
         *     overwrites files explicitly provided.
         */
        post: operations["init_story_api_init_story_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/init/generate-characters": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Init Generate Characters */
        post: operations["init_generate_characters_api_init_generate_characters_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/init/generate-locations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Init Generate Locations */
        post: operations["init_generate_locations_api_init_generate_locations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/init/generate-opening": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Init Generate Opening */
        post: operations["init_generate_opening_api_init_generate_opening_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/init/generate-premise": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Init Generate Premise */
        post: operations["init_generate_premise_api_init_generate_premise_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/init/generate-tone-themes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Init Generate Tone Themes */
        post: operations["init_generate_tone_themes_api_init_generate_tone_themes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/init/generate-world": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Init Generate World */
        post: operations["init_generate_world_api_init_generate_world_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/inspiration/summarize": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Inspiration Summarize
         * @description Short digest of a reference item: game type, themes, characters.
         */
        post: operations["inspiration_summarize_api_inspiration_summarize_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Lore */
        get: operations["get_lore_api_lore_get"];
        put?: never;
        /** Create Lore */
        post: operations["create_lore_api_lore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lore/{category}/{lore_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Lore Entry */
        get: operations["get_lore_entry_api_lore__category___lore_id__get"];
        put?: never;
        /** Save Lore Entry */
        post: operations["save_lore_entry_api_lore__category___lore_id__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lore/{category}/{lore_id}/generate-keywords": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Generate Lore Keywords */
        post: operations["generate_lore_keywords_api_lore__category___lore_id__generate_keywords_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/lore/{category}/{lore_id}/keywords": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Set Lore Keywords Endpoint */
        post: operations["set_lore_keywords_endpoint_api_lore__category___lore_id__keywords_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/manifest/rebuild": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Manifest Rebuild
         * @description Reconstruct story.json from the .tw files on disk. Repairs manifest
         *     drift and duplicate file ownership; preserves authorial snapshots/summaries
         *     for passages that still exist.
         */
        post: operations["manifest_rebuild_api_manifest_rebuild_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/manifest/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Manifest Sync */
        get: operations["manifest_sync_api_manifest_sync_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/files": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Media Files
         * @description List usable files in the project media/ folder for one-click resolving.
         */
        get: operations["media_files_api_media_files_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import Media
         * @description Copy an external file into the project media/ library.
         */
        post: operations["import_media_api_media_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/slots": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Slots */
        get: operations["get_slots_api_media_slots_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/slots/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Search Media Slots
         * @description Filter slots by free-text query and/or status (pending|resolved).
         */
        get: operations["search_media_slots_api_media_slots_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/slots/{slot_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Delete Media Slot */
        delete: operations["delete_media_slot_api_media_slots__slot_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/slots/{slot_id}/meta": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Update Slot Meta
         * @description Set description / alt / caption / type / embed options on a slot.
         */
        post: operations["update_slot_meta_api_media_slots__slot_id__meta_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/slots/{slot_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Preview Media Slot
         * @description Serve only the file already approved on a resolved media slot.
         */
        get: operations["preview_media_slot_api_media_slots__slot_id__preview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/slots/{slot_id}/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resolve */
        post: operations["resolve_api_media_slots__slot_id__resolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/media/slots/{slot_id}/unresolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Unresolve */
        post: operations["unresolve_api_media_slots__slot_id__unresolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/notes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Notes */
        get: operations["get_notes_api_notes_get"];
        put?: never;
        /** Create Note */
        post: operations["create_note_api_notes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/notes/{note_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Note */
        get: operations["get_note_api_notes__note_id__get"];
        put?: never;
        /** Save Note Endpoint */
        post: operations["save_note_endpoint_api_notes__note_id__post"];
        /** Delete Note Endpoint */
        delete: operations["delete_note_endpoint_api_notes__note_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ollama/delete-model": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Delete Model
         * @description Delete one model from Ollama and drop its cached test score.
         */
        post: operations["delete_model_api_ollama_delete_model_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ollama/delete-unresponsive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Delete Unresponsive
         * @description Delete every model whose latest cached smoke test failed (ok == false).
         *
         *     Models that were never tested are left alone — only proven-bad ones go.
         */
        post: operations["delete_unresponsive_api_ollama_delete_unresponsive_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ollama/scores": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Scores
         * @description Return cached test scores without re-running any tests.
         */
        get: operations["get_scores_api_ollama_scores_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ollama/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Ollama Status
         * @description Ping Ollama, return available models + cached test scores.
         */
        get: operations["ollama_status_api_ollama_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/ollama/test-model": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Test Model
         * @description Send a minimal prompt to a specific model. Saves result to
         *     .harness/cache/model_tests.json so the score persists across sessions.
         *
         *     Reads the response body's ``error`` field directly (instead of relying on
         *     raise_for_status) so Ollama's "requires more system memory" message — which
         *     arrives as a 500 with a JSON body — is captured and flagged as OOM.
         */
        post: operations["test_model_api_ollama_test_model_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage-types": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Passage Types
         * @description List of valid passage types with short descriptions for UI dropdown.
         */
        get: operations["get_passage_types_api_passage_types_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage/{passage_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Passage */
        get: operations["get_passage_api_passage__passage_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Passage Endpoint
         * @description Delete a passage and clean up all references. Children become orphans
         *     (surfaced by validation), not cascade-deleted.
         */
        delete: operations["delete_passage_endpoint_api_passage__passage_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage/{passage_id}/delta": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Passage Delta
         * @description Return the stored snapshot_delta for a passage (or null if none).
         */
        get: operations["get_passage_delta_api_passage__passage_id__delta_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage/{passage_id}/generate-summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Generate Summary For Passage */
        post: operations["generate_summary_for_passage_api_passage__passage_id__generate_summary_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage/{passage_id}/generate-threads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Generate Threads For Passage */
        post: operations["generate_threads_for_passage_api_passage__passage_id__generate_threads_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage/{passage_id}/media/{slot_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Delete Passage Media
         * @description Detach a media slot from a passage and delete it: drop it from
         *     entry.media_slots, remove the slot record, and strip the
         *     ``<!-- media:slot_id -->`` line from the passage .tw file.
         */
        delete: operations["delete_passage_media_api_passage__passage_id__media__slot_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage/{passage_id}/metadata": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Update Passage Metadata */
        post: operations["update_passage_metadata_api_passage__passage_id__metadata_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage/{passage_id}/snapshot": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Reconstructed Snapshot
         * @description Return the reconstructed snapshot for a passage (deltas applied from root).
         */
        get: operations["get_reconstructed_snapshot_api_passage__passage_id__snapshot_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage/{passage_id}/suggest-characters": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Suggest Characters For Passage */
        post: operations["suggest_characters_for_passage_api_passage__passage_id__suggest_characters_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage/{passage_id}/suggest-choices": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Suggest Choices For Passage */
        post: operations["suggest_choices_for_passage_api_passage__passage_id__suggest_choices_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passage/{passage_id}/suggest-state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Suggest State For Passage */
        post: operations["suggest_state_for_passage_api_passage__passage_id__suggest_state_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/passages/{passage_id}/beats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Edit Passage Beats */
        put: operations["edit_passage_beats_api_passages__passage_id__beats_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Plan
         * @description Full planning overview: acts, beats+coverage, arcs+status, and gaps.
         */
        get: operations["get_plan_api_plan_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/acts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Edit Acts */
        put: operations["edit_acts_api_plan_acts_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/arcs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Arc Endpoint
         * @description Create a new empty arc plan by name.
         */
        post: operations["create_arc_endpoint_api_plan_arcs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/arcs/{arc_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Edit Arc Plan */
        put: operations["edit_arc_plan_api_plan_arcs__arc_name__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/arcs/{arc_name}/generate-scenes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Generate Scenes
         * @description AI-outline planned scenes for an arc from premise + arc goal + its beats,
         *     then append them to the arc plan.
         */
        post: operations["generate_scenes_api_plan_arcs__arc_name__generate_scenes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/arcs/{arc_name}/scenes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Scene */
        post: operations["create_scene_api_plan_arcs__arc_name__scenes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/arcs/{arc_name}/scenes/{scene_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Edit Scene */
        put: operations["edit_scene_api_plan_arcs__arc_name__scenes__scene_id__put"];
        post?: never;
        /** Remove Scene */
        delete: operations["remove_scene_api_plan_arcs__arc_name__scenes__scene_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/beats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Beat */
        post: operations["create_beat_api_plan_beats_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/beats/{beat_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Edit Beat */
        put: operations["edit_beat_api_plan_beats__beat_id__put"];
        post?: never;
        /** Remove Beat */
        delete: operations["remove_beat_api_plan_beats__beat_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/generate-arcs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Generate Plan Arcs
         * @description AI-propose new arcs (name + goal) from premise + beats, create them.
         */
        post: operations["generate_plan_arcs_api_plan_generate_arcs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/generate-beats": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Generate Plan Beats
         * @description AI-propose new plot beats from premise + story points, append to the plan.
         */
        post: operations["generate_plan_beats_api_plan_generate_beats_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/import-points": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import Points
         * @description Promote story_points.md headings/bullets into structured plan beats.
         */
        post: operations["import_points_api_plan_import_points_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plan/open-questions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Edit Open Questions */
        put: operations["edit_open_questions_api_plan_open_questions_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Passage Plan */
        post: operations["create_passage_plan_api_plans_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plans/{plan_id}/revisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revise Passage Plan */
        post: operations["revise_passage_plan_api_plans__plan_id__revisions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plans/{plan_id}/revisions/{revision}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Passage Plan */
        get: operations["get_passage_plan_api_plans__plan_id__revisions__revision__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/plans/{plan_id}/revisions/{revision}/approve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Approve Passage Plan */
        post: operations["approve_passage_plan_api_plans__plan_id__revisions__revision__approve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/playtests/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Typed Draft Playtest */
        get: operations["get_typed_draft_playtest_api_playtests__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/premise": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Premise */
        get: operations["get_premise_api_premise_get"];
        put?: never;
        /** Save Premise */
        post: operations["save_premise_api_premise_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/project-status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Project Status
         * @description Return whether project looks empty (for showing init wizard).
         */
        get: operations["project_status_api_project_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/rag/file": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Rag Delete File
         * @description Delete a file from inspiration/. Path is relative to project root.
         */
        delete: operations["rag_delete_file_api_rag_file_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/rag/reindex": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Rag Reindex
         * @description Rebuild the inspiration vector index. Blocks until done.
         */
        post: operations["rag_reindex_api_rag_reindex_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/rag/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Rag Status
         * @description Index stats + on-disk file listing under inspiration/.
         */
        get: operations["rag_status_api_rag_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/rag/upload": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Rag Upload
         * @description Save a file into <project>/inspiration/<filename>.
         *     For images, also writes a sidecar <name>.caption.txt if caption is provided.
         *     Does NOT auto-reindex — call /api/rag/reindex after batch uploads.
         */
        post: operations["rag_upload_api_rag_upload_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/scene-keywords": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Scene Keywords
         * @description Generate scene keywords + one-sentence summary from prose or prompt.
         */
        post: operations["scene_keywords_api_scene_keywords_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Session */
        get: operations["get_session_api_session_get"];
        put?: never;
        /** Update Session */
        post: operations["update_session_api_session_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/simulation-fixtures": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Simulation Fixtures */
        get: operations["get_simulation_fixtures_api_simulation_fixtures_get"];
        /** Update Simulation Fixtures */
        put: operations["update_simulation_fixtures_api_simulation_fixtures_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/simulations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Simulation */
        post: operations["create_simulation_api_simulations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/simulations/{simulation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Simulation */
        get: operations["get_simulation_api_simulations__simulation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/simulations/{simulation_id}/actions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Apply Simulation Action */
        post: operations["apply_simulation_action_api_simulations__simulation_id__actions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/story-index/reindex": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Story Index Reindex
         * @description Rebuild the self-story index over committed passages.
         */
        post: operations["story_index_reindex_api_story_index_reindex_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/story-index/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Story Index Status */
        get: operations["story_index_status_api_story_index_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/suggest-names": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Suggest Names
         * @description Call Ollama with a tiny prompt to suggest passage slug (+ optional arc name).
         */
        post: operations["suggest_names_api_suggest_names_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/systems": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Systems */
        get: operations["get_systems_api_systems_get"];
        /** Update Systems */
        put: operations["update_systems_api_systems_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/templates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Templates */
        get: operations["get_templates_api_templates_get"];
        put?: never;
        /** Create Template */
        post: operations["create_template_api_templates_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/templates/{template_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Template */
        put: operations["update_template_api_templates__template_id__put"];
        post?: never;
        /** Delete Template */
        delete: operations["delete_template_api_templates__template_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/topology": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Topology */
        get: operations["get_topology_api_topology_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/topology/locations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add Topology Location */
        post: operations["add_topology_location_api_topology_locations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/topology/locations/{location_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Topology Location */
        put: operations["update_topology_location_api_topology_locations__location_id__put"];
        post?: never;
        /** Delete Topology Location */
        delete: operations["delete_topology_location_api_topology_locations__location_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/topology/routes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add Topology Route */
        post: operations["add_topology_route_api_topology_routes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/topology/routes/{route_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Update Topology Route */
        put: operations["update_topology_route_api_topology_routes__route_id__put"];
        post?: never;
        /** Delete Topology Route */
        delete: operations["delete_topology_route_api_topology_routes__route_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/tweego/find": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Tweego Find
         * @description Try to locate tweego on disk. Returns found path or None.
         */
        get: operations["tweego_find_api_tweego_find_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/typed/generate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Generate Typed
         * @description Create and persist one validated typed draft revision.
         */
        post: operations["generate_typed_api_typed_generate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Validate */
        get: operations["validate_api_validate_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/legacy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Legacy Spa */
        get: operations["legacy_spa_legacy_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/next": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Next Spa */
        get: operations["next_spa_next_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/{path}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Spa */
        get: operations["spa__path__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActsRequest */
        ActsRequest: {
            /** Acts */
            acts: string[];
        };
        /** AgendaState */
        AgendaState: {
            /**
             * Blocked Reason
             * @default
             */
            blocked_reason: string;
            /**
             * Current Step
             * @default
             */
            current_step: string;
            /** Deadline Tick */
            deadline_tick?: number | null;
            /**
             * Eligibility
             * @default []
             */
            eligibility: components["schemas"]["StateCondition"][];
            /** Goal */
            goal: string;
            /** Id */
            id: string;
            /**
             * Priority
             * @default 0
             */
            priority: number;
            /**
             * Progress
             * @default 0
             */
            progress: number;
            /**
             * Status
             * @default active
             * @enum {string}
             */
            status: "active" | "blocked" | "completed" | "failed";
        };
        /** ArcPlanRequest */
        ArcPlanRequest: {
            /** Beat Ids */
            beat_ids?: string[] | null;
            /**
             * Expected Story Fingerprint
             * @default
             */
            expected_story_fingerprint: string;
            /** Goal */
            goal?: string | null;
            /** Status */
            status?: string | null;
            /** Summary */
            summary?: string | null;
        };
        /** BeatRequest */
        BeatRequest: {
            /**
             * Act
             * @default
             */
            act: string;
            /**
             * Expected Story Fingerprint
             * @default
             */
            expected_story_fingerprint: string;
            /** Text */
            text: string;
        };
        /** BeatUpdateRequest */
        BeatUpdateRequest: {
            /** Act */
            act?: string | null;
            /**
             * Expected Story Fingerprint
             * @default
             */
            expected_story_fingerprint: string;
            /** Text */
            text?: string | null;
        };
        /** BenchmarkPaginationResponse */
        BenchmarkPaginationResponse: {
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /** BenchmarkRunDetailResponse */
        BenchmarkRunDetailResponse: {
            /** Id */
            id: string;
            /** Manifest */
            manifest: {
                [key: string]: unknown;
            };
            pagination: components["schemas"]["BenchmarkPaginationResponse"];
            /** Results */
            results: {
                [key: string]: unknown;
            }[];
            /** Summary */
            summary: string;
        };
        /** BenchmarkRunSummaryResponse */
        BenchmarkRunSummaryResponse: {
            /** Benchmark Name */
            benchmark_name: string;
            /** Benchmark Version */
            benchmark_version: string;
            /** Has Comparison */
            has_comparison: boolean;
            /** Id */
            id: string;
            /** Result Count */
            result_count: number;
            /** Run Id */
            run_id: string;
            /** Started At */
            started_at: string;
        };
        /** BenchmarkRunsResponse */
        BenchmarkRunsResponse: {
            /** Runs */
            runs: components["schemas"]["BenchmarkRunSummaryResponse"][];
        };
        /** CapabilityCard */
        CapabilityCard: {
            /** Card Id */
            card_id: string;
            evidence: components["schemas"]["CapabilityEvidence"];
            identity: components["schemas"]["CapabilityIdentity"];
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Source Sha256 */
            source_sha256: {
                [key: string]: string;
            };
            /** Strategies */
            strategies: components["schemas"]["StrategyCapability"][];
            /**
             * Valid Until
             * Format: date-time
             */
            valid_until: string;
        };
        /** CapabilityCardStatusResponse */
        CapabilityCardStatusResponse: {
            card: components["schemas"]["CapabilityCard"];
            /** Evidence Valid */
            evidence_valid: boolean;
            /** Expired */
            expired: boolean;
            /** Fingerprint */
            fingerprint: string;
            /** Source Valid */
            source_valid: boolean;
        };
        /** CapabilityCardsResponse */
        CapabilityCardsResponse: {
            /** Cards */
            cards: components["schemas"]["CapabilityCardStatusResponse"][];
        };
        /** CapabilityEvidence */
        CapabilityEvidence: {
            /** Browser Manifest */
            browser_manifest: string;
            /** Browser Manifest Sha256 */
            browser_manifest_sha256: string;
            /** Confirmation Report */
            confirmation_report: string;
            /** Confirmation Report Sha256 */
            confirmation_report_sha256: string;
            /** Parent Manifest */
            parent_manifest: string;
            /** Parent Manifest Sha256 */
            parent_manifest_sha256: string;
        };
        /** CapabilityIdentity */
        CapabilityIdentity: {
            /** Compiler Version */
            compiler_version: string;
            /** Contract Schema Version */
            contract_schema_version: number;
            /** Generation Settings Sha256 */
            generation_settings_sha256: string;
            /** Model Digest */
            model_digest: string;
            /** Ollama Version */
            ollama_version: string;
            /** Prompt Profile Sha256 */
            prompt_profile_sha256: string;
            /** Quantization */
            quantization: string;
        };
        /** CharacterEffect */
        CharacterEffect: {
            /** Character Id */
            character_id: string;
            /**
             * Operation
             * @enum {string}
             */
            operation: "set" | "add" | "remove" | "clamp" | "add_fact" | "remove_fact" | "move_character" | "start_condition" | "advance_agenda" | "schedule_activity";
            /**
             * Source
             * @default
             */
            source: string;
            /**
             * Target
             * @default
             */
            target: string;
            /** Value */
            value?: unknown;
        };
        /** CharacterMemory */
        CharacterMemory: {
            /** Expires At Tick */
            expires_at_tick?: number | null;
            /** Fact */
            fact: string;
            /** Id */
            id: string;
            /**
             * Salience
             * @default 0.5
             */
            salience: number;
            /** Source Visit */
            source_visit?: number | null;
        };
        /** CharacterRuntimeState */
        CharacterRuntimeState: {
            /**
             * Activity
             * @default idle
             */
            activity: string;
            /**
             * Agendas
             * @default []
             */
            agendas: components["schemas"]["AgendaState"][];
            /** Character Id */
            character_id: string;
            /**
             * Conditions
             * @default []
             */
            conditions: components["schemas"]["ConditionState"][];
            /** Cooldowns */
            cooldowns?: {
                [key: string]: number;
            };
            /** Current Location */
            current_location: string;
            /** Faction Standings */
            faction_standings?: {
                [key: string]: number;
            };
            /** Inventory */
            inventory?: {
                [key: string]: number;
            };
            /**
             * Known Facts
             * @default []
             */
            known_facts: string[];
            /**
             * Last Updated Tick
             * @default 0
             */
            last_updated_tick: number;
            /**
             * Memories
             * @default []
             */
            memories: components["schemas"]["CharacterMemory"][];
            /**
             * Needs
             * @default []
             */
            needs: components["schemas"]["NeedState"][];
            /**
             * Relationships
             * @default []
             */
            relationships: components["schemas"]["RelationshipState"][];
            /**
             * Revision
             * @default 1
             */
            revision: number;
            /**
             * Schedules
             * @default []
             */
            schedules: components["schemas"]["ScheduleRule"][];
            /** Stats */
            stats?: {
                [key: string]: unknown;
            };
        };
        /**
         * CharacterSimulation
         * @enum {string}
         */
        CharacterSimulation: "none" | "relationships" | "persistent_stats" | "full_agendas";
        /** CharacterStatDefinition */
        CharacterStatDefinition: {
            /**
             * Allowed Operations
             * @default [
             *       "set"
             *     ]
             */
            allowed_operations: ("set" | "add" | "clamp")[];
            /** Decay Per Tick */
            decay_per_tick?: number | null;
            /** Default */
            default: unknown;
            /**
             * Description
             * @default
             */
            description: string;
            /** Id */
            id: string;
            /** Maximum */
            maximum?: number | null;
            /** Minimum */
            minimum?: number | null;
            /**
             * Value Type
             * @enum {string}
             */
            value_type: "bool" | "int" | "float" | "string";
            /**
             * Visibility
             * @default model
             * @enum {string}
             */
            visibility: "public" | "model" | "private";
        };
        /** ChoiceSlot */
        ChoiceSlot: {
            /**
             * Conditions
             * @default []
             */
            conditions: components["schemas"]["StateCondition"][];
            /**
             * Destination
             * @default
             */
            destination: string;
            /**
             * Effects
             * @default []
             */
            effects: components["schemas"]["StateEffect"][];
            /** Id */
            id: string;
            /**
             * Restart
             * @default false
             */
            restart: boolean;
            /**
             * Weight
             * @default 1
             */
            weight: number;
        };
        /** CommitRequest */
        CommitRequest: {
            /** Arc Name */
            arc_name: string;
            /**
             * Branch Name
             * @default main
             */
            branch_name: string;
            /** Choice Index */
            choice_index?: number | null;
            /**
             * Dialogue Npc
             * @default
             */
            dialogue_npc: string;
            /**
             * Entry Condition
             * @default
             */
            entry_condition: string;
            /**
             * Event Odds
             * @default 100
             */
            event_odds: number;
            /**
             * Exits
             * @default {}
             */
            exits: {
                [key: string]: string;
            };
            /**
             * Fallback Passage
             * @default
             */
            fallback_passage: string;
            /** Override Parsed */
            override_parsed?: {
                [key: string]: unknown;
            } | null;
            /** Parent Passage Id */
            parent_passage_id?: string | null;
            /** Passage Slug */
            passage_slug: string;
            /**
             * Passage Type
             * @default normal
             */
            passage_type: string;
            /** Raw Output */
            raw_output: string;
            /**
             * Skill Branch
             * @default
             */
            skill_branch: string;
        };
        /** CompileArtifact */
        CompileArtifact: {
            /** Compiler Version */
            compiler_version: string;
            /**
             * Diagnostics
             * @default []
             */
            diagnostics: components["schemas"]["Diagnostic"][];
            /**
             * Link Targets
             * @default []
             */
            link_targets: string[];
            /**
             * Media Placeholders
             * @default []
             */
            media_placeholders: string[];
            /**
             * Schema Version
             * @default 1
             */
            schema_version: number;
            /** Source Draft Fingerprint */
            source_draft_fingerprint: string;
            /**
             * Source Map
             * @default []
             */
            source_map: components["schemas"]["SourceMapEntry"][];
            /**
             * State Reads
             * @default []
             */
            state_reads: string[];
            /**
             * State Writes
             * @default []
             */
            state_writes: components["schemas"]["StateEffect"][];
            /** Twee Source */
            twee_source: string;
        };
        /** ConditionState */
        ConditionState: {
            /** Id */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "injury" | "illness" | "mood" | "buff" | "debuff";
            /** Remaining Ticks */
            remaining_ticks?: number | null;
            /**
             * Severity
             * @default 0
             */
            severity: number;
            /**
             * Source
             * @default
             */
            source: string;
        };
        /**
         * ContextPack
         * @description Bounded story context with explicit trusted and untrusted sections.
         */
        ContextPack: {
            /**
             * Entity Facts
             * @default []
             */
            entity_facts: string[];
            /**
             * Inspiration
             * @default
             */
            inspiration: string;
            /**
             * Open Threads
             * @default []
             */
            open_threads: string[];
            /**
             * Parent Passage Id
             * @default
             */
            parent_passage_id: string;
            /**
             * Parent Prose
             * @default
             */
            parent_prose: string;
            /**
             * Parent Summary
             * @default
             */
            parent_summary: string;
            /**
             * Premise
             * @default
             */
            premise: string;
            /**
             * Story Recall
             * @default
             */
            story_recall: string;
            /**
             * World Facts
             * @default []
             */
            world_facts: string[];
        };
        /** ContinuityProposal */
        ContinuityProposal: {
            /**
             * Evidence Slot Ids
             * @default []
             */
            evidence_slot_ids: string[];
            /** Key */
            key: string;
            /** Value */
            value: string;
        };
        /** CreateArcRequest */
        CreateArcRequest: {
            /**
             * Expected Story Fingerprint
             * @default
             */
            expected_story_fingerprint: string;
            /**
             * Goal
             * @default
             */
            goal: string;
            /** Name */
            name: string;
        };
        /** DeleteModelRequest */
        DeleteModelRequest: {
            /** Model */
            model: string;
        };
        /** Diagnostic */
        Diagnostic: {
            /** Code */
            code: string;
            level: components["schemas"]["DiagnosticLevel"];
            /** Message */
            message: string;
            owner: components["schemas"]["DiagnosticOwner"];
            /**
             * Path
             * @default []
             */
            path: (string | number)[];
            stage: components["schemas"]["DiagnosticStage"];
        };
        /**
         * DiagnosticLevel
         * @enum {string}
         */
        DiagnosticLevel: "info" | "warning" | "error";
        /**
         * DiagnosticOwner
         * @enum {string}
         */
        DiagnosticOwner: "plan" | "model_fill" | "harness_compiler" | "runtime" | "commit";
        /**
         * DiagnosticStage
         * @enum {string}
         */
        DiagnosticStage: "plan" | "narrative" | "mechanics" | "compile" | "playtest" | "commit";
        /**
         * DraftLifecycle
         * @enum {string}
         */
        DraftLifecycle: "generated" | "edited" | "validated" | "committed" | "rejected" | "superseded";
        /** DraftRecord */
        DraftRecord: {
            /**
             * Arc Name
             * @default
             */
            arc_name: string;
            /**
             * Branch Name
             * @default main
             */
            branch_name: string;
            compile_artifact?: components["schemas"]["CompileArtifact"] | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at?: string;
            /**
             * Diagnostics
             * @default []
             */
            diagnostics: components["schemas"]["Diagnostic"][];
            draft: components["schemas"]["PassageDraft"];
            /** Generation Id */
            generation_id: string;
            lifecycle_state: components["schemas"]["DraftLifecycle"];
            /** Parent Choice Index */
            parent_choice_index?: number | null;
            /**
             * Parent Fingerprint
             * @default
             */
            parent_fingerprint: string;
            /**
             * Parent Passage Id
             * @default
             */
            parent_passage_id: string;
            /** Parent Revision */
            parent_revision?: number | null;
            /**
             * Passage Id
             * @default
             */
            passage_id: string;
            provenance: components["schemas"]["GenerationProvenance"];
            /**
             * Schema Version
             * @default 1
             */
            schema_version: number;
        };
        /** EncounterCatalogRequest */
        EncounterCatalogRequest: {
            /** Expected Fingerprint */
            expected_fingerprint: string;
            /** Templates */
            templates: components["schemas"]["EncounterTemplate"][];
        };
        /** EncounterTemplate */
        EncounterTemplate: {
            /**
             * Cooldown Ticks
             * @default 0
             */
            cooldown_ticks: number;
            /**
             * Eligibility
             * @default []
             */
            eligibility: components["schemas"]["StateCondition"][];
            /** Id */
            id: string;
            /** Label */
            label: string;
            /**
             * Location Ids
             * @default []
             */
            location_ids: string[];
            /** Occurrence Limit */
            occurrence_limit?: number | null;
            plan: components["schemas"]["PassagePlan"];
            /**
             * Required Tags
             * @default []
             */
            required_tags: string[];
            /**
             * Variation Slots
             * @default []
             */
            variation_slots: string[];
            /**
             * Weight
             * @default 1
             */
            weight: number;
        };
        /**
         * EndingPolicy
         * @enum {string}
         */
        EndingPolicy: "required" | "optional" | "none";
        /** EntityReferencePart */
        EntityReferencePart: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "entity_ref";
            /** Target */
            target: string;
        };
        /**
         * ExperienceMode
         * @enum {string}
         */
        ExperienceMode: "story_driven" | "hybrid" | "sandbox";
        /** ExperienceOverride */
        ExperienceOverride: {
            character_simulation?: components["schemas"]["CharacterSimulation"] | null;
            /** Encounter Reuse */
            encounter_reuse?: boolean | null;
            ending_policy?: components["schemas"]["EndingPolicy"] | null;
            /** Failure Persistence */
            failure_persistence?: boolean | null;
            goal_model?: components["schemas"]["GoalModel"] | null;
            /** Main Plot Required */
            main_plot_required?: boolean | null;
            /** Narrative Pressure */
            narrative_pressure?: number | null;
            /** Scope Id */
            scope_id: string;
            /**
             * Scope Kind
             * @enum {string}
             */
            scope_kind: "arc" | "region" | "scenario";
            story_guidance?: components["schemas"]["StoryGuidance"] | null;
            time_model?: components["schemas"]["TimeModel"] | null;
            /** World Reactivity */
            world_reactivity?: number | null;
        };
        /** ExperienceProfile */
        ExperienceProfile: {
            character_simulation: components["schemas"]["CharacterSimulation"];
            /** Encounter Reuse */
            encounter_reuse: boolean;
            ending_policy: components["schemas"]["EndingPolicy"];
            /** Failure Persistence */
            failure_persistence: boolean;
            goal_model: components["schemas"]["GoalModel"];
            /** Main Plot Required */
            main_plot_required: boolean;
            mode: components["schemas"]["ExperienceMode"];
            /** Narrative Pressure */
            narrative_pressure: number;
            /**
             * Overrides
             * @default []
             */
            overrides: components["schemas"]["ExperienceOverride"][];
            /**
             * Revision
             * @default 1
             */
            revision: number;
            /**
             * Schema Version
             * @default 1
             */
            schema_version: number;
            story_guidance: components["schemas"]["StoryGuidance"];
            time_model: components["schemas"]["TimeModel"];
            /** World Reactivity */
            world_reactivity: number;
        };
        /** ExperienceProfilePreviewRequest */
        ExperienceProfilePreviewRequest: {
            /** Expected Revision */
            expected_revision: number;
            profile: components["schemas"]["ExperienceProfile"];
        };
        /** ExperienceProfileRevisionRequest */
        ExperienceProfileRevisionRequest: {
            /** Expected Revision */
            expected_revision: number;
            /** Preview Fingerprint */
            preview_fingerprint: string;
            profile: components["schemas"]["ExperienceProfile"];
        };
        /** ExtractEntitiesRequest */
        ExtractEntitiesRequest: {
            /**
             * Direction
             * @default
             */
            direction: string;
            /** Prose */
            prose: string;
        };
        /** FactApproval */
        FactApproval: {
            /** Action */
            action: string;
            /**
             * Backstory
             * @default
             */
            backstory: string;
            /** Category */
            category?: string | null;
            /** Id */
            id: string;
            /**
             * Motivation
             * @default
             */
            motivation: string;
            /**
             * Personality
             * @default
             */
            personality: string;
            /**
             * Physical
             * @default
             */
            physical: string;
            /**
             * Prose Sheet
             * @default
             */
            prose_sheet: string;
            /**
             * Relationships
             * @default
             */
            relationships: string;
            /**
             * Speech
             * @default
             */
            speech: string;
            /** Type */
            type: string;
        };
        /** FactionEffect */
        FactionEffect: {
            /** Delta */
            delta: number;
            /** Faction Id */
            faction_id: string;
            /**
             * Operation
             * @enum {string}
             */
            operation: "influence" | "disposition" | "resource" | "relationship";
            /**
             * Target
             * @default
             */
            target: string;
        };
        /** FactionState */
        FactionState: {
            /**
             * Disposition
             * @default 0
             */
            disposition: number;
            /** Faction Id */
            faction_id: string;
            /**
             * Influence
             * @default 0
             */
            influence: number;
            /** Relationships */
            relationships?: {
                [key: string]: number;
            };
            /** Resources */
            resources?: {
                [key: string]: number;
            };
        };
        /** FilledChoiceSlot */
        FilledChoiceSlot: {
            /**
             * Hint
             * @default
             */
            hint: string;
            /** Slot Id */
            slot_id: string;
            /** Text */
            text: string;
        };
        /** FilledNarrativeSlot */
        FilledNarrativeSlot: {
            kind: components["schemas"]["NarrativeBlockKind"];
            /** Parts */
            parts: (components["schemas"]["TextPart"] | components["schemas"]["StateReferencePart"] | components["schemas"]["EntityReferencePart"])[];
            /** Slot Id */
            slot_id: string;
            /**
             * Speaker
             * @default
             */
            speaker: string;
        };
        /** FormField */
        FormField: {
            /**
             * Autocheck
             * @default false
             */
            autocheck: boolean;
            /**
             * Autofocus
             * @default false
             */
            autofocus: boolean;
            /**
             * Autoselect
             * @default false
             */
            autoselect: boolean;
            /**
             * Checked
             * @default false
             */
            checked: boolean;
            /**
             * Checked Value
             * @default
             */
            checked_value: string;
            /** Default */
            default?: unknown;
            /** Id */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "textbox" | "numberbox" | "textarea" | "checkbox" | "radiobutton" | "listbox" | "cycle";
            /**
             * Label
             * @default
             */
            label: string;
            /**
             * Once
             * @default false
             */
            once: boolean;
            /**
             * Options
             * @default []
             */
            options: components["schemas"]["FormOption"][];
            /**
             * Unchecked Value
             * @default
             */
            unchecked_value: string;
        };
        /** FormOption */
        FormOption: {
            /** Label */
            label: string;
            /**
             * Selected
             * @default false
             */
            selected: boolean;
            /**
             * Value
             * @default
             */
            value: string;
        };
        /** GenItemsRequest */
        GenItemsRequest: {
            /**
             * Count
             * @default 5
             */
            count: number;
            /**
             * Direction
             * @default
             */
            direction: string;
        };
        /** GenOpeningRequest */
        GenOpeningRequest: {
            /**
             * Direction
             * @default
             */
            direction: string;
            /** Inspiration Files */
            inspiration_files?: string[];
            /** Premise */
            premise: string;
            /**
             * World Overview
             * @default
             */
            world_overview: string;
        };
        /** GenPremiseRequest */
        GenPremiseRequest: {
            /**
             * Direction
             * @default
             */
            direction: string;
            /** Inspiration Files */
            inspiration_files?: string[];
            /**
             * Seed
             * @default
             */
            seed: string;
        };
        /** GenSketchRequest */
        GenSketchRequest: {
            /**
             * Count
             * @default 3
             */
            count: number;
            /**
             * Direction
             * @default
             */
            direction: string;
            /** Inspiration Files */
            inspiration_files?: string[];
            /** Premise */
            premise: string;
            /**
             * World Overview
             * @default
             */
            world_overview: string;
        };
        /** GenToneThemesRequest */
        GenToneThemesRequest: {
            /**
             * Direction
             * @default
             */
            direction: string;
            /** Inspiration Files */
            inspiration_files?: string[];
            /** Premise */
            premise: string;
        };
        /** GenWorldRequest */
        GenWorldRequest: {
            /**
             * Direction
             * @default
             */
            direction: string;
            /** Inspiration Files */
            inspiration_files?: string[];
            /** Premise */
            premise: string;
            /**
             * Themes
             * @default
             */
            themes: string;
            /**
             * Tone
             * @default
             */
            tone: string;
        };
        /** GenerateKeywordsBody */
        GenerateKeywordsBody: {
            /**
             * Direction
             * @default
             */
            direction: string;
        };
        /** GenerateRequest */
        GenerateRequest: {
            /** Arc Name */
            arc_name: string;
            /**
             * Branch Name
             * @default main
             */
            branch_name: string;
            /** Choice Index */
            choice_index?: number | null;
            /**
             * Extra Ideas
             * @default
             */
            extra_ideas: string;
            /** Inspiration Files */
            inspiration_files?: string[];
            /**
             * Inspiration Text
             * @default
             */
            inspiration_text: string;
            /**
             * Mode
             * @default co-author
             */
            mode: string;
            /** Parent Passage Id */
            parent_passage_id?: string | null;
            /** Passage Slug */
            passage_slug: string;
            /** Prompt */
            prompt: string;
        };
        /** GenerateScenesRequest */
        GenerateScenesRequest: {
            /**
             * Count
             * @default 4
             */
            count: number;
            /**
             * Direction
             * @default
             */
            direction: string;
        };
        /** GenerateStoryPointsRequest */
        GenerateStoryPointsRequest: {
            /**
             * Direction
             * @default
             */
            direction: string;
            /** Inspiration Files */
            inspiration_files?: string[];
            /**
             * Num Acts
             * @default 3
             */
            num_acts: number;
            /**
             * Premise
             * @default
             */
            premise: string;
            /**
             * Themes
             * @default
             */
            themes: string;
            /**
             * Tone
             * @default
             */
            tone: string;
            /**
             * World Overview
             * @default
             */
            world_overview: string;
        };
        /** GenerationProvenance */
        GenerationProvenance: {
            /** Effective Configuration */
            effective_configuration?: {
                [key: string]: unknown;
            };
            /**
             * Finish Reason
             * @default
             */
            finish_reason: string;
            /**
             * Ingestion Profile Fingerprint
             * @default
             */
            ingestion_profile_fingerprint: string;
            /** Input Tokens */
            input_tokens?: number | null;
            /** Latency Seconds */
            latency_seconds?: number | null;
            /**
             * Model Digest
             * @default
             */
            model_digest: string;
            /**
             * Model Name
             * @default
             */
            model_name: string;
            /** Output Tokens */
            output_tokens?: number | null;
            /**
             * Raw Model Output
             * @default
             */
            raw_model_output: string;
            /**
             * Rendered Prompt
             * @default
             */
            rendered_prompt: string;
            /** Seed */
            seed?: number | null;
        };
        /**
         * GoalModel
         * @enum {string}
         */
        GoalModel: "authored" | "mixed" | "player_directed";
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** ImportMediaRequest */
        ImportMediaRequest: {
            /**
             * Dest Name
             * @default
             */
            dest_name: string;
            /** Src Path */
            src_path: string;
        };
        /** ImportPointsRequest */
        ImportPointsRequest: {
            /**
             * Replace
             * @default false
             */
            replace: boolean;
        };
        /** InspirationSummaryRequest */
        InspirationSummaryRequest: {
            /**
             * Path
             * @default
             */
            path: string;
            /**
             * Text
             * @default
             */
            text: string;
        };
        /** KeywordsBody */
        KeywordsBody: {
            /** Keywords */
            keywords: string[];
        };
        /** LocationAction */
        LocationAction: {
            /**
             * Effects
             * @default []
             */
            effects: components["schemas"]["StateEffect"][];
            /**
             * Eligibility
             * @default []
             */
            eligibility: components["schemas"]["StateCondition"][];
            /**
             * Encounter Table Refs
             * @default []
             */
            encounter_table_refs: string[];
            /** Id */
            id: string;
            /** Label */
            label: string;
            /**
             * Time Cost
             * @default 1
             */
            time_cost: number;
        };
        /** LocationNode */
        LocationNode: {
            /**
             * Actions
             * @default []
             */
            actions: components["schemas"]["LocationAction"][];
            /**
             * Encounter Table Refs
             * @default []
             */
            encounter_table_refs: string[];
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Region Id */
            region_id: string;
            /**
             * Tags
             * @default []
             */
            tags: string[];
        };
        /** LoopBinding */
        LoopBinding: {
            /** Collection */
            collection: string;
            /** Variable */
            variable: string;
        };
        /** MechanicProposal */
        MechanicProposal: {
            /** Plan Id */
            plan_id: string;
            /** Plan Revision */
            plan_revision: number;
            /**
             * Revision
             * @default 1
             */
            revision: number;
            /**
             * Schema Version
             * @default 1
             */
            schema_version: number;
            /** Values */
            values: components["schemas"]["MechanicValue"][];
        };
        /** MechanicSlot */
        MechanicSlot: {
            /**
             * Allowed Operations
             * @default []
             */
            allowed_operations: components["schemas"]["StateOperation"][];
            /**
             * Allowed Targets
             * @default []
             */
            allowed_targets: string[];
            /** Id */
            id: string;
            /**
             * Required
             * @default false
             */
            required: boolean;
        };
        /** MechanicValue */
        MechanicValue: {
            operation: components["schemas"]["StateOperation"];
            /** Slot Id */
            slot_id: string;
            /** Target */
            target: string;
            /** Value */
            value?: unknown;
        };
        /** MediaProposal */
        MediaProposal: {
            /**
             * Description
             * @default
             */
            description: string;
            /** Keywords */
            keywords: string[];
            /** Slot Id */
            slot_id: string;
        };
        /**
         * NarrativeBlockKind
         * @enum {string}
         */
        NarrativeBlockKind: "paragraph" | "dialogue" | "thought";
        /** NarrativeFill */
        NarrativeFill: {
            /** Beats */
            beats: string[];
            /** Choices */
            choices: components["schemas"]["FilledChoiceSlot"][];
            /**
             * Continuity Proposals
             * @default []
             */
            continuity_proposals: components["schemas"]["ContinuityProposal"][];
            /**
             * Media Proposals
             * @default []
             */
            media_proposals: components["schemas"]["MediaProposal"][];
            /** Narrative */
            narrative: components["schemas"]["FilledNarrativeSlot"][];
            /** Plan Id */
            plan_id: string;
            /** Plan Revision */
            plan_revision: number;
            /**
             * Revision
             * @default 1
             */
            revision: number;
            /**
             * Schema Version
             * @default 1
             */
            schema_version: number;
            /** Summary */
            summary: string;
        };
        /** NarrativeSlot */
        NarrativeSlot: {
            /** Id */
            id: string;
            kind: components["schemas"]["NarrativeBlockKind"];
            /**
             * Speaker
             * @default
             */
            speaker: string;
        };
        /** NeedState */
        NeedState: {
            /**
             * Change Per Tick
             * @default 0
             */
            change_per_tick: number;
            /** Id */
            id: string;
            /** Value */
            value: number;
        };
        /** NewCharacterRequest */
        NewCharacterRequest: {
            /**
             * Description
             * @default
             */
            description: string;
            /** Id */
            id: string;
            /**
             * Name
             * @default
             */
            name: string;
            /**
             * Tags
             * @default []
             */
            tags: string[];
        };
        /** NewLoreRequest */
        NewLoreRequest: {
            /** Category */
            category: string;
            /**
             * Description
             * @default
             */
            description: string;
            /** Id */
            id: string;
            /**
             * Title
             * @default
             */
            title: string;
        };
        /** NewNoteRequest */
        NewNoteRequest: {
            /** Id */
            id: string;
            /**
             * Title
             * @default
             */
            title: string;
        };
        /** OpenQuestionsRequest */
        OpenQuestionsRequest: {
            /** Questions */
            questions: string[];
        };
        /** PassageBeatsRequest */
        PassageBeatsRequest: {
            /** Beat Ids */
            beat_ids: string[];
        };
        /** PassageDraft */
        PassageDraft: {
            /** Draft Id */
            draft_id: string;
            fill: components["schemas"]["NarrativeFill"];
            mechanic_proposal?: components["schemas"]["MechanicProposal"] | null;
            plan: components["schemas"]["PassagePlan"];
            /**
             * Resolved Effects
             * @default []
             */
            resolved_effects: components["schemas"]["StateEffect"][];
            /**
             * Resolved Required Components
             * @default []
             */
            resolved_required_components: string[];
            /** Revision */
            revision: number;
            /**
             * Schema Version
             * @default 1
             */
            schema_version: number;
        };
        /** PassageMediaSlotEdit */
        PassageMediaSlotEdit: {
            /** Id */
            id: string;
            /**
             * Keywords
             * @default []
             */
            keywords: string[];
            /**
             * Type
             * @default image
             */
            type: string;
        };
        /** PassageMetadataUpdate */
        PassageMetadataUpdate: {
            /** Characters Present */
            characters_present?: components["schemas"]["SceneCharacterEdit"][] | null;
            /** Children */
            children?: string[] | null;
            /** Media Slots */
            media_slots?: components["schemas"]["PassageMediaSlotEdit"][] | null;
            /** Open Threads */
            open_threads?: string[] | null;
            /** State Writes */
            state_writes?: string[] | null;
            /** Summary */
            summary?: string | null;
            /** World State */
            world_state?: string[] | null;
        };
        /**
         * PassageMode
         * @enum {string}
         */
        PassageMode: "normal" | "conditional" | "event" | "random_event" | "dialogue" | "dialogue_loop" | "ending" | "form" | "hub" | "loop" | "random" | "room" | "widget" | "include";
        /** PassagePlan */
        PassagePlan: {
            /**
             * Allowed Effects
             * @default []
             */
            allowed_effects: components["schemas"]["StateEffect"][];
            /**
             * Allowed Entity Refs
             * @default []
             */
            allowed_entity_refs: string[];
            /**
             * Allowed State Refs
             * @default []
             */
            allowed_state_refs: string[];
            /** Choice Slots */
            choice_slots: components["schemas"]["ChoiceSlot"][];
            /**
             * Context Fingerprint
             * @default
             */
            context_fingerprint: string;
            /** Cooldown */
            cooldown?: number | null;
            /**
             * Eligibility
             * @default []
             */
            eligibility: components["schemas"]["StateCondition"][];
            /**
             * Event Odds
             * @default 100
             */
            event_odds: number;
            /**
             * Exits
             * @default []
             */
            exits: components["schemas"]["RouteSlot"][];
            /**
             * Experience Profile Fingerprint
             * @default
             */
            experience_profile_fingerprint: string;
            /** Expiry */
            expiry?: number | null;
            /**
             * Fallback Passage
             * @default
             */
            fallback_passage: string;
            /**
             * Fixed Effects
             * @default []
             */
            fixed_effects: components["schemas"]["StateEffect"][];
            /**
             * Form Fields
             * @default []
             */
            form_fields: components["schemas"]["FormField"][];
            loop_binding?: components["schemas"]["LoopBinding"] | null;
            /**
             * Mechanic Slots
             * @default []
             */
            mechanic_slots: components["schemas"]["MechanicSlot"][];
            /** Narrative Slots */
            narrative_slots: components["schemas"]["NarrativeSlot"][];
            passage_mode: components["schemas"]["PassageMode"];
            /** Plan Id */
            plan_id: string;
            /**
             * Reentry Policy
             * @default forbid
             * @enum {string}
             */
            reentry_policy: "forbid" | "allow" | "refresh";
            /**
             * Repeatable
             * @default false
             */
            repeatable: boolean;
            /**
             * Required Components
             * @default []
             */
            required_components: string[];
            /** Revision */
            revision: number;
            /**
             * Schema Version
             * @default 1
             */
            schema_version: number;
            /** Time Cost */
            time_cost?: number | null;
        };
        /** PassagePlanApprovalRequest */
        PassagePlanApprovalRequest: {
            /** Expected Plan Fingerprint */
            expected_plan_fingerprint: string;
        };
        /** PassagePlanCreateRequest */
        PassagePlanCreateRequest: {
            /**
             * Arc Name
             * @default
             */
            arc_name: string;
            plan: components["schemas"]["PassagePlan"];
        };
        /** PassagePlanRecordResponse */
        PassagePlanRecordResponse: {
            /** Approved */
            approved: boolean;
            /** Fingerprint */
            fingerprint: string;
            plan: components["schemas"]["PassagePlan"];
        };
        /** PassagePlanRevisionRequest */
        PassagePlanRevisionRequest: {
            /**
             * Arc Name
             * @default
             */
            arc_name: string;
            /** Expected Plan Fingerprint */
            expected_plan_fingerprint: string;
            plan: components["schemas"]["PassagePlan"];
        };
        /** PlanDeleteRequest */
        PlanDeleteRequest: {
            /**
             * Expected Story Fingerprint
             * @default
             */
            expected_story_fingerprint: string;
        };
        /** RagUploadRequest */
        RagUploadRequest: {
            /**
             * Caption
             * @default
             */
            caption: string;
            /** Content B64 */
            content_b64: string;
            /** Filename */
            filename: string;
        };
        /** RelationshipState */
        RelationshipState: {
            /** Target Character Id */
            target_character_id: string;
            /** Values */
            values?: {
                [key: string]: number;
            };
        };
        /** ResolveSlotRequest */
        ResolveSlotRequest: {
            /**
             * Expected Slot Fingerprint
             * @default
             */
            expected_slot_fingerprint: string;
            /** Resolved Path */
            resolved_path: string;
        };
        /** Route */
        Route: {
            /** Destination */
            destination: string;
            /**
             * Eligibility
             * @default []
             */
            eligibility: components["schemas"]["StateCondition"][];
            /** Id */
            id: string;
            /** Resource Cost */
            resource_cost?: {
                [key: string]: number;
            };
            /**
             * Risk Tags
             * @default []
             */
            risk_tags: string[];
            /** Source */
            source: string;
            /**
             * Time Cost
             * @default 1
             */
            time_cost: number;
            /**
             * Travel Effects
             * @default []
             */
            travel_effects: components["schemas"]["StateEffect"][];
        };
        /** RouteSlot */
        RouteSlot: {
            /** Destination */
            destination: string;
            /** Label */
            label: string;
        };
        /** SaveCharacterRequest */
        SaveCharacterRequest: {
            /** Content */
            content: string;
            /**
             * Expected Content Fingerprint
             * @default
             */
            expected_content_fingerprint: string;
        };
        /** SaveLoreRequest */
        SaveLoreRequest: {
            /** Content */
            content: string;
            /**
             * Expected Content Fingerprint
             * @default
             */
            expected_content_fingerprint: string;
        };
        /** SaveNoteRequest */
        SaveNoteRequest: {
            /** Content */
            content: string;
        };
        /** SavePremiseRequest */
        SavePremiseRequest: {
            /** Premise */
            premise?: string | null;
            /** Story Points */
            story_points?: string | null;
        };
        /** SceneCharacterEdit */
        SceneCharacterEdit: {
            /** Id */
            id: string;
            /**
             * Knows
             * @default []
             */
            knows: string[];
            /**
             * Relationship To Player
             * @default
             */
            relationship_to_player: string;
            /**
             * Status
             * @default present
             */
            status: string;
        };
        /** SceneKeywordsRequest */
        SceneKeywordsRequest: {
            /** Text */
            text: string;
        };
        /** SceneRequest */
        SceneRequest: {
            /** Beat Ids */
            beat_ids?: string[];
            /** Characters */
            characters?: string[];
            /**
             * Expected Story Fingerprint
             * @default
             */
            expected_story_fingerprint: string;
            /** Keywords */
            keywords?: string[];
            /**
             * Summary
             * @default
             */
            summary: string;
            /**
             * Title
             * @default
             */
            title: string;
        };
        /** SceneUpdateRequest */
        SceneUpdateRequest: {
            /** Beat Ids */
            beat_ids?: string[] | null;
            /** Characters */
            characters?: string[] | null;
            /**
             * Expected Story Fingerprint
             * @default
             */
            expected_story_fingerprint: string;
            /** Keywords */
            keywords?: string[] | null;
            /** Passage Id */
            passage_id?: string | null;
            /** Status */
            status?: string | null;
            /** Summary */
            summary?: string | null;
            /** Title */
            title?: string | null;
        };
        /** ScheduleRule */
        ScheduleRule: {
            /** Activity */
            activity: string;
            /** End Tick */
            end_tick?: number | null;
            /** Id */
            id: string;
            /** Location Id */
            location_id: string;
            /**
             * Priority
             * @default 0
             */
            priority: number;
            /** Start Tick */
            start_tick: number;
        };
        /** SessionUpdate */
        SessionUpdate: {
            /** Active Mode */
            active_mode?: string | null;
            /** Current Branch */
            current_branch?: string | null;
            /** Current Passage */
            current_passage?: string | null;
        };
        /** SimulationActionRequest */
        SimulationActionRequest: {
            /** Action Id */
            action_id: string;
            /** Expected Revision */
            expected_revision: number;
            /** Kind */
            kind: string;
        };
        /** SimulationCreateRequest */
        SimulationCreateRequest: {
            /**
             * Character Stat Definitions
             * @default []
             */
            character_stat_definitions: components["schemas"]["CharacterStatDefinition"][];
            /**
             * Characters
             * @default []
             */
            characters: components["schemas"]["CharacterRuntimeState"][];
            /**
             * Factions
             * @default []
             */
            factions: components["schemas"]["FactionState"][];
            /** Fixture Id */
            fixture_id?: string | null;
            /** Resources */
            resources?: {
                [key: string]: number;
            };
            /** Seed */
            seed?: number | null;
            /** Start Location */
            start_location?: string | null;
            /** World State */
            world_state?: {
                [key: string]: unknown;
            };
        };
        /**
         * SimulationFixture
         * @description Named, authored initial state for a disposable simulation.
         */
        SimulationFixture: {
            /**
             * Character Stat Definitions
             * @default []
             */
            character_stat_definitions: components["schemas"]["CharacterStatDefinition"][];
            /**
             * Characters
             * @default []
             */
            characters: components["schemas"]["CharacterRuntimeState"][];
            /**
             * Factions
             * @default []
             */
            factions: components["schemas"]["FactionState"][];
            /** Id */
            id: string;
            /** Label */
            label: string;
            /** Resources */
            resources?: {
                [key: string]: number;
            };
            /**
             * Seed
             * @default 1
             */
            seed: number;
            /** Start Location */
            start_location: string;
            /** World State */
            world_state?: {
                [key: string]: unknown;
            };
        };
        /** SimulationFixtureCatalogRequest */
        SimulationFixtureCatalogRequest: {
            /** Expected Fingerprint */
            expected_fingerprint: string;
            /** Fixtures */
            fixtures: components["schemas"]["SimulationFixture"][];
        };
        /** SlotMetaRequest */
        SlotMetaRequest: {
            /** Alt */
            alt?: string | null;
            /** Autoplay */
            autoplay?: boolean | null;
            /** Caption */
            caption?: string | null;
            /** Controls */
            controls?: boolean | null;
            /** Description */
            description?: string | null;
            /**
             * Expected Slot Fingerprint
             * @default
             */
            expected_slot_fingerprint: string;
            /** Keywords */
            keywords?: string[] | null;
            /** Lazy */
            lazy?: boolean | null;
            /** Loop */
            loop?: boolean | null;
            /** Muted */
            muted?: boolean | null;
            /** Poster */
            poster?: string | null;
            /** Type */
            type?: string | null;
        };
        /** SlotMutationGuard */
        SlotMutationGuard: {
            /**
             * Expected Slot Fingerprint
             * @default
             */
            expected_slot_fingerprint: string;
        };
        /** SourceMapEntry */
        SourceMapEntry: {
            /** End */
            end: number;
            /** Source Path */
            source_path: (string | number)[];
            /** Start */
            start: number;
        };
        /** StateCondition */
        StateCondition: {
            /**
             * Operation
             * @enum {string}
             */
            operation: "eq" | "ne" | "gt" | "gte" | "lt" | "lte" | "truthy" | "falsy";
            /** Target */
            target: string;
            /** Value */
            value?: unknown;
        };
        /** StateEffect */
        StateEffect: {
            /** Component Id */
            component_id: string;
            operation: components["schemas"]["StateOperation"];
            /**
             * Source
             * @default
             */
            source: string;
            /** Target */
            target: string;
            /** Value */
            value?: unknown;
        };
        /**
         * StateOperation
         * @enum {string}
         */
        StateOperation: "set" | "add" | "subtract" | "toggle";
        /** StateReferencePart */
        StateReferencePart: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "state_ref";
            /** Target */
            target: string;
        };
        /**
         * StoryGuidance
         * @enum {string}
         */
        StoryGuidance: "off" | "light" | "anchors" | "directed";
        /** StoryInitRequest */
        StoryInitRequest: {
            /**
             * Characters
             * @default []
             */
            characters: {
                [key: string]: unknown;
            }[];
            /**
             * Locations
             * @default []
             */
            locations: {
                [key: string]: unknown;
            }[];
            /**
             * Opening Situation
             * @default
             */
            opening_situation: string;
            /**
             * Premise
             * @default
             */
            premise: string;
            /**
             * Story Points
             * @default
             */
            story_points: string;
            /**
             * Themes
             * @default
             */
            themes: string;
            /** Title */
            title: string;
            /**
             * Tone
             * @default
             */
            tone: string;
            /**
             * World Overview
             * @default
             */
            world_overview: string;
        };
        /** StrategyCapability */
        StrategyCapability: {
            /**
             * Default Eligible
             * @default false
             */
            default_eligible: boolean;
            /** Mechanically Qualified */
            mechanically_qualified: boolean;
            /**
             * Narrative Report
             * @default
             */
            narrative_report: string;
            /**
             * Narrative Report Sha256
             * @default
             */
            narrative_report_sha256: string;
            /**
             * Narrative Review
             * @enum {string}
             */
            narrative_review: "not_assessed" | "pass" | "fail";
            /**
             * Notes
             * @default
             */
            notes: string;
            /**
             * Strategy
             * @enum {string}
             */
            strategy: "legacy_delimited" | "legacy_json" | "typed_fill" | "flat_fill";
        };
        /** SuggestNamesRequest */
        SuggestNamesRequest: {
            /** Description */
            description: string;
            /**
             * Direction
             * @default
             */
            direction: string;
            /**
             * Suggest Arc
             * @default false
             */
            suggest_arc: boolean;
        };
        /** SystemCatalogRequest */
        SystemCatalogRequest: {
            /** Expected Fingerprint */
            expected_fingerprint: string;
            /** Rules */
            rules: components["schemas"]["SystemRule"][];
        };
        /** SystemRule */
        SystemRule: {
            /**
             * Character Effects
             * @default []
             */
            character_effects: components["schemas"]["CharacterEffect"][];
            /**
             * Conditions
             * @default []
             */
            conditions: components["schemas"]["StateCondition"][];
            /**
             * Cooldown Ticks
             * @default 0
             */
            cooldown_ticks: number;
            /**
             * Effects
             * @default []
             */
            effects: components["schemas"]["StateEffect"][];
            /**
             * Faction Effects
             * @default []
             */
            faction_effects: components["schemas"]["FactionEffect"][];
            /** Id */
            id: string;
            /** Occurrence Limit */
            occurrence_limit?: number | null;
            /**
             * Priority
             * @default 0
             */
            priority: number;
            /**
             * Trigger
             * @enum {string}
             */
            trigger: "tick" | "local_action" | "travel" | "enter_location" | "encounter";
        };
        /** TemplateRequest */
        TemplateRequest: {
            /**
             * Body
             * @default
             */
            body: string;
            /** Id */
            id?: string | null;
            /**
             * Keywords
             * @default []
             */
            keywords: string[];
            /** Title */
            title: string;
            /**
             * Type
             * @default normal
             */
            type: string;
        };
        /** TestModelRequest */
        TestModelRequest: {
            /** Model */
            model: string;
        };
        /** TextPart */
        TextPart: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "text";
            /** Text */
            text: string;
        };
        /**
         * TimeModel
         * @enum {string}
         */
        TimeModel: "none" | "turn" | "phase" | "day" | "authored_clock";
        /** TopologyDeleteRequest */
        TopologyDeleteRequest: {
            /** Expected Revision */
            expected_revision: number;
        };
        /** TopologyLocationRequest */
        TopologyLocationRequest: {
            /** Expected Revision */
            expected_revision: number;
            location: components["schemas"]["LocationNode"];
        };
        /** TopologyRouteRequest */
        TopologyRouteRequest: {
            /** Expected Revision */
            expected_revision: number;
            route: components["schemas"]["Route"];
        };
        /** TypedCommitResponse */
        TypedCommitResponse: {
            /** Draft Id */
            draft_id: string;
            /** Draft Revision */
            draft_revision: number;
            /** Passage Id */
            passage_id: string;
            /** Pending Facts */
            pending_facts: components["schemas"]["ContinuityProposal"][];
            /**
             * Status
             * @constant
             */
            status: "committed";
        };
        /** TypedDraftCommitRequest */
        TypedDraftCommitRequest: {
            /** Expected Draft Fingerprint */
            expected_draft_fingerprint: string;
            /**
             * Expected Parent Fingerprint
             * @default
             */
            expected_parent_fingerprint: string;
            /** Expected Plan Revision */
            expected_plan_revision: number;
        };
        /** TypedDraftCompileRequest */
        TypedDraftCompileRequest: {
            /** Expected Draft Fingerprint */
            expected_draft_fingerprint: string;
        };
        /** TypedDraftCompileResponse */
        TypedDraftCompileResponse: {
            artifact: components["schemas"]["CompileArtifact"];
            /** Draft Fingerprint */
            draft_fingerprint: string;
            /** Draft Id */
            draft_id: string;
            /** Draft Revision */
            draft_revision: number;
            /** Persisted Artifact Match */
            persisted_artifact_match: boolean;
        };
        /** TypedDraftEditRequest */
        TypedDraftEditRequest: {
            /** Expected Draft Fingerprint */
            expected_draft_fingerprint: string;
            fill: components["schemas"]["NarrativeFill"];
        };
        /** TypedDraftPlaytestJobResponse */
        TypedDraftPlaytestJobResponse: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Draft Fingerprint */
            draft_fingerprint: string;
            /** Draft Id */
            draft_id: string;
            /** Draft Revision */
            draft_revision: number;
            /**
             * Error Code
             * @default
             */
            error_code: string;
            /**
             * Error Message
             * @default
             */
            error_message: string;
            /** Job Id */
            job_id: string;
            result?: components["schemas"]["TypedDraftPlaytestResult"] | null;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "completed" | "failed";
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /** TypedDraftPlaytestRequest */
        TypedDraftPlaytestRequest: {
            /** Choice Slot Ids */
            choice_slot_ids?: string[] | null;
            /** Expected Draft Fingerprint */
            expected_draft_fingerprint: string;
            /** Initial State */
            initial_state?: {
                [key: string]: unknown;
            };
        };
        /** TypedDraftPlaytestResult */
        TypedDraftPlaytestResult: {
            /** Browser Load */
            browser_load: boolean;
            /** Choice Effect Execution */
            choice_effect_execution?: boolean | null;
            /** Choice Reachability */
            choice_reachability?: boolean | null;
            /** Continuity After Navigation */
            continuity_after_navigation?: boolean | null;
            /** Details */
            details?: string[];
            /** Form Binding */
            form_binding?: boolean | null;
            /** Hostile Text Safe */
            hostile_text_safe?: boolean | null;
            /** Passed */
            passed: boolean;
            /** Runtime Errors */
            runtime_errors?: string[];
            /** Runtime State Transaction */
            runtime_state_transaction?: boolean | null;
            /** Tweego Compile */
            tweego_compile: boolean;
        };
        /** TypedDraftRejectRequest */
        TypedDraftRejectRequest: {
            /** Expected Draft Fingerprint */
            expected_draft_fingerprint: string;
        };
        /** TypedDraftValidateRequest */
        TypedDraftValidateRequest: {
            /** Expected Draft Fingerprint */
            expected_draft_fingerprint: string;
        };
        /** TypedFactDecisionRequest */
        TypedFactDecisionRequest: {
            /**
             * Action
             * @enum {string}
             */
            action: "accept" | "reject";
        };
        /** TypedFactDecisionResponse */
        TypedFactDecisionResponse: {
            /** Key */
            key: string;
            /**
             * Status
             * @enum {string}
             */
            status: "accepted" | "rejected";
        };
        /** TypedGenerateRequest */
        TypedGenerateRequest: {
            /** Arc Name */
            arc_name: string;
            /** Author Task */
            author_task: string;
            /**
             * Branch Name
             * @default main
             */
            branch_name: string;
            context: components["schemas"]["ContextPack"];
            /**
             * Expected Plan Fingerprint
             * @default
             */
            expected_plan_fingerprint: string;
            /** Parent Choice Index */
            parent_choice_index?: number | null;
            /**
             * Parent Passage Id
             * @default
             */
            parent_passage_id: string;
            /** Passage Id */
            passage_id: string;
            plan?: components["schemas"]["PassagePlan"] | null;
            /**
             * Plan Id
             * @default
             */
            plan_id: string;
            /** Plan Revision */
            plan_revision?: number | null;
            /** Seed */
            seed?: number | null;
            /**
             * Strategy
             * @default typed_fill
             */
            strategy: string;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    spa__get: {
        parameters: {
            query?: {
                path?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_arcs_api_arcs_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    benchmark_runs_api_benchmarks_runs_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BenchmarkRunsResponse"];
                };
            };
        };
    };
    benchmark_run_api_benchmarks_runs__run_id__get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
            };
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BenchmarkRunDetailResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    benchmark_run_comparison_api_benchmarks_runs__run_id__comparison_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_capability_cards_api_capability_cards_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CapabilityCardsResponse"];
                };
            };
        };
    };
    get_characters_api_characters_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    create_character_api_characters_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NewCharacterRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_character_api_characters__char_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                char_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    save_character_api_characters__char_id__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                char_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveCharacterRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_character_endpoint_api_characters__char_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                char_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_character_keywords_api_characters__char_id__generate_keywords_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                char_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["GenerateKeywordsBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_character_keywords_endpoint_api_characters__char_id__keywords_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                char_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KeywordsBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    commit_api_commit_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CommitRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    compile_endpoint_api_compile_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    get_config_api_config_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    update_config_api_config_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    debug_calls_api_debug_calls_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    debug_calls_clear_api_debug_calls_clear_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    get_latest_typed_draft_api_drafts__draft_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DraftRecord"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_typed_draft_api_drafts__draft_id___revision__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DraftRecord"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    commit_typed_api_drafts__draft_id___revision__commit_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TypedDraftCommitRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TypedCommitResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    compile_typed_draft_api_drafts__draft_id___revision__compile_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TypedDraftCompileRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TypedDraftCompileResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_typed_draft_api_drafts__draft_id___revision__edit_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TypedDraftEditRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DraftRecord"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    decide_typed_fact_api_drafts__draft_id___revision__facts__fact_key__decision_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
                revision: number;
                fact_key: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TypedFactDecisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TypedFactDecisionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    playtest_typed_draft_api_drafts__draft_id___revision__playtest_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TypedDraftPlaytestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TypedDraftPlaytestJobResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reject_typed_draft_api_drafts__draft_id___revision__reject_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TypedDraftRejectRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DraftRecord"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    validate_typed_draft_api_drafts__draft_id___revision__validate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                draft_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TypedDraftValidateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DraftRecord"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_encounters_api_encounters_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    update_encounters_api_encounters_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EncounterCatalogRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_experience_profile_api_experience_profile_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    preview_experience_profile_api_experience_profile_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExperienceProfilePreviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_experience_profile_revision_api_experience_profile_revisions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExperienceProfileRevisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    extract_entities_endpoint_api_extract_entities_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExtractEntitiesRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    approve_fact_api_facts_approve_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FactApproval"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_api_generate_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenerateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_story_points_api_generate_story_points_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenerateStoryPointsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_generations_api_generations_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_generation_api_generations__gen_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                gen_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_graph_api_graph_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    init_story_api_init_story_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StoryInitRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    init_generate_characters_api_init_generate_characters_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenSketchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    init_generate_locations_api_init_generate_locations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenSketchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    init_generate_opening_api_init_generate_opening_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenOpeningRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    init_generate_premise_api_init_generate_premise_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenPremiseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    init_generate_tone_themes_api_init_generate_tone_themes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenToneThemesRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    init_generate_world_api_init_generate_world_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenWorldRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    inspiration_summarize_api_inspiration_summarize_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InspirationSummaryRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_lore_api_lore_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    create_lore_api_lore_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NewLoreRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_lore_entry_api_lore__category___lore_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                category: string;
                lore_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    save_lore_entry_api_lore__category___lore_id__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                category: string;
                lore_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveLoreRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_lore_keywords_api_lore__category___lore_id__generate_keywords_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                category: string;
                lore_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["GenerateKeywordsBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_lore_keywords_endpoint_api_lore__category___lore_id__keywords_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                category: string;
                lore_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KeywordsBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    manifest_rebuild_api_manifest_rebuild_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    manifest_sync_api_manifest_sync_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    media_files_api_media_files_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    import_media_api_media_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ImportMediaRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_slots_api_media_slots_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    search_media_slots_api_media_slots_search_get: {
        parameters: {
            query?: {
                q?: string;
                status?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_media_slot_api_media_slots__slot_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slot_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_slot_meta_api_media_slots__slot_id__meta_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slot_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SlotMetaRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_media_slot_api_media_slots__slot_id__preview_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slot_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_api_media_slots__slot_id__resolve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slot_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResolveSlotRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    unresolve_api_media_slots__slot_id__unresolve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                slot_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["SlotMutationGuard"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_notes_api_notes_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    create_note_api_notes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NewNoteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_note_api_notes__note_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                note_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    save_note_endpoint_api_notes__note_id__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                note_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveNoteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_note_endpoint_api_notes__note_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                note_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_model_api_ollama_delete_model_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeleteModelRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_unresponsive_api_ollama_delete_unresponsive_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    get_scores_api_ollama_scores_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    ollama_status_api_ollama_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    test_model_api_ollama_test_model_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TestModelRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_passage_types_api_passage_types_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    get_passage_api_passage__passage_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_passage_endpoint_api_passage__passage_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_passage_delta_api_passage__passage_id__delta_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_summary_for_passage_api_passage__passage_id__generate_summary_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_threads_for_passage_api_passage__passage_id__generate_threads_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_passage_media_api_passage__passage_id__media__slot_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
                slot_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_passage_metadata_api_passage__passage_id__metadata_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PassageMetadataUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_reconstructed_snapshot_api_passage__passage_id__snapshot_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    suggest_characters_for_passage_api_passage__passage_id__suggest_characters_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    suggest_choices_for_passage_api_passage__passage_id__suggest_choices_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    suggest_state_for_passage_api_passage__passage_id__suggest_state_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_passage_beats_api_passages__passage_id__beats_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                passage_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PassageBeatsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_plan_api_plan_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    edit_acts_api_plan_acts_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ActsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_arc_endpoint_api_plan_arcs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateArcRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_arc_plan_api_plan_arcs__arc_name__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                arc_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ArcPlanRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_scenes_api_plan_arcs__arc_name__generate_scenes_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                arc_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenerateScenesRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_scene_api_plan_arcs__arc_name__scenes_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                arc_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SceneRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_scene_api_plan_arcs__arc_name__scenes__scene_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                arc_name: string;
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SceneUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_scene_api_plan_arcs__arc_name__scenes__scene_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                arc_name: string;
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanDeleteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_beat_api_plan_beats_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BeatRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_beat_api_plan_beats__beat_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                beat_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BeatUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    remove_beat_api_plan_beats__beat_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                beat_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanDeleteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_plan_arcs_api_plan_generate_arcs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenItemsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    generate_plan_beats_api_plan_generate_beats_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GenItemsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_points_api_plan_import_points_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ImportPointsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_open_questions_api_plan_open_questions_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OpenQuestionsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_passage_plan_api_plans_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PassagePlanCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PassagePlanRecordResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revise_passage_plan_api_plans__plan_id__revisions_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PassagePlanRevisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PassagePlanRecordResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_passage_plan_api_plans__plan_id__revisions__revision__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PassagePlanRecordResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    approve_passage_plan_api_plans__plan_id__revisions__revision__approve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                plan_id: string;
                revision: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PassagePlanApprovalRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PassagePlanRecordResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_typed_draft_playtest_api_playtests__job_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TypedDraftPlaytestJobResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_premise_api_premise_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    save_premise_api_premise_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SavePremiseRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    project_status_api_project_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    rag_delete_file_api_rag_file_delete: {
        parameters: {
            query: {
                path: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rag_reindex_api_rag_reindex_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    rag_status_api_rag_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    rag_upload_api_rag_upload_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RagUploadRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    scene_keywords_api_scene_keywords_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SceneKeywordsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_session_api_session_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    update_session_api_session_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_simulation_fixtures_api_simulation_fixtures_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    update_simulation_fixtures_api_simulation_fixtures_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationFixtureCatalogRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_simulation_api_simulations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_simulation_api_simulations__simulation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    apply_simulation_action_api_simulations__simulation_id__actions_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                simulation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SimulationActionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    story_index_reindex_api_story_index_reindex_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    story_index_status_api_story_index_status_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    suggest_names_api_suggest_names_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SuggestNamesRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_systems_api_systems_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    update_systems_api_systems_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SystemCatalogRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_templates_api_templates_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    create_template_api_templates_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_template_api_templates__template_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                template_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TemplateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_template_api_templates__template_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                template_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_topology_api_topology_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    add_topology_location_api_topology_locations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TopologyLocationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_topology_location_api_topology_locations__location_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                location_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TopologyLocationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_topology_location_api_topology_locations__location_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                location_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TopologyDeleteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    add_topology_route_api_topology_routes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TopologyRouteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_topology_route_api_topology_routes__route_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                route_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TopologyRouteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_topology_route_api_topology_routes__route_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                route_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TopologyDeleteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    tweego_find_api_tweego_find_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    generate_typed_api_typed_generate_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TypedGenerateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DraftRecord"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    validate_api_validate_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    legacy_spa_legacy_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": string;
                };
            };
        };
    };
    next_spa_next_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": string;
                };
            };
        };
    };
    spa__path__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                path: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/html": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
