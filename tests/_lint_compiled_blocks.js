// Compiled-story HTML linter — independent JS (acorn) + CSS (css-tree) check.
//
// Invoked by tests/test_compiled_html_lint.py.  Reads block bodies from a
// manifest JSON file written by the Python test (which extracts
// <script>/<style> blocks with a real HTML parser — a regex-based extractor
// would mis-tokenise regex literals containing <script|<style substrings in
// the minified SugarCube/jQuery engine bundles, producing false positives).
//
// Usage:  node _lint_compiled_blocks.js <node_modules_dir> <manifest.json>
//
// manifest.json schema:
//   { "scripts": [{"id": "...", "body": "..."}, ...],
//     "styles":  [{"id": "...", "body": "..."}, ...] }
//
// Prints a JSON report to stdout:
//   { "scripts_checked": N, "styles_checked": N,
//     "js_errors":    [{"id","message","line","col"} ...],
//     "css_errors":   [{"id","message"} ...],
//     "css_warnings": [{"id","kind","selector","message"} ...] }
//
//   * js_errors    — acorn parse failures (genuine JS syntax errors).
//     The VS-Code/tsserver false positives on regex literals in the minified
//     engine bundles do NOT appear here: acorn tokenises regex literals
//     correctly.
//   * css_errors    — css-tree parse failures (malformed CSS).
//   * css_warnings  — the two VS-Code CSS-linter warning classes that
//     SugarCube's bundled CSS produces:
//       - vendor_prefix:    -webkit-appearance:X without standard appearance:X
//         (selectors containing ::-webkit- are skipped, mirroring VS Code).
//       - unknown_property: speak (a valid CSS2 aural property VS Code's
//         linter does not recognise, common in fontello icon-font rules).
'use strict';
var fs = require('fs');
var path = require('path');

var nodeModulesDir = process.argv[2];
var manifestPath = process.argv[3];

var acorn = require(path.join(nodeModulesDir, 'acorn'));
var css = require(path.join(nodeModulesDir, 'css-tree'));

var manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));

// ── JS: parse each non-empty <script> body with acorn ────────────────────────
var jsErrors = [];
var scriptsChecked = 0;
manifest.scripts.forEach(function (block) {
  var body = block.body;
  if (!body || !body.trim()) return;
  scriptsChecked++;
  try {
    acorn.parse(body, { ecmaVersion: 2022 });
  } catch (e) {
    jsErrors.push({
      id: block.id || '(script)',
      message: e.message,
      line: e.loc ? e.loc.line : null,
      col: e.loc ? e.loc.column : null,
    });
  }
});

// ── CSS: parse + lint each non-empty <style> body with css-tree ───────────────
var cssErrors = [];
var cssWarnings = [];
var stylesChecked = 0;
manifest.styles.forEach(function (block) {
  var body = block.body;
  if (!body || !body.trim()) return;
  stylesChecked++;
  var label = block.id || '(style)';
  var ast;
  try {
    ast = css.parse(body);
  } catch (e) {
    cssErrors.push({ id: label, message: 'CSS parse error: ' + e.message });
    return;
  }
  css.walk(ast, {
    visit: 'Rule',
    enter: function (node) {
      var decls = [];
      node.block.children.forEach(function (c) {
        if (c.type === 'Declaration') decls.push(c);
      });
      var propSet = {};
      decls.forEach(function (d) { propSet[d.property] = true; });
      var sel = '';
      try { sel = css.generate(node.prelude); } catch (e) {}
      var isWebkitPseudo = sel.indexOf('::-webkit-') !== -1;
      decls.forEach(function (d) {
        // unknown property: speak (valid CSS2 aural; VS Code linter flags it)
        if (d.property === 'speak') {
          cssWarnings.push({
            id: label, kind: 'unknown_property', selector: sel.slice(0, 70),
            message: "speak property is not recognised (unknown property)",
          });
        }
        // vendorPrefix: -webkit-appearance without standard appearance
        if (d.property === '-webkit-appearance' && !isWebkitPseudo && !propSet['appearance']) {
          var val = '';
          try { val = css.generate(d.value).trim(); } catch (e) {}
          cssWarnings.push({
            id: label, kind: 'vendor_prefix', selector: sel.slice(0, 70),
            message: '-webkit-appearance:' + val + ' used without standard appearance:' + val,
          });
        }
      });
    },
  });
});

console.log(JSON.stringify({
  scripts_checked: scriptsChecked,
  styles_checked: stylesChecked,
  js_errors: jsErrors,
  css_errors: cssErrors,
  css_warnings: cssWarnings,
}));
