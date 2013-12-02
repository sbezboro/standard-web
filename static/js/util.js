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

  $(document).on('click', '.nav-pills a', function() {
    var $anchor = $(this);
    var id = $anchor.attr('href').substring(1);

    var $pill = $(this).closest('li');

    $('.nav-pills li').each(function() {
      var $otherPill = $(this);

      if ($otherPill[0] == $pill[0]) {
        $otherPill.addClass('active');
      } else {
        $otherPill.removeClass('active');
      }
    });

    $('.nav-section').each(function() {
      var $section = $(this);

      if ($section.attr('id') === id) {
        $section.addClass('active');
        $section.removeClass('hidden');
      } else {
        $section.addClass('hidden');
        $section.removeClass('active');
      }
    });
  });

  $('.nav-section').each(function() {
    var $this = $(this);
    if (!$this.hasClass('active')) {
      $this.addClass('hidden');
    }
  });
});