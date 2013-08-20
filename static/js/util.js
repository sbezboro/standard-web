if (typeof Object.create === 'undefined') {
    Object.create = function (o) { 
        function F() {} 
        F.prototype = o; 
        return new F(); 
    };
}

$(document).ready(function() {
    $('.extender').on('click', function(e) {
        var target = '#' + $(this).attr('data-target');
        $(target).toggle();
    });
});