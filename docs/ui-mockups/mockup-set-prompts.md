# Extended Storyweaver Mockup Prompts

- **Generation method:** Built-in image generation
- **Use case:** `ui-mockup`
- **Shared visual reference:** `greenfield-authoring-workspace.png`
- **Output dimensions:** 1536 × 1024 each

The shared image was supplied as a visual-system and application-shell reference
for every generation below.

## Story map

```text
Use case: ui-mockup
Asset type: high-fidelity desktop screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; create a different screen while preserving its navigation, typography, colors, spacing, icon treatment, and polished implementable quality.
Primary request: Create the complete "Story" workspace for the project "The Cartographer's Dilemma".
Composition: 16:10 full desktop viewport. Preserve the narrow left navigation with Story selected. Top bar includes project breadcrumb, search, filters, and a primary "New passage" button. The central area is a large branching story graph organized into three softly labeled vertical arc regions: "Act I · Arrival", "Act II · The Accord", "Act III · Fracture". Show 14 clean connected passage nodes with readable labels, including "Arrival", "Mira's Offer", "The Glass Accord", "Cross-examination", "Accord Signed", and "City in Fracture". Use different small status marks for committed, draft, warning, ending, and unresolved. Highlight "The Glass Accord" with a coral border.
Right inspector: heading "The Glass Accord"; status "Draft 3 · Valid"; compact summary; Parents: "Mira's Offer"; Children: "Accord Signed", "Cross-examination"; passage type "Normal"; state reads "trust_mira"; state writes "treaty_signed"; buttons "Open in Write" and "Validate path".
Bottom-left graph controls: zoom, fit, layout. Also show a clear toggle "Graph | Outline" for accessible alternative navigation.
Style: same restrained deep navy shell, slate panels, warm neutral node cards, teal valid, amber warning, coral selection. Crisp modern SaaS UI with practical density and generous space.
Constraints: no decorative fantasy art, no gradients, no glassmorphism, no browser frame, no people, no tiny unreadable labels, no watermark. Render specified labels verbatim and avoid adding marketing copy.
```

## New passage plan

```text
Use case: ui-mockup
Asset type: high-fidelity desktop screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; create a different screen while preserving its navigation, typography, colors, spacing, icon treatment, and polished implementable quality.
Primary request: Create the "New passage" planning screen shown before model generation.
Composition: 16:10 full desktop viewport with Write selected in the left navigation. Top breadcrumb: "The Cartographer's Dilemma > Act II: The Accord > New passage". Main content is a calm two-column setup workflow.
Left main column heading "Plan the next passage". Step indicator across top: "1 Intent", "2 Structure", "3 Review" with Review active. Show a compact direction field containing: "Mira reveals the treaty's hidden cost and forces an immediate decision." Below, a read-only plan review with sections "Narrative slots" containing "Opening paragraph", "Mira Vale · dialogue", "Player · thought"; "Choice slots" containing "Sign the accord" and "Challenge the witness"; "Mechanics" containing a guard card "trust_mira ≥ 2" and effect cards "treaty_signed → true", "trust_mira +1"; "Destinations" showing "Accord Signed" and "Cross-examination".
Right panel heading "Generation setup": Parent "Mira's Offer"; Passage type "Normal"; Strategy "Typed fill"; Model "Qwen 3"; Context summary with green checks for Premise, Parent snapshot, Mira Vale, Accord of Glass; compact token estimate. Buttons "Back", "Save plan", and prominent "Generate draft".
Include a small authority note: "The model writes prose and choice copy. The harness owns mechanics and links."
Style: same deep navy shell and slate inspector, warm parchment content cards, teal validation, amber open question, coral primary action. Practical, polished, accessible.
Constraints: no chat bubbles, no raw JSON, no SugarCube code, no decorative fantasy art, no gradients, no glassmorphism, no browser frame, no people, no watermark. Render labels verbatim.
```

## Passage mechanics

```text
Use case: ui-mockup
Asset type: high-fidelity desktop screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; create a different screen while preserving its navigation, typography, colors, spacing, icon treatment, and polished implementable quality.
Primary request: Create the detailed "Mechanics" tab for passage "The Glass Accord".
Composition: 16:10 full desktop viewport. Preserve Write selection, breadcrumb, title, Draft 3 · Valid chip, and tabs Write, Choices, Mechanics, Preview with Mechanics active.
Main workbench heading "Passage mechanics". Show structured, human-readable sections: "Passage mode" with Normal selected; "Entry requirements" card showing "trust_mira is at least 2"; "On enter" card showing "No state changes"; "Choices" with two expanded mechanic cards.
Choice 1: "Sign the accord" destination "Accord Signed", guard "trust_mira ≥ 2", effects "treaty_signed → true" and "trust_mira +1".
Choice 2: "Challenge the witness" destination "Cross-examination", guard "Always available", effect "No state changes".
Use lock icons and labels "Fixed by plan" beside destinations and state targets, with an "Edit plan" secondary action—not direct arbitrary code editing.
Right review inspector: Mechanics stage selected in the validation pipeline. Show "3 components resolved", "State transaction exact", "No unauthorized targets", and an expandable "Generated SugarCube" advanced section. Buttons "Validate mechanics", "Save revision", "Commit passage".
Bottom local story path strip remains visible with current node and two destinations.
Style: match reference exactly in shell, restrained editorial palette, typography, spacing, border radii, and status colors.
Constraints: no raw JSON, no code editor as primary content, no decorative fantasy art, no gradients, no glassmorphism, no browser frame, no people, no tiny labels, no watermark. Render specified labels verbatim.
```

## Preview and playtest

```text
Use case: ui-mockup
Asset type: high-fidelity desktop screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; create a different screen while preserving its navigation, typography, colors, spacing, icon treatment, and polished implementable quality.
Primary request: Create the "Preview" tab for passage "The Glass Accord", combining playable preview and runtime diagnostics.
Composition: 16:10 full desktop viewport. Preserve Write selection, breadcrumb, title, Draft 3 · Valid chip, and tabs Write, Choices, Mechanics, Preview with Preview active.
Main left area: a framed playable passage preview on a warm reading surface titled "The Glass Accord", polished prose and Mira Vale dialogue, then two choice buttons "Sign the accord" and "Challenge the witness". Above preview include controls "Desktop", "Tablet", "Restart", and state fixture dropdown "trust_mira = 3". A compact banner says "Isolated preview · changes are not saved".
Right review inspector: Playtest stage selected. Sections "Runtime checks" with green results "Passage loaded", "2 choices reachable", "No JavaScript errors"; "Choice trace" showing selected "Sign the accord" then destination "Accord Signed"; "Observed state" with before/after values treaty_signed false → true and trust_mira 3 → 4. Include secondary actions "Test other choice" and "Open trace", primary "Commit passage".
Bottom drawer titled "Diagnostics" with tabs Console, Network, State, Source and a short timeline of Load passage, Render choices, Click choice 1, Apply effects, Navigate.
Style: same deep navy shell, warm parchment preview, slate diagnostics, teal valid, amber informational, coral action.
Constraints: practical shippable UI, no fantasy illustration, no gradients, no glassmorphism, no browser frame, no people, no raw code dominating the screen, no watermark. Render labels verbatim.
```

## World continuity

```text
Use case: ui-mockup
Asset type: high-fidelity desktop screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; create a different screen while preserving its navigation, typography, colors, spacing, icon treatment, and polished implementable quality.
Primary request: Create the "World" continuity workspace focused on character Mira Vale.
Composition: 16:10 full desktop viewport with World selected. Top bar breadcrumb "The Cartographer's Dilemma > World", global search, button "New entity".
Three-column master-detail layout. Left column titled "World" with search and grouped navigation: Characters, Locations, Factions, Lore, State. Characters expanded with Mira Vale selected, plus Ilyan Voss and Captain Sera.
Center warm editor panel heading "Mira Vale" with chips Character and Canonical. Sections "Overview", "Motivation", "Voice", "Relationships", each containing concise readable content. Show an editable canonical fact list: "Witness to the Accord of Glass", "Distrusts the Council", "Owes the player one favor". Button "Save changes".
Right continuity inspector: "Story presence" timeline listing Arrival, Mira's Offer, The Glass Accord; "Snapshot at The Glass Accord" with status alive, wary and knows "The player found the hidden clause"; "Proposed facts" card with amber status containing "Mira secretly funded the smugglers" and buttons "Accept" and "Reject"; "Conflicts" showing "No conflicts".
Include a top context selector "At passage: The Glass Accord".
Style: same deep navy shell, slate side panels, warm parchment content, modern sans UI and literary serif only for prose notes, teal canonical/valid, amber proposals, coral selection.
Constraints: no decorative character portrait, no fantasy art, no gradients, no glassmorphism, no browser frame, no people, no tiny text, no watermark. Render specified labels verbatim.
```

## Benchmark comparison

```text
Use case: ui-mockup
Asset type: high-fidelity desktop screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; create a different screen while preserving its navigation, typography, colors, spacing, icon treatment, and polished implementable quality.
Primary request: Create the "Tests" workspace showing a matched architecture benchmark comparison.
Composition: 16:10 full desktop viewport with Tests selected. Top heading "Architecture comparison". Run selector "refactor-core · 5 seeds · Aug 13" and fingerprint status "Comparable". Controls for Models "4", Cases "24", Seeds "42–46", button "Run canary".
Main upper area contains three architecture summary columns: "Legacy JSON", "Typed fill", "Flat fill". Each shows request-level stage funnel with exact labels Requests, Normalized, Valid drafts, Compiled, Browser playable, Exact state. Use plausible counts out of 480 and make Typed fill clearly strongest without perfection. Example: Legacy playable 286/480, Typed playable 421/480, Flat playable 398/480. Show p95 latency and repair rate beneath.
Middle area heading "Stage comparison" with grouped horizontal bars for Plan adherence, Semantic correctness, Compile success, Runtime state transaction. Keep counts and percentages readable.
Bottom table heading "Regressions and gains" with rows R3-FORM-COPY, R3-LOOP-COPY, R6-UNICODE-HOSTILE, R9-LONG-DIALOGUE and columns Legacy JSON, Typed fill, Flat fill, Delta, Notes. Use green gains and one amber regression.
Right inspector heading "Run provenance": model digest, schema hash, compiler v1, seed policy 42 + run index, request denominator 480; green checks "Same plans", "Same seeds", "Same budgets". Buttons "Open full report" and "Export artifacts".
Style: same deep navy/slate shell, dense but readable analytics, teal gains, amber warnings, coral selected architecture, no gratuitous charts.
Constraints: never hide failed requests, do not use a single overall score, no gradients, no glassmorphism, no browser frame, no people, no decorative art, no tiny unreadable text, no watermark. Render specified labels verbatim.
```

## Media library

```text
Use case: ui-mockup
Asset type: high-fidelity desktop screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; create a different screen while preserving its navigation, typography, colors, spacing, icon treatment, and polished implementable quality.
Primary request: Create the "Media" workspace for proposing and resolving story media slots.
Composition: 16:10 full desktop viewport with Media selected. Top heading "Media library", search, filters "All types", "All status", primary button "Import files".
Left main area uses a practical table/gallery hybrid with rows for media slots. Columns Preview, Slot, Passage, Type, Keywords, Status. Include: slot_glass_accord for The Glass Accord, image, keywords crystal tablet treaty, status Pending; slot_station_rain for Arrival, ambient audio, status Resolved; slot_mira_theme for Mira's Offer, music, status Missing; slot_archive_door for Whispers in the Archives, image, status Resolved. Use simple neutral thumbnails/icons, not fantasy artwork.
Right inspector for selected slot_glass_accord: heading "Crystal treaty tablet"; chip Pending; read-only source "The Glass Accord"; type dropdown Image; description; keyword chips crystal, tablet, treaty, etched; accessibility field "Alt text" containing "A thin crystal tablet etched with trade routes."; section "Resolve with local file" showing a drop zone and button "Choose file"; below "Suggested matches" with three local filename rows and Match buttons; actions "Save metadata" and prominent "Resolve slot".
Bottom status summary: 12 total, 7 resolved, 3 pending, 2 missing; note "Media files remain local."
Style: same deep navy shell, slate panels, warm neutral list rows, teal resolved, amber pending, coral primary action, accessible practical layout.
Constraints: no generated imagery in thumbnails beyond neutral placeholders, no gradients, no glassmorphism, no browser frame, no people, no watermark. Render specified labels verbatim.
```

## Commit transaction review

```text
Use case: ui-mockup
Asset type: high-fidelity desktop modal-state screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; preserve its navigation, typography, colors, spacing, icon treatment, and implementable quality.
Primary request: Create the final "Commit passage" transaction review for draft "The Glass Accord", shown over the Write workspace.
Composition: 16:10 full desktop viewport. The underlying authoring workspace remains visible but subdued. Center a large accessible modal titled "Commit passage" with subtitle "Draft 3 · Plan revision 1". Do not make it a tiny confirmation.
Modal content uses two columns. Left: "Passage" with ID act2__glass_accord, Parent Mira's Offer, Type Normal; "Links" showing Sign the accord → Accord Signed and Challenge the witness → Cross-examination; "State transaction" showing reads trust_mira and writes treaty_signed → true, trust_mira +1. Right: "Files to update" showing arcs/02_the_accord/03_glass_accord.tw, story.json, media/_slots.json; "Validation" with green checks Plan, Narrative, Mechanics, Compile, Playtest; "Pending after commit" showing 1 proposed fact and 1 media slot, with note "These require separate approval."
Bottom warning note: "This commits exactly Draft 3. Later edits create a new revision." Include checkbox "Open committed passage" selected. Buttons "Cancel", "Save revision only", and prominent "Commit Draft 3".
Style: same deep navy/slate shell, warm modal content, teal checks, amber pending, coral commit action, clear hierarchy.
Constraints: practical, accessible modal, no vague yes/no confirmation, no gradients, no glassmorphism, no browser frame, no people, no watermark. Render specified labels verbatim.
```

## Stale draft conflict

```text
Use case: ui-mockup
Asset type: high-fidelity desktop conflict-recovery screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; preserve its navigation, typography, colors, spacing, icon treatment, and implementable quality.
Primary request: Create a stale draft revision conflict state in the Write workspace for "The Glass Accord".
Composition: 16:10 full desktop viewport with Write selected. Top status chip amber "Draft 3 · Stale". Main warm workbench shows a comparison heading "This draft needs attention" and explanation "Mira's Offer changed after Draft 3 was generated." Use a clear side-by-side comparison.
Left column "Draft context" shows Parent revision 5, parent summary excerpt, plan revision 1, generated 18 min ago.
Right column "Current project" shows Parent revision 6, changed summary excerpt with a highlighted added sentence "Mira now knows the Council forged the seal.", and a compact affected-items list: Narrative context, Continuity check, Playtest.
Below, section "Choose how to continue" with three large actions: recommended "Rebase and revalidate" explaining preserve edits and rebuild context; "Regenerate draft" explaining create a new fill from current context; "Keep as historical revision" explaining no commit. Secondary link "View full parent diff".
Right inspector shows review pipeline Plan passed, Narrative stale, Mechanics passed, Compile stale, Playtest stale. Commit button disabled with reason "Resolve stale context before commit."
Include revision history rail with Draft 1, Draft 2, Draft 3 selected.
Style: same navy shell, warm editor, amber stale state, teal unaffected stages, coral only for selection, practical diff highlighting.
Constraints: never suggest overwriting current parent, no destructive default, no raw JSON, no gradients, no glassmorphism, no browser frame, no people, no watermark. Render labels verbatim.
```

## Models and generation settings

```text
Use case: ui-mockup
Asset type: high-fidelity desktop settings screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; create a settings screen while preserving its navigation, typography, colors, spacing, icon treatment, and implementable quality.
Primary request: Create "Models & generation" settings focused on local Ollama models and measured capability routing.
Composition: 16:10 full desktop viewport. Left app navigation remains; settings gear selected at bottom. Secondary settings navigation column with Project, Models & generation selected, Compiler, Appearance, Storage, Advanced.
Main heading "Models & generation" with status "Ollama connected" and button "Refresh models". Section "Default strategy" with radio-style options Typed fill recommended, Flat fill, Legacy JSON compatibility. Explain selected default applies only to validated model profiles.
Section "Installed models" as a readable list/table. Rows: qwen3:14b selected and Ready; mistral-small:24b Ready; gemma3:12b Needs benchmark. Columns Model, Digest, Context, Capability profile, Last tested. Each row has Test action.
Right inspector for qwen3:14b titled "Capability profile". Fingerprint details digest, template hash, Ollama version. Capability bars/checks: Typed schema 96%, Plan adherence 93%, Exact state 91%, Dialogue 88%, Long context 72%. Recommended route "Typed fill"; fallback "Legacy JSON". Button "Run refactor-canary".
Bottom section "Generation limits": Temperature 0.2, Max output tokens 640, Timeout 120 seconds, Seed policy Fixed for benchmarks / Random for authoring. Include warning note that changing digest, template, or runtime invalidates capability results. Buttons "Discard changes" and "Save settings".
Style: same deep navy/slate shell, warm neutral settings content, teal ready, amber needs benchmark, coral primary action, accessible form layout.
Constraints: no cloud-service upsell, no API keys, no gradients, no glassmorphism, no browser frame, no people, no tiny text, no watermark. Render specified labels verbatim.
```

The initial settings generation incorrectly showed both Write and Settings as
selected. The final saved image was corrected with this targeted edit:

```text
Use case: precise-object-edit
Asset type: correction to the Storyweaver Models & generation settings UI mockup
Primary request: Change only the left application navigation selection state. Remove the blue selected background and coral selection rail from "Write" so it appears like the other inactive Story, World, Media, and Tests items. Keep "Settings" as the one and only selected navigation item with its existing blue selected background and coral selection rail.
Invariants: preserve every other pixel-level design decision, all text, layout, settings content, model table, capability profile, colors, spacing, typography, and 1536×1024 framing. Do not alter any other UI element. No added text, no watermark.
```

## Sandbox workspace

```text
Use case: ui-mockup
Asset type: high-fidelity desktop screen for the Storyweaver interactive-fiction authoring application
Input images: Image 1 is the visual-system and application-shell reference only; create a new Sandbox workspace while preserving its navigation, typography, colors, spacing, icon treatment, and polished implementable quality.
Primary request: Create a first-class sandbox authoring and simulation workspace for project "The Cartographer's Dilemma", configured as "Sandbox".
Composition: 16:10 full desktop viewport. Left navigation keeps Story selected. Top breadcrumb "The Cartographer's Dilemma > Sandbox", mode selector chip "Sandbox", world clock "Day 12 · Dusk", and primary button "Create opportunity".
Main left-center area is a navigable location topology map, not a linear story arc. Show six connected district/location cards arranged spatially: Harbor Ward selected, Glass Market, Council Heights, Old Archives, Smuggler's Quay, North Gate. Use small badges for current player location, active opportunity count, faction control, and unresolved danger. Connections are roads/routes, with no start-to-ending progression.
Below the map, a horizontal "Active systems" strip with compact cards: Time Dusk → Night, Council influence 62, Smuggler heat 38, Supplies 7, Weather Rain.
Main lower panel heading "Available opportunities" with three reusable/emergent cards: "A courier needs discreet passage" tagged Player initiated and Expires at Night; "Council patrol searches the market" tagged World event; "Mira Vale requests a private meeting" tagged Character agenda. Each shows location, prerequisites, possible consequences, and button "Open encounter".
Right inspector for Harbor Ward: heading "Harbor Ward"; tags Location, Revisit-safe; description; "Available actions" list Travel to Glass Market, Ask for rumors, Rest until night, Inspect the docks; "Local state" Dockworkers wary, Patrol presence low, Visited 4 times; "Encounter table" 3 eligible of 8; buttons "Simulate 10 turns" and "Open location".
Include toggle near map "Topology | Visit history | Systems".
Style: same restrained deep navy shell, slate panels, warm neutral location/opportunity cards, teal active/valid, amber danger/time, coral current selection. Practical simulation-authoring UI, not a quest-log clone.
Constraints: emphasize player agency, reusable locations, systemic state, cycles, and emergent opportunities. No linear act lanes, no ending funnel, no decorative fantasy art, no gradients, no glassmorphism, no browser frame, no people, no watermark. Render specified labels verbatim.
```
