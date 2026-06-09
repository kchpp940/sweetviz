const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const args = process.argv.slice(2);
if (args.length < 2) {
    console.error(JSON.stringify({ error: 'Usage: node test_cat_fold_interactive.js <html_path> <widescreen|vertical>' }));
    process.exit(1);
}

const [htmlPath, layout] = args;
if (!fs.existsSync(htmlPath)) {
    console.error(JSON.stringify({ error: `HTML not found: ${htmlPath}` }));
    process.exit(1);
}

let rawHtml = fs.readFileSync(htmlPath, 'utf-8');

// Inject jQuery stubs for layout-dependent methods (position/outerHeight) right after jQuery loads
// This ensures sweetviz JS sees real values when computing heights.
const jqueryStubCode = `
<script>
(function() {
    // Stub jQuery layout methods that jsdom cannot compute
    var origReady = window.jQuery ? window.jQuery.fn.ready : null;
    function applyStubs() {
        if (!window.jQuery) return false;
        var $ = window.jQuery;

        // Track which features are expanded (full rows rendered) so outerHeight can vary
        window.__sv_stub_state = { expandedF: {} };

        $.fn.position = function() {
            var el = this[0];
            if (!el) return { top: 0, left: 0 };
            var id = el.id || '';
            // Put breakdown and assoc at reasonable vertical offsets
            if (id.indexOf('detail_breakdown') === 0) return { top: 200, left: 0 };
            if (id.indexOf('cat-assoc-window') === 0) return { top: 700, left: 0 };
            return { top: 0, left: 0 };
        };

        $.fn.outerHeight = function(includeMargin) {
            var el = this[0];
            if (!el) return 0;
            var id = el.id || '';
            if (id.indexOf('detail_breakdown') === 0) {
                var prefix = 'detail_breakdown-';
                var fkey = id.substring(prefix.length);
                if (fkey && window.__sv_stub_state.expandedF[fkey]) {
                    return 1800;
                }
                return 500;
            }
            if (id.indexOf('cat-assoc-window') === 0) return 200;
            return 0;
        };
        return true;
    }
    // Try now and also after a small delay
    if (!applyStubs()) setTimeout(applyStubs, 50);
})();
</script>
`;

// Insert stub right before </head> so it runs after jQuery but before sweetviz.js
if (rawHtml.indexOf('</head>') !== -1) {
    rawHtml = rawHtml.replace('</head>', jqueryStubCode + '</head>');
} else if (rawHtml.indexOf('<head>') !== -1) {
    rawHtml = rawHtml.replace('<head>', '<head>' + jqueryStubCode);
}

const dom = new JSDOM(rawHtml, {
    runScripts: 'dangerously',
    resources: 'usable',
    pretendToBeVisual: true,
});

const { window } = dom;
const { document } = window;

function result(steps) {
    console.log(JSON.stringify({ layout, steps }, null, 2));
    process.exit(0);
}

setTimeout(() => {
    try {
        const $ = window.$;
        if (typeof $ === 'undefined') {
            result([{ name: 'jQuery_load', ok: false, error: 'jQuery not defined' }]);
            return;
        }
        if (typeof window.__sv_stub_state === 'undefined') {
            result([{ name: 'stub_injection', ok: false, error: 'jQuery stubs not injected' }]);
            return;
        }

        // Find the categorical feature with most categories
        const allCatData = document.querySelectorAll('script[id^="cat-data-f"]');
        let targetIdx = null;
        let maxCats = 0;
        allCatData.forEach(el => {
            const idx = el.id.substring('cat-data-f'.length);
            const data = JSON.parse(el.textContent);
            const catCount = data.filter(r => !r.is_total).length;
            if (catCount > maxCats) {
                maxCats = catCount;
                targetIdx = idx;
            }
        });

        if (!targetIdx) {
            result([{ name: 'find_feature', ok: false, error: 'No categorical feature found' }]);
            return;
        }
        const fKey = targetIdx === '-1' ? 'f-1' : 'f' + targetIdx;

        const folded = document.getElementById('cat-folded-' + fKey);
        const full = document.getElementById('cat-full-' + fKey);
        const btn = document.getElementById('cat-toggle-btn-' + fKey);
        const detail = document.getElementById('detail-' + fKey);

        if (!folded || !full || !btn) {
            result([{ name: 'dom_elements', ok: false, error: 'Missing folded/full/btn elements for ' + fKey,
                      ids: { folded: !!folded, full: !!full, btn: !!btn } }]);
            return;
        }

        const steps = [];
        const initialFoldedRows = folded.querySelectorAll('.breakdown-row').length;

        // ---- Widescreen: need to show detail first ----
        if (layout === 'widescreen' && detail) {
            detail.style.display = 'block';
            detail.classList.remove('isHidden');
        }

        // ---- Vertical: click selector to expand detail ----
        let summaryEl = null;
        let posContainer = null;
        if (layout === 'vertical') {
            summaryEl = document.getElementById('summary-' + fKey);
            if (!summaryEl && fKey === 'f-1') summaryEl = document.getElementById('summary-target');
            posContainer = summaryEl ? summaryEl.parentElement : null;
            if (summaryEl) {
                $(summaryEl.querySelector('.selector')).trigger('click');
                steps.push({
                    name: 'vertical_expand_detail',
                    ok: !!posContainer && $(posContainer).data('expanded') === 'true',
                    pos_height: posContainer ? posContainer.style.height : null,
                });
            }
        }

        // ---- STEP 1: Initial state ----
        steps.push({
            name: 'initial_state',
            ok: (
                full.innerHTML.trim() === '' &&
                !full.dataset.built &&
                full.classList.contains('isHidden') &&
                btn.textContent.trim() === '显示全部类别' &&
                (folded.style.display !== 'none' && !folded.classList.contains('isHidden')) &&
                initialFoldedRows > 0 &&
                folded.textContent.includes('(Other)')
            ),
            folded_visible: folded.style.display !== 'none' && !folded.classList.contains('isHidden'),
            folded_rows: initialFoldedRows,
            folded_has_other: folded.textContent.includes('(Other)'),
            full_empty: full.innerHTML.trim() === '',
            full_built: !!full.dataset.built,
            full_hidden: full.classList.contains('isHidden'),
            btn_text: btn.textContent.trim(),
        });

        // ---- STEP 2: Click expand ----
        // Mark this feature as expanded in our stub BEFORE clicking
        // (the click handler will build the DOM, and our outerHeight stub needs to know)
        window.__sv_stub_state.expandedF[fKey] = true;

        const heightBeforeExpand = (layout === 'vertical' && posContainer)
            ? (posContainer.style.height || window.getComputedStyle(posContainer).height)
            : null;

        $(btn).trigger('click');

        steps.push({
            name: 'click_expand',
            ok: (
                folded.style.display === 'none' &&
                full.style.display === 'block' &&
                full.dataset.built === '1' &&
                btn.textContent.trim() === '收起' &&
                full.querySelectorAll('.breakdown-row').length >= maxCats &&
                !full.textContent.includes('(Other)')
            ),
            folded_display: folded.style.display,
            full_display: full.style.display,
            full_built: !!full.dataset.built,
            full_rows: full.querySelectorAll('.breakdown-row').length,
            expected_full_rows_min: maxCats,
            full_has_other: full.textContent.includes('(Other)'),
            btn_text: btn.textContent.trim(),
        });

        // ---- STEP 3: Vertical height recompute after expand ----
        if (layout === 'vertical' && posContainer) {
            const heightAfterExpand = posContainer.style.height || window.getComputedStyle(posContainer).height;
            const hBefore = parseFloat(heightBeforeExpand || '0');
            const hAfter = parseFloat(heightAfterExpand || '0');
            steps.push({
                name: 'vertical_height_after_expand',
                ok: hAfter > hBefore && hAfter > 0,
                height_before: heightBeforeExpand,
                height_after: heightAfterExpand,
                height_diff: hAfter - hBefore,
                stub_expanded: window.__sv_stub_state.expandedF[fKey],
            });
        }

        // ---- STEP 4: Click collapse ----
        // Mark as collapsed in stub
        window.__sv_stub_state.expandedF[fKey] = false;

        const heightBeforeCollapse = (layout === 'vertical' && posContainer)
            ? (posContainer.style.height || window.getComputedStyle(posContainer).height)
            : null;

        $(btn).trigger('click');

        steps.push({
            name: 'click_collapse',
            ok: (
                (folded.style.display === 'block' || folded.style.display === '') &&
                full.style.display === 'none' &&
                btn.textContent.trim() === '显示全部类别' &&
                full.querySelectorAll('.breakdown-row').length >= maxCats
            ),
            folded_display: folded.style.display,
            full_display: full.style.display,
            full_rows: full.querySelectorAll('.breakdown-row').length,
            btn_text: btn.textContent.trim(),
        });

        // ---- STEP 5: Vertical height recompute after collapse ----
        if (layout === 'vertical' && posContainer) {
            const heightAfterCollapse = posContainer.style.height || window.getComputedStyle(posContainer).height;
            const hBefore = parseFloat(heightBeforeCollapse || '0');
            const hAfter = parseFloat(heightAfterCollapse || '0');
            steps.push({
                name: 'vertical_height_after_collapse',
                ok: hAfter < hBefore,
                height_before: heightBeforeCollapse,
                height_after: heightAfterCollapse,
                height_diff: hAfter - hBefore,
            });
        }

        // ---- STEP 6: Switch field reset ----
        if (layout === 'widescreen') {
            if (full.style.display !== 'block') {
                window.__sv_stub_state.expandedF[fKey] = true;
                $(btn).trigger('click');
            }
            window.resetAllCatFolds();
            window.__sv_stub_state.expandedF[fKey] = false;
        } else {
            // For vertical: contract then re-expand detail -> should reset
            if (summaryEl) $(summaryEl.querySelector('.selector')).trigger('click');
            window.__sv_stub_state.expandedF[fKey] = false;
            if (summaryEl) $(summaryEl.querySelector('.selector')).trigger('click');
        }

        steps.push({
            name: 'reset_after_switch',
            ok: (
                full.innerHTML.trim() === '' &&
                !full.dataset.built &&
                btn.textContent.trim() === '显示全部类别' &&
                (folded.style.display !== 'none' && !folded.classList.contains('isHidden'))
            ),
            folded_display: folded.style.display,
            folded_hidden_class: folded.classList.contains('isHidden'),
            full_empty: full.innerHTML.trim() === '',
            full_built: !!full.dataset.built,
            btn_text: btn.textContent.trim(),
        });

        result(steps);
    } catch (e) {
        console.error(JSON.stringify({ error: e.message, stack: e.stack }));
        process.exit(1);
    }
}, 1500);
