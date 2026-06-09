let g_snapped = "";
// let g_lastHovered = "";

// ------------------------------------------------------------------------------
// CATEGORICAL FOLD MODULE (incremental add)
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
        html += '<div class="text-label ' + nameColorClass + '" style="position: absolute; left:10px; width: ' + cols.name_max_len + 'px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">' + row.name + '</div>';
        if (row.count) {
            html += '<div class="pair__col color-source" style="left: ' + cols.source + 'px">';
            html += '<div class="pair-pos__num dim">' + fmtIntLimit(row.count.number) + '</div>';
            html += '<div class="pair-pos__perc">' + fmtPercent(row.count.perc) + '</div>';
            html += '</div>';
        }
        if (hasCompare && row.count_compare) {
            html += '<div class="pair__col color-compare" style="position: absolute; left: ' + cols.compare + 'px">';
            html += '<div class="pair-pos__num dim">' + fmtIntLimit(row.count_compare.number) + '</div>';
            html += '<div class="pair-pos__perc">' + fmtPercent(row.count_compare.perc) + '</div>';
            html += '</div>';
        }
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
function resetAllCatFolds() {
    $(".cat-fold-toggle").each(function() {
        let feature_index = $(this).data('feature-index');
        let folded_id = "#cat-folded-f" + feature_index;
        let full_id = "#cat-full-f" + feature_index;
        $(folded_id).show();
        let fullEl = $(full_id);
        fullEl.hide().empty();
        if (fullEl[0]) delete fullEl[0].dataset.built;
        $(this).text("显示全部类别");
    });
}

function hideAllDetails()
{
    $(".container-feature-detail").hide();
    $(".container-df-associations").hide();
    $("span.bg-tab-summary-rollover").hide();
    $("#button-summary-associations-source, #button-summary-associations-compare").removeClass("button-assoc-selected");
    $("#button-summary-associations-source, #button-summary-associations-compare").addClass("button-assoc");
    resetAllCatFolds();
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
hideAllDetails();

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
    if(g_snapped=="")
    {
        // Rollover start!
        resetAllCatFolds();
        $(".container-feature-detail").hide();
        $("span.bg-tab-summary-rollover").hide();
        $("#" + $(this).data("detail-div")).show();
        $("#" + $(this).data("rollover-span")).removeClass("bg-tab-summary-rollover-locked");
        $("#" + $(this).data("rollover-span")).addClass("bg-tab-summary-rollover");
        $("#" + $(this).data("rollover-span")).show();
    }
    // g_lastHovered = "#" + $(this).data("detail-div");
    },
// EXIT function
function(event) {
    if(g_snapped=="")
    {
        // Rollover end!
        hideAllDetails();
//FBFB        $("#" + $(this).data("detail-div")).hide();
    }
    }
);
// EVENT: SUMMARY CLICK
// $(".container-feature-summary, .container-feature-summary-target").click(function(event) {
$(".selector").click(function(event) {
    // No matter what, we should deselect the associations buttons
    $("#button-summary-associations-source, #button-summary-associations-compare").removeClass("button-assoc-selected");
    $("#button-summary-associations-source, #button-summary-associations-compare").addClass("button-assoc");

    // alert($(this).parent().attr('id'));
    let this_to_snap=$(this).parent().attr('id');

    if(g_snapped == this_to_snap)
    {
        // "Unselect"
        $("#" + $(this).data("rollover-span")).removeClass("bg-tab-summary-rollover-locked");
        $("#" + $(this).data("rollover-span")).addClass("bg-tab-summary-rollover");
        g_snapped = "";
    }
    else if (g_snapped == "")
    {
        // "Select"
        resetAllCatFolds();
        $("#" + $(this).data("rollover-span")).removeClass("bg-tab-summary-rollover");
        $("#" + $(this).data("rollover-span")).addClass("bg-tab-summary-rollover-locked");
        g_snapped = $(this).parent().attr('id');
        //$("#" + $(this).data("detail-div")).show();
        //$(g_lastHovered).show();
        // alert(this.parent().id);
    }
    else if (g_snapped !== this_to_snap) // implied
    {
        // "Select" while another was previously selected
        $("#" + $("#"+g_snapped).children().data("rollover-span")).removeClass("bg-tab-summary-rollover-locked");
        $("#" + $("#"+g_snapped).children().data("rollover-span")).addClass("bg-tab-summary-rollover");

        resetAllCatFolds();
        $(".container-feature-detail").hide();
        $("span.bg-tab-summary-rollover").hide();
        $("#" + $(this).data("detail-div")).show();
        
        $("#" + $(this).data("rollover-span")).removeClass("bg-tab-summary-rollover");
        $("#" + $(this).data("rollover-span")).addClass("bg-tab-summary-rollover-locked");
        $("#" + $(this).data("rollover-span")).css("display","inline");
        g_snapped = $(this).parent().attr('id');
    }
/*
    if (g_snapped != "")
    {
        $('html,body').animate(
            {scrollTop: $("#" + g_snapped).offset().top},
            'fast');

    }

 */
}
);
/*
$(window).scroll(function(e){
  var $el = $('.container-feature-detail');
    $el.css({'position': 'fixed', 'top': '0px'});

});
function fix_scroll() {
  var s = parseFloat($(window).scrollTop()) / 0.6;
  var fixedTitle = $('.container-feature-detail');
  fixedTitle.css('position','absolute');
  fixedTitle.css('top',s + 'px');
}fix_scroll();

$(window).on('scroll',fix_scroll);
*/

// ---------------------------------------------------------------------------------------------------------------------------
// SPECIFIC BUTTONS
// ---------------------------------------------------------------------------------------------------------------------------
// SUMMARY: ASSOCIATIONS -> HOVER
// --------------------------------------------------------
$("#button-summary-associations-source, #button-summary-associations-compare").hover(
    // ENTER function
    function()
    {
        if(g_snapped=="")
        {
            resetAllCatFolds();
            hideAllDetails();
            $("#" + $(this).data("detail-div")).show();
            // $("#df-assoc").show();
            //$("#df-assoc").show();
        }
        // g_lastHovered = "#df-assoc";
    },
    // EXIT function
    function()
    {
        if(g_snapped=="")
        {
            hideAllDetails();
        }
    });

// SUMMARY: ASSOCIATIONS -> CLICK
// --------------------------------------------------------
$("#button-summary-associations-source, #button-summary-associations-compare").click(function(event) {
    // Quick hack: just remove the selected state to both buttons and restore if needed
    $("#button-summary-associations-source, #button-summary-associations-compare").removeClass("button-assoc-selected");
    $("#button-summary-associations-source, #button-summary-associations-compare").addClass("button-assoc");
    let this_to_snap=this.id;
    if(g_snapped == this_to_snap)
    {
        // DESELECT/HIDE ASSOC
        // --------------------------------------------------------
        g_snapped = "";
    }
    else if(g_snapped=="")
    {
        // SELECT/SHOW ASSOC (Hide other one if already shown)
        // --------------------------------------------------------
        resetAllCatFolds();
        //$(".container-feature-detail").hide();
        //alert("#" + this.id+" GS:"+g_snapped);
        //$("#df-assoc").show();
        g_snapped = this.id;
        $(this).addClass("button-assoc-selected");
    }
    else
    {
        // SWAP to OTHER ASSOC: DESELECT old, select new
        // --------------------------------------------------------
        $("#" + $("#"+g_snapped).children().data("rollover-span")).removeClass("bg-tab-summary-rollover-locked");
        $("#" + $("#"+g_snapped).children().data("rollover-span")).addClass("bg-tab-summary-rollover");
        resetAllCatFolds();
        hideAllDetails();
        $(this).addClass("button-assoc-selected");
        g_snapped = this.id;
        $("#" + $(this).data("detail-div")).show();
    }
//    $(this).addClass("assoc_active");
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

    if ($(folded_id).is(":visible")) {
        if (!fullContainer[0] || !fullContainer[0].dataset.built) {
            buildCatDetailRows(feature_index);
        }
        $(folded_id).hide();
        fullContainer.show();
        btn.text("收起");
    } else {
        fullContainer.hide();
        $(folded_id).show();
        btn.text("显示全部类别");
    }
});


}); // $(document).ready(...
