(() => {
  const header = document.querySelector('.brand-header');
  const button = header?.querySelector('.menu-toggle');
  const nav = header?.querySelector('#main-nav');
  if (!button || !nav) return;
  const groups = [...nav.querySelectorAll('details')];
  const close = () => {
    button.setAttribute('aria-expanded', 'false');
    nav.classList.remove('is-open');
    groups.forEach(group => { group.open = false; });
  };
  button.addEventListener('click', () => {
    const open = button.getAttribute('aria-expanded') !== 'true';
    close();
    button.setAttribute('aria-expanded', String(open));
    nav.classList.toggle('is-open', open);
  });
  groups.forEach(group => group.addEventListener('toggle', () => {
    if (group.open) groups.forEach(other => { if (other !== group) other.open = false; });
  }));
  document.addEventListener('click', event => { if (!header.contains(event.target)) close(); });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    const focus = button.getAttribute('aria-expanded') === 'true' ? button : nav.querySelector('details[open] summary');
    close();
    focus?.focus();
  });
  header.addEventListener('focusout', event => { if (event.relatedTarget && !header.contains(event.relatedTarget)) close(); });
  const normalize = path => path.replace(/\/index\.html$/, '/');
  document.querySelectorAll('a[href]').forEach(link => {
    const url = new URL(link.href, location.href);
    if (url.origin === location.origin && normalize(url.pathname) === normalize(location.pathname)) {
      if (url.hash) link.setAttribute('href', url.hash);
      else if (nav.contains(link)) link.setAttribute('aria-current', 'page');
    }
  });
  nav.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    if (link.getAttribute('href').startsWith('#')) {
      const target = document.getElementById(link.hash.slice(1));
      if (target) { target.setAttribute('tabindex', '-1'); target.focus({preventScroll:true}); }
    }
    close();
  }));
  matchMedia('(max-width:1100px)').addEventListener('change', close);
})();
