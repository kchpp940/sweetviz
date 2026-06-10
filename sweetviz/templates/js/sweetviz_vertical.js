let g_snapped = "";
let g_lastHovered = "";

function getSafeId(element) {
    let safeId = $(element).data('safe-id');
    if (safeId !== undefined && safeId !== "") {
        return safeId;
    }
    let parent = $(element).closest('[data-safe-id]');
    if (parent.length > 0) {
        return parent.data('safe-id');
    }
    let elemId = $(element).attr('id');
    if (elemId !== undefined) {
        if (elemId.startsWith("summary-")) {
            return elemId.substring(8);
        }
        if (elemId.startsWith("detail-")) {
            return elemId.substring(7);
        }
        if (elemId.startsWith("rollover-")) {
            return elemId.substring(9);
        }
        return elemId;
    }
    return "";
}

function getFieldName(element) {
    let fieldName = $(element).data('field-name');
    if (fieldName !== undefined) {
        return fieldName;
    }
    let parent = $(element).closest('[data-field-name]');
    if (parent.length > 0) {
        return parent.data('field-name');
    }
    return "";
}

function getSummaryElementBySafeId(safeId) {
    return $('[data-safe-id="' + safeId + '"].container-feature-summary, [data-safe-id="' + safeId + '"].container-feature-summary-target');
}

function getDetailElementBySafeId(safeId) {
    return $('#detail-' + safeId);
}

function hideAllDetails()
{
    $(".container-feature-detail").hide();
    $(".container-df-associations").hide();
    $("span.bg-tab-summary-rollover").hide();
}


$("span.bg-tab-summary-rollover").hide();

$(document).ready(function() {
hideAllDetails();
$("span.bg-tab-summary-rollover").hide();

$("#col1").height(g_height);
$("#col2").height(g_height);

// SUMMARY AREA
// --------------------------------------------------------
// EVENT: SUMMARY ROLLOVER
$(".selector").hover(
// ENTER function
function(event) {
    let safeId = $(this).data('safe-id');
    let rolloverSpan = $(this).data('rollover-span');
    let detailDiv = $(this).data('detail-div');

    $("span.bg-tab-summary-rollover").hide();
    $("#" + rolloverSpan).removeClass("bg-tab-summary-rollover-locked");
    $("#" + rolloverSpan).addClass("bg-tab-summary-rollover-vertical");
    $("#" + rolloverSpan).show();
    g_lastHovered = "#" + detailDiv;
    },
// EXIT function
function(event) {
    }
);

// EVENT: SUMMARY CLICK
$(".selector").click(function(event) {
    let summaryContainer = $(this).parent();
    let outerContainer = summaryContainer.parent();
    let safeId = $(this).data('safe-id');
    let detailDiv = $(this).data('detail-div');
    let rolloverSpan = $(this).data('rollover-span');
    let isTarget = summaryContainer.data('is-target') === true;

    if (outerContainer.data('expanded') != 'true')
    {
        // EXPAND
        // --------------------------------------------------------
        $("#" + detailDiv).show();
        outerContainer.data('expanded', 'true');

        if ($('#cat-assoc-window-'+safeId).length) {
            // CATEGORICAL feature: use variable-height window
            var $el = $('#detail_breakdown-' + safeId);
            // HACK: BUG IN BROWSERS? DIVING BY SCALE HERE...
            var bottom = ($el.position().top / g_scale) + $el.outerHeight(true);
            var desiredBottomBreakdown = bottom + 157;

            $el = $('#cat-assoc-window-' + safeId);
            var bottomAssoc = $el.position().top + $el.outerHeight(true);
            var desiredBottomAssoc = bottomAssoc + 166;

            var finalHeight = Math.max(desiredBottomBreakdown, desiredBottomAssoc);
            if (isTarget)
            {
               summaryContainer.css('height', String((finalHeight + 50))+ 'px');
               summaryContainer.css("overflow", "hidden");
            }
            outerContainer.css('height', String(finalHeight) + 'px');
        }
        else
        {
            // NON-CATEGORICAL feature: use fixed height window
            outerContainer.css('height', '1030px');
        }
        // Use the "big" background image for the target
        if (isTarget)
        {
            summaryContainer.find(".bg-tab-summary-target").addClass("bg-tab-summary-target-full");
            summaryContainer.find(".bg-tab-summary-target").removeClass("bg-tab-summary-target");
        }

        // HACK: For SOME reason, a selection gets made when we change what is hidden, unselect it
        let sel = document.getSelection();
        sel.removeAllRanges();

        // Animate to the top of the screen when expanding, so we can see the whole thing immediately
        $('html,body').animate(
            {scrollTop: $("#" + summaryContainer.attr('id')).offset().top}, 'fast');
    }
    else
    {
        // CONTRACT
        // --------------------------------------------------------
        $("#" + detailDiv).hide();

        // HACK: For SOME reason, a selection gets made when we change what is hidden, unselect it
        let sel = document.getSelection();
        sel.removeAllRanges();

        outerContainer.data('expanded', 'false');
        outerContainer.css('height', '161px');

        if (isTarget)
        {
            summaryContainer.find(".bg-tab-summary-target").removeClass("bg-tab-summary-target-full");
            summaryContainer.find(".bg-tab-summary-target").addClass("bg-tab-summary-target");
        }
    }
    }
);


// SPECIFIC BUTTONS
// ---------------------------------------------------------------------------------------------------------------------------
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
    let which_id = $(this).attr('data-target');
    $("#"+which_id).attr('class', $(this).attr('data-new_class') + " pos-detail-num-graph");
});


}); // $(document).ready(...
