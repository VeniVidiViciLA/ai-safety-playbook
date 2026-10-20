/* Small progressive enhancements for playbook pages. */
(function () {
  'use strict';
  document.addEventListener('click', function (e) {
    if (e.target.closest && e.target.closest('[data-print]')) window.print();
  });
  // On narrow screens, start the contents panel collapsed.
  var d = document.querySelector('.doc-sidebar details');
  if (d && window.matchMedia('(max-width: 900px)').matches) d.removeAttribute('open');
})();
