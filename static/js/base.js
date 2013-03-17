jQuery(document).ready(function() {
    jQuery("abbr.timeago").timeago();
    $("#searchBox").placeholder();
/*
    //$(".face-large").fadeTo(0, 0);
    $(".face-large").load(function() {
        $(this).fadeTo(0, 0);
        $(this).fadeTo(200, 1);
    });
    //$(".face-thumb").fadeTo(0, 0);
    $(".face-thumb").load(function() {
        $(this).fadeTo(0, 0);
        $(this).fadeTo(200, 1);
    });*/
});

function playerSearch() {
    if ($("#searchBox").val()) {
        window.location = "/search?q=" + $("#searchBox").val();
    }
}

$.ajaxSetup ({
    cache: false
});