let g_snapped = "";
let g_lastHovered = "";

// ------------------------------------------------------------------------------
// FORMAT HELPERS (mirrors sweetviz.sv_html_formatters)
// ------------------------------------------------------------------------------
function fmtIntLimit(value) {
    if (value === null || value === undefined || isNaN(value)) return "---";
    if (value > 999999) return (value / 1000000).toFixed(1) + "M";
    return value.toLocaleString('en-US');
}
function fmtPercent(value) {
    if (value === null || value === undefined || isNaN(value)) return "---";
    if (value < 1.0 && value > 0.0) return "<1%";
    if (value > 99.0 && value < 100.0) return ">99%";
    return Math.round(value) + "%";
}
function fmtSmartRange(value, range) {
    if (value === null || value === undefined || isNaN(value)) return "---";
    let absRange = Math.abs(range);
    if (absRange === 0.0) return "0.00";
    if (absRange < 0.001) return value.toFixed(5);
    if (absRange < 0.1) return value.toFixed(3);
    if (absRange < 1.0) return value.toFixed(3);
    if (absRange < 10) return value.toFixed(2);
    if (absRange < 100) return value.toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1});
    if (absRange < 99999) return Math.round(value).toLocaleString('en-US');
    if (absRange < 999999) return (value / 1000.0).toFixed(0) + "k";
    if (absRange < 999999999) return (value / 1000000.0).toFixed(1) + "M";
    return (value / 1000000000.0).toFixed(1) + "B";
}

// ------------------------------------------------------------------------------
// CATEGORICAL DETAIL: Build full rows from JSON data
// ------------------------------------------------------------------------------
function buildCatDetailRows(feature_index) {
    let dataEl = document.getElementById("cat-data-f" + feature_index);
    let layoutEl = document.getElementById("cat-layout-f" + feature_index);
    let fullContainer = document.getElementById("cat-full-f" + feature_index);
    if (!dataEl || !layoutEl || !fullContainer) return;

    let data = JSON.parse(dataEl.textContent);
    let layout = JSON.parse(layoutEl.textContent);
    let cols = layout.cols;
    let targetType = layout.target_type;
    let hasCompare = layout.has_compare;
    let hasCompareTarget = layout.has_compare_target;
    let isTargetFeature = layout.is_target_feature;
    let maxRange = layout.max_range;
    let pageLayout = layout.page_layout;

    let html = "";
    let rowIdx = 0;
    for (let i = 0; i < data.length; i++) {
        let row = data[i];
        let rowClass = (rowIdx % 2 === 0) ? "" : "row-colored";
        rowIdx++;

        if (row.is_total !== null && row.is_total !== undefined) {
            html += '<div class="breakdown-row text-value" style="width:553px"></div>';
        }

        let nameColorClass = "color-normal";
        if (pageLayout === "vertical" && isTargetFeature) {
            nameColorClass = "color-target-summary";
        }

        html += '<div class="breakdown-row text-value ' + rowClass + '" style="width:553px">';

        // Name
        html += '<div class="text-label ' + nameColorClass + '" style="position: absolute; left:10px; width: ' + cols.name_max_len + 'px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + row.name + '</div>';

        // Source count/percent
        if (row.count) {
            html += '<div class="pair__col color-source" style="left: ' + cols.source + 'px">';
            html += '<div class="pair-pos__num dim">' + fmtIntLimit(row.count.number) + '</div>';
            html += '<div class="pair-pos__perc">' + fmtPercent(row.count.perc) + '</div>';
            html += '</div>';
        }

        // Compare count/percent
        if (hasCompare && row.count_compare) {
            html += '<div class="pair__col color-compare" style="position: absolute; left: ' + cols.compare + 'px">';
            html += '<div class="pair-pos__num dim">' + fmtIntLimit(row.count_compare.number) + '</div>';
            html += '<div class="pair-pos__perc">' + fmtPercent(row.count_compare.perc) + '</div>';
            html += '</div>';
        }

        // Source target stats
        if (row.target_stats) {
            if (targetType === "BOOL") {
                html += '<div class="pair__col color-source-target" style="position: absolute; left: ' + cols.source_target + 'px">';
                html += '<div class="pair-pos__num dim">' + fmtIntLimit(row.target_stats.number) + '</div>';
                html += '<div class="pair-pos__perc">' + fmtPercent(row.target_stats.perc) + '</div>';
                html += '</div>';
            } else {
                html += '<div class="pair__header color-source-target" style="position: absolute; left: ' + cols.source_target + 'px; text-align: right;">';
                html += fmtSmartRange(row.target_stats.number, maxRange);
                html += '</div>';
            }
        }

        // Compare target stats
        if (hasCompareTarget && row.target_stats_compare) {
            if (targetType === "BOOL") {
                html += '<div class="pair__col color-compare-target" style="position: absolute; left: ' + cols.compare_target + 'px">';
                html += '<div class="pair-pos__num dim">' + fmtIntLimit(row.target_stats_compare.number) + '</div>';
                html += '<div class="pair-pos__perc">' + fmtPercent(row.target_stats_compare.perc) + '</div>';
                html += '</div>';
            } else {
                html += '<div class="pair__header color-compare-target" style="position: absolute; left: ' + cols.compare_target + 'px; text-align: right;">';
                html += fmtSmartRange(row.target_stats_compare.number, maxRange);
                html += '</div>';
            }
        }

        html += '</div>';
    }
    fullContainer.innerHTML = html;
    fullContainer.dataset.built = "1";
}

// ------------------------------------------------------------------------------
// CATEGORICAL DETAIL: Reset fold for a single feature (by order index string like "0", "f0", "f-1")
// ------------------------------------------------------------------------------
function resetCatFoldByFeatureIndex(raw_index) {
    let feature_index;
    if (typeof raw_index === "string") {
        if (raw_index.startsWith("f")) {
            feature_index = raw_index.substring(1);
        } else {
            feature_index = raw_index;
        }
    } else {
        feature_index = raw_index;
    }
    let folded_id = "#cat-folded-f" + feature_index;
    let full_id = "#cat-full-f" + feature_index;
    let btn_id = "#cat-toggle-btn-f" + feature_index;
    $(folded_id).show();
    let fullEl = $(full_id);
    fullEl.hide().empty();
    if (fullEl[0]) delete fullEl[0].dataset.built;
    $(btn_id).text("显示全部类别");
}

// ------------------------------------------------------------------------------
// CATEGORICAL DETAIL: Recompute vertical layout height for a feature after expand/collapse
// ------------------------------------------------------------------------------
function recomputeVerticalFeatureHeight(summary_parent) {
    if (!summary_parent || summary_parent.data('expanded') !== 'true') return;

    let feature_index_str = summary_parent.attr('id').substring(8);
    if (summary_parent.attr('id') === "summary-target") {
        feature_index_str = "f-1";
    }
    if ($('#cat-assoc-window-' + feature_index_str).length) {
        let $el = $('#detail_breakdown-' + feature_index_str);
        let bottom = ($el.position().top / g_scale) + $el.outerHeight(true);
        let desiredBottomBreakdown = bottom + 157;

        $el = $('#cat-assoc-window-' + feature_index_str);
        let bottomAssoc = $el.position().top + $el.outerHeight(true);
        let desiredBottomAssoc = bottomAssoc + 166;

        let finalHeight = Math.max(desiredBottomBreakdown, desiredBottomAssoc);
        if (summary_parent.attr('id') === "summary-target") {
            summary_parent.css('height', String((finalHeight + 50)) + 'px');
            $("#summary-target").css("overflow", "hidden");
        }
        summary_parent.parent().css('height', String(finalHeight) + 'px');
    }
}

function hideAllDetails()
{
    $(".container-feature-detail").hide();
    $(".container-df-associations").hide();
    $("span.bg-tab-summary-rollover").hide();
}


// GLOBAL EVENTS
// ---------------------------------------------------------------------------------------------------------------------------
// EVENT: [ANYWHERE] RIGHT-CLICK REMOVES SELECTION
// $(document).contextmenu(function() {
//     if (g_snapped != "")
//     {
//         g_snapped = "";
//         hideAllDetails();
//     }
//     if (g_lastHovered != "")
//     {
//         $(g_lastHovered).show();
//         //alert("#"+g_lastHovered);
//     }
//     return false;
// });

$("span.bg-tab-summary-rollover").hide();
// hideAllDetails();

$(document).ready(function() {
// INITIALIZATION
// --------------------------------------------------------
hideAllDetails();
$("span.bg-tab-summary-rollover").hide();

// Make the detail column the same height, so the floating element has room
//$("#col2").height($("#col1").height());
$("#col1").height(g_height);
$("#col2").height(g_height);
//alert($("#col1").height());

// SUMMARY AREA
// --------------------------------------------------------
// EVENT: SUMMARY ROLLOVER
// $(".selector, .container-feature-summary-target").hover(
$(".selector").hover(
// ENTER function
function(event) {
    // Rollover start!
    // $(".container-feature-detail").hide();
    $("span.bg-tab-summary-rollover").hide();
    $("#" + $(this).data("rollover-span")).removeClass("bg-tab-summary-rollover-locked");
    $("#" + $(this).data("rollover-span")).addClass("bg-tab-summary-rollover-vertical");
    $("#" + $(this).data("rollover-span")).show();
    g_lastHovered = "#" + $(this).data("detail-div");
    },
// EXIT function
function(event) {
    // Rollover end!
    // hideAllDetails();
    //FBFB        $("#" + $(this).data("detail-div")).hide();
    }
);

// EVENT: SUMMARY CLICK
// $(".container-feature-summary, .container-feature-summary-target").click(function(event) {
$(".selector").click(function(event) {
    if ($(this).parent().parent().data('expanded') != 'true')
    {
        // EXPAND
        // --------------------------------------------------------
        // Reset categorical fold state when expanding a feature
        let fid = $(this).parent().attr('id').substring(8);
        if ($(this).parent().attr('id') === "summary-target") {
            fid = "f-1";
        }
        resetCatFoldByFeatureIndex(fid);

        $("#" + $(this).data("detail-div")).show();
        $(this).parent().parent().data('expanded', 'true');
        //alert($(this).parent().attr('id').substring(8) );

        var feature_index_str = $(this).parent().attr('id').substring(8);
        if ($(this).parent().attr('id') == "summary-target") {
            // Special feature name for target, so use common index notation for the following tasks
            feature_index_str = "f-1";
        }
        if ($('#cat-assoc-window-'+feature_index_str).length) {
            // CATEGORICAL feature: use variable-height window
            var $el = $('#detail_breakdown-' + feature_index_str);  //record the elem so you don't crawl the DOM everytime
            // HACK: BUG IN BROWSERS? DIVING BY SCALE HERE...
            var bottom = ($el.position().top / g_scale) + $el.outerHeight(true); // passing "true" will also include the top and bottom margin
            var desiredBottomBreakdown = bottom + 157;

            $el = $('#cat-assoc-window-' + feature_index_str);  //record the elem so you don't crawl the DOM everytime
            var bottomAssoc = $el.position().top + $el.outerHeight(true); // passing "true" will also include the top and bottom margin
            var desiredBottomAssoc = bottomAssoc + 166;

            var finalHeight = Math.max(desiredBottomBreakdown, desiredBottomAssoc);
            if ($(this).parent().attr('id') == "summary-target")
            {
                // More special processing for the target: change its background and limit its height (so it doesn't show through others below)
                // (Here, make the Height a bit taller so the black background shows through)
               $(this).parent().css('height', String((finalHeight + 50))+ 'px');
               $("#summary-target").css("overflow", "hidden");
            }
            $(this).parent().parent().css('height', String(finalHeight) + 'px');
        }
        else
        {
            // NON-CATEGORICAL feature: use fixed height window
            $(this).parent().parent().css('height', '1030px');
        }
        // Use the "big" background image for the target
        if ($(this).parent().attr('id') == "summary-target")
        {
            $("#summary-target-bg").addClass("bg-tab-summary-target-full");
            $("#summary-target-bg").removeClass("bg-tab-summary-target");
        }

        // HACK: For SOME reason, a selection gets made when we change what is hidden, unselect it
        let sel = document.getSelection();
        sel.removeAllRanges();

        // Animate to the top of the screen when expanding, so we can see the whole thing immediately
        $('html,body').animate(
            {scrollTop: $("#" + $(this).parent().attr('id')).offset().top}, 'fast');
    }
    else
    {
        // CONTRACT
        // --------------------------------------------------------
        $("#" + $(this).data("detail-div")).hide();

        // Reset categorical fold state when collapsing a feature
        let fid = $(this).parent().attr('id').substring(8);
        if ($(this).parent().attr('id') === "summary-target") {
            fid = "f-1";
        }
        resetCatFoldByFeatureIndex(fid);

        // HACK: For SOME reason, a selection gets made when we change what is hidden, unselect it
        let sel = document.getSelection();
        sel.removeAllRanges();

        $(this).parent().parent().data('expanded', 'false');
        $(this).parent().parent().css('height', '161px');

        if ($(this).parent().attr('id') == "summary-target")
        {
            $("#summary-target-bg").removeClass("bg-tab-summary-target-full");
            $("#summary-target-bg").addClass("bg-tab-summary-target");
        }
    }
    // var offTop = $("#" + $(this).parent().attr('id')).offset().top;
  //  $('html,body').scrollTop(offTop);
    // let thisIndex = $(this).parent().parent().data('order-index');
    //alert(thisIndex);
    // for (let i = parseInt(thisIndex) + 1; i < 10; i++) {
    //     let currentTop = $("#summary-pos-f" + i).attr('style')
    //     $("#summary-pos-f" + i).attr('style',
    // }
// if(g_snapped == $(this).parent().attr('id'))
//     {
//         $("#" + $(this).data("rollover-span")).removeClass("bg-tab-summary-rollover-locked");
//         $("#" + $(this).data("rollover-span")).addClass("bg-tab-summary-rollover");
//         g_snapped = "";
//     }
//     else if (g_snapped == "")
//     {
//         $("#" + $(this).data("rollover-span")).removeClass("bg-tab-summary-rollover");
//         $("#" + $(this).data("rollover-span")).addClass("bg-tab-summary-rollover-locked");
//         g_snapped = $(this).parent().attr('id');
// //        $("#" + $(this).data("detail-div")).show();
//         //$(g_lastHovered).show();
//         // alert(this.parent().id);
//     }
    }
);


// SPECIFIC BUTTONS
// ---------------------------------------------------------------------------------------------------------------------------
// SUMMARY: ASSOCIATIONS
// $("#button-summary-associations-source, #button-summary-associations-compare").hover(
//     // ENTER function
//     function()
//     {
//         if(g_snapped=="")
//         {
//             hideAllDetails();
//             $("#df-assoc").show();
//             //$("#df-assoc").show();
//         }
//         g_lastHovered = "#df-assoc";
//     },
//     // EXIT function
//     function()
//     {
//         if(g_snapped=="")
//         {
//             hideAllDetails();
//         }
//     });
// );

// ASSOCIATIONS CLICK
$("#button-summary-associations-source, #button-summary-associations-compare").click(function(event) {
    let actual_div = "#" + $(this).data("detail-div");
    // Quick hack: just remove the selected state to both buttons and restore if needed
    $("#button-summary-associations-source, #button-summary-associations-compare").removeClass("button-assoc-selected");
    $("#button-summary-associations-source, #button-summary-associations-compare").addClass("button-assoc");
    if(g_snapped == actual_div)
    {
        // DESELECT/HIDE ASSOC
        // --------------------------------------------------------
        g_snapped = "";
        $(actual_div).hide();
        $(".page-all-summaries").css({top: "160px"});
        // $(this).removeClass("button-assoc-selected");
        // $(this).addClass("button-assoc");
    }
    else if(g_snapped == "")
    {
        // SELECT/SHOW ASSOC
        // --------------------------------------------------------
        g_snapped =  actual_div;
        $(actual_div).show();
        $(".page-all-summaries").css({top: "993px"});
        $(this).addClass("button-assoc-selected");
    }
    else
    {
        // SWAP to OTHER ASSOC: DESELECT old, select new
        // --------------------------------------------------------
        $(g_snapped).hide();
        g_snapped =  actual_div;
        $(this).addClass("button-assoc-selected");
        $(actual_div).show();
    }
});


// DETAIL GRAPH BUTTONS
$(".button-bin").click(function() {
    which_id = $(this).attr('data-target');
    $("#"+which_id).attr('class', $(this).attr('data-new_class') + " pos-detail-num-graph");
});

// CATEGORICAL DETAIL: EXPAND/COLLAPSE (lazy build full rows on first expand)
$(".cat-fold-toggle").click(function() {
    let feature_index = $(this).data('feature-index');
    let folded_id = "#cat-folded-f" + feature_index;
    let full_id = "#cat-full-f" + feature_index;
    let btn = $(this);
    let fullContainer = $(full_id);

    // Find the summary parent element for recomputing vertical height
    let summary_parent = $(this).closest('[data-expanded]');

    if ($(folded_id).is(":visible")) {
        // EXPAND: build DOM lazily on first expand
        if (!fullContainer[0] || !fullContainer[0].dataset.built) {
            buildCatDetailRows(feature_index);
        }
        $(folded_id).hide();
        fullContainer.show();
        btn.text("收起");
    } else {
        // COLLAPSE: just hide, keep DOM for potential re-expand
        fullContainer.hide();
        $(folded_id).show();
        btn.text("显示全部类别");
    }

    // Recompute vertical layout height
    recomputeVerticalFeatureHeight(summary_parent);
});


}); // $(document).ready(...
