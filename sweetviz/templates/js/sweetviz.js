let g_snapped = "";

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
    $("#button-summary-associations-source, #button-summary-associations-compare").removeClass("button-assoc-selected");
    $("#button-summary-associations-source, #button-summary-associations-compare").addClass("button-assoc");
}


$("span.bg-tab-summary-rollover").hide();
hideAllDetails();

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
    if(g_snapped=="")
    {
        let safeId = $(this).data('safe-id');
        let detailDiv = $(this).data('detail-div');
        let rolloverSpan = $(this).data('rollover-span');

        $(".container-feature-detail").hide();
        $("span.bg-tab-summary-rollover").hide();
        $("#" + detailDiv).show();
        $("#" + rolloverSpan).removeClass("bg-tab-summary-rollover-locked");
        $("#" + rolloverSpan).addClass("bg-tab-summary-rollover");
        $("#" + rolloverSpan).show();
    }
    },
// EXIT function
function(event) {
    if(g_snapped=="")
    {
        hideAllDetails();
    }
    }
);
// EVENT: SUMMARY CLICK
$(".selector").click(function(event) {
    $("#button-summary-associations-source, #button-summary-associations-compare").removeClass("button-assoc-selected");
    $("#button-summary-associations-source, #button-summary-associations-compare").addClass("button-assoc");

    let safeId = $(this).data('safe-id');
    let summaryElement = $(this).parent();
    let this_to_snap = summaryElement.attr('id');
    let rolloverSpan = $(this).data('rollover-span');

    if(g_snapped == this_to_snap)
    {
        $("#" + rolloverSpan).removeClass("bg-tab-summary-rollover-locked");
        $("#" + rolloverSpan).addClass("bg-tab-summary-rollover");
        g_snapped = "";
    }
    else if (g_snapped == "")
    {
        $("#" + rolloverSpan).removeClass("bg-tab-summary-rollover");
        $("#" + rolloverSpan).addClass("bg-tab-summary-rollover-locked");
        g_snapped = this_to_snap;
    }
    else if (g_snapped !== this_to_snap)
    {
        let snappedElement = $("#" + g_snapped);
        let snappedSelector = snappedElement.children(".selector").first();
        let snappedRollover = snappedSelector.data('rollover-span');
        if (snappedRollover !== undefined) {
            $("#" + snappedRollover).removeClass("bg-tab-summary-rollover-locked");
            $("#" + snappedRollover).addClass("bg-tab-summary-rollover");
        }

        let currentDetailDiv = $(this).data('detail-div');
        $(".container-feature-detail").hide();
        $("span.bg-tab-summary-rollover").hide();
        $("#" + currentDetailDiv).show();

        $("#" + rolloverSpan).removeClass("bg-tab-summary-rollover");
        $("#" + rolloverSpan).addClass("bg-tab-summary-rollover-locked");
        $("#" + rolloverSpan).css("display","inline");
        g_snapped = this_to_snap;
    }
}
);

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
            hideAllDetails();
            let detailDiv = $(this).data('detail-div');
            $("#" + detailDiv).show();
        }
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
    $("#button-summary-associations-source, #button-summary-associations-compare").removeClass("button-assoc-selected");
    $("#button-summary-associations-source, #button-summary-associations-compare").addClass("button-assoc");
    let this_to_snap = $(this).attr('id');
    let detailDiv = $(this).data('detail-div');
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
        g_snapped = this_to_snap;
        $(this).addClass("button-assoc-selected");
    }
    else
    {
        // SWAP to OTHER ASSOC: DESELECT old, select new
        // --------------------------------------------------------
        let oldSnappedElement = $("#" + g_snapped);
        let oldRolloverSpan = oldSnappedElement.children().first().data('rollover-span');
        if (oldRolloverSpan !== undefined) {
            $("#" + oldRolloverSpan).removeClass("bg-tab-summary-rollover-locked");
            $("#" + oldRolloverSpan).addClass("bg-tab-summary-rollover");
        }
        hideAllDetails();
        $(this).addClass("button-assoc-selected");
        g_snapped = this_to_snap;
        $("#" + detailDiv).show();
    }
});


// DETAIL GRAPH BUTTONS
$(".button-bin").click(function() {
    let which_id = $(this).attr('data-target');
    $("#"+which_id).attr('class', $(this).attr('data-new_class') + " pos-detail-num-graph");
});


}); // $(document).ready(...
