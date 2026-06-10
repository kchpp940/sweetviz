let g_snapped = "";
// let g_lastHovered = "";

function getSafeId(element) {
    let safeId = $(element).data('safe-id');
    if (safeId !== undefined && safeId !== "") {
        return safeId;
    }
    let parent = $(element).closest('[data-safe-id]');
    if (parent.length > 0) {
        return parent.data('safe-id');
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

function hideAllDetails()
{
    $(".container-feature-detail").hide();
    $(".container-df-associations").hide();
    $("span.bg-tab-summary-rollover").hide();
    $("#button-summary-associations-source, #button-summary-associations-compare").removeClass("button-assoc-selected");
    $("#button-summary-associations-source, #button-summary-associations-compare").addClass("button-assoc");
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
        let safeId = getSafeId(this);
        $(".container-feature-detail").hide();
        $("span.bg-tab-summary-rollover").hide();
        $("#detail-" + safeId).show();
        $("#rollover-" + safeId).removeClass("bg-tab-summary-rollover-locked");
        $("#rollover-" + safeId).addClass("bg-tab-summary-rollover");
        $("#rollover-" + safeId).show();
    }
    // g_lastHovered = "#detail-" + getSafeId(this);
    },
// EXIT function
function(event) {
    if(g_snapped=="")
    {
        // Rollover end!
        hideAllDetails();
//FBFB        $("#detail-" + getSafeId(this)).hide();
    }
    }
);
// EVENT: SUMMARY CLICK
// $(".container-feature-summary, .container-feature-summary-target").click(function(event) {
$(".selector").click(function(event) {
    // No matter what, we should deselect the associations buttons
    $("#button-summary-associations-source, #button-summary-associations-compare").removeClass("button-assoc-selected");
    $("#button-summary-associations-source, #button-summary-associations-compare").addClass("button-assoc");

    let this_to_snap=$(this).parent().attr('id');
    let safeId = getSafeId(this);

    if(g_snapped == this_to_snap)
    {
        // "Unselect"
        $("#rollover-" + safeId).removeClass("bg-tab-summary-rollover-locked");
        $("#rollover-" + safeId).addClass("bg-tab-summary-rollover");
        g_snapped = "";
    }
    else if (g_snapped == "")
    {
        // "Select"
        $("#rollover-" + safeId).removeClass("bg-tab-summary-rollover");
        $("#rollover-" + safeId).addClass("bg-tab-summary-rollover-locked");
        g_snapped = $(this).parent().attr('id');
        //$("#detail-" + safeId).show();
        //$(g_lastHovered).show();
        // alert(this.parent().id);
    }
    else if (g_snapped !== this_to_snap) // implied
    {
        // "Select" while another was previously selected
        let snappedSafeId = $("#"+g_snapped).data("safe-id");
        $("#rollover-" + snappedSafeId).removeClass("bg-tab-summary-rollover-locked");
        $("#rollover-" + snappedSafeId).addClass("bg-tab-summary-rollover");

        $(".container-feature-detail").hide();
        $("span.bg-tab-summary-rollover").hide();
        $("#detail-" + safeId).show();
        
        $("#rollover-" + safeId).removeClass("bg-tab-summary-rollover");
        $("#rollover-" + safeId).addClass("bg-tab-summary-rollover-locked");
        $("#rollover-" + safeId).css("display","inline");
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
            hideAllDetails();
            $("#" + getSafeId(this)).show();
            // $("#df-assoc").show();
            //$("#df-assoc").show();
        }
        // g_lastHovered = "#" + getSafeId(this);
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
    let safeId = getSafeId(this);
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
        let snappedSafeId = $("#"+g_snapped).data("safe-id");
        $("#rollover-" + snappedSafeId).removeClass("bg-tab-summary-rollover-locked");
        $("#rollover-" + snappedSafeId).addClass("bg-tab-summary-rollover");
        hideAllDetails();
        $(this).addClass("button-assoc-selected");
        g_snapped = this.id;
        $("#" + safeId).show();
    }
//    $(this).addClass("assoc_active");
});


// DETAIL GRAPH BUTTONS
$(".button-bin").click(function() {
    which_id = $(this).attr('data-target');
    $("#"+which_id).attr('class', $(this).attr('data-new_class') + " pos-detail-num-graph");
});


}); // $(document).ready(...
