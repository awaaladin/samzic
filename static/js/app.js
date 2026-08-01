/**
 * Progressive enhancement for cart mutations and menu filtering.
 *
 * Everything here is an interception of markup that already works: each cart
 * form has a real action, each filter is a real link or GET form. With this
 * script the same actions happen over fetch() and the page updates in place;
 * without it the browser posts and reloads exactly as before. Nothing is
 * JS-only, and the server validates either way.
 */
(function () {
  'use strict';

  const AJAX_HEADERS = { 'X-Requested-With': 'XMLHttpRequest' };

  /** Reflect the new plate count in the header badge(s). */
  function setCartCount(count) {
    document.querySelectorAll('[data-cart-count]').forEach(el => {
      el.textContent = count;
    });
    document.querySelectorAll('[data-cart-count-text]').forEach(el => {
      el.textContent = 'Cart (' + count + ')';
    });
  }

  /** Briefly mark a button as working so a slow network still feels answered. */
  function busy(button, on) {
    if (!button) return;
    button.disabled = on;
    button.classList.toggle('opacity-50', on);
    button.classList.toggle('pointer-events-none', on);
  }

  /**
   * POST a cart form over fetch and apply the JSON result.
   * Falls back to a normal submit if the request fails outright, so a flaky
   * connection degrades to the old behaviour rather than doing nothing.
   */
  async function postCartForm(form, submitter) {
    const action = (submitter && submitter.getAttribute('formaction')) || form.action;
    const data = new FormData(form);

    // A button with name="quantity" only lands in FormData when it is the
    // submitter, and FormData does not know that — so set it explicitly.
    if (submitter && submitter.name) data.set(submitter.name, submitter.value);

    busy(submitter, true);
    let response;
    try {
      response = await fetch(action, {
        method: 'POST',
        headers: AJAX_HEADERS,
        body: data,
        credentials: 'same-origin',
      });
    } catch (err) {
      busy(submitter, false);
      form.submit();  // network failure: let the browser do it the old way
      return;
    }
    busy(submitter, false);

    let payload;
    try {
      payload = await response.json();
    } catch (err) {
      form.submit();  // not JSON (a login redirect, say) — follow it properly
      return;
    }

    if (!payload.ok) {
      flash(payload.message || 'That did not work. Please try again.', 'error');
      return;
    }

    setCartCount(payload.count);
    if (payload.message) flash(payload.message, payload.level);
    applyCartState(payload);
  }

  /** Update the cart page in place from a mutation response. */
  function applyCartState(payload) {
    const lines = document.getElementById('cart-lines');
    if (!lines) return;  // not on the cart page; the badge update was enough

    if (payload.removed_id) {
      const row = lines.querySelector('[data-row="' + payload.removed_id + '"]');
      if (row) {
        row.style.transition = 'opacity .2s ease';
        row.style.opacity = '0';
        setTimeout(() => row.remove(), 200);
      }
    }

    // Re-sync every remaining row: quantity, line total, and the two buttons
    // whose behaviour depends on the quantity.
    Object.keys(payload.rows || {}).forEach(id => {
      const row = lines.querySelector('[data-row="' + id + '"]');
      if (!row) return;
      const info = payload.rows[id];

      const qty = row.querySelector('[data-qty]');
      if (qty) qty.textContent = info.quantity;

      const total = row.querySelector('[data-line-total]');
      if (total) total.textContent = '₦' + info.line_total;

      const minus = row.querySelector('[data-step="-1"]');
      const plus = row.querySelector('[data-step="1"]');
      const form = row.querySelector('[data-cart-form]');

      if (plus) {
        plus.value = info.quantity + 1;
        // The ceiling comes from the server; infer it from being refused a step.
        plus.disabled = info.quantity >= (window.CART_MAX_QUANTITY || 20);
      }
      if (minus && form) {
        if (info.quantity > 1) {
          minus.setAttribute('name', 'quantity');
          minus.value = info.quantity - 1;
          minus.removeAttribute('formaction');
          minus.setAttribute('aria-label', 'Decrease quantity');
        } else {
          // At 1, minus becomes a remove: same endpoint the no-JS markup uses.
          minus.removeAttribute('name');
          minus.setAttribute('formaction', form.dataset.removeUrl || removeUrlFor(row));
          minus.setAttribute('aria-label', 'Remove item');
        }
      }
    });

    if (payload.summary_html) {
      const summary = document.getElementById('cart-summary');
      if (summary) summary.innerHTML = payload.summary_html;
    }

    // Swap to the empty state once the last line goes.
    const body = document.getElementById('cart-body');
    const empty = document.getElementById('cart-empty');
    if (payload.empty && body && empty) {
      setTimeout(() => { body.hidden = true; empty.hidden = false; }, 220);
    }
  }

  /** The remove endpoint for a row, taken from its own Remove button. */
  function removeUrlFor(row) {
    const remove = row.querySelector('[data-remove]');
    return remove ? remove.getAttribute('formaction') : '';
  }

  // Delegated so rows added later are covered without rebinding.
  document.addEventListener('submit', function (event) {
    const form = event.target.closest('[data-cart-form]');
    if (!form) return;
    event.preventDefault();
    postCartForm(form, event.submitter);
  });

  // ---------------------------------------------------------------------
  // Menu filtering, search, sort and paging — same page, no reload.
  // ---------------------------------------------------------------------
  const grid = document.getElementById('menu-grid');

  if (grid) {
    /** Fetch a menu URL and swap in just the parts that changed. */
    async function loadMenu(url, push) {
      const region = document.getElementById('menu-results');
      region.classList.add('opacity-40');
      region.setAttribute('aria-busy', 'true');

      let html;
      try {
        const response = await fetch(url, { headers: AJAX_HEADERS, credentials: 'same-origin' });
        html = await response.text();
      } catch (err) {
        window.location.href = url;  // let the browser navigate instead
        return;
      }

      // Parse the response and lift out the pieces we replace. Cheaper to
      // maintain than a second JSON serialiser for the same cards.
      const doc = new DOMParser().parseFromString(html, 'text/html');
      const swap = ['menu-grid', 'menu-count', 'menu-pagination', 'menu-filters', 'menu-heading'];
      swap.forEach(id => {
        const next = doc.getElementById(id);
        const current = document.getElementById(id);
        if (next && current) current.innerHTML = next.innerHTML;
      });

      const title = doc.querySelector('title');
      if (title) document.title = title.textContent;

      region.classList.remove('opacity-40');
      region.removeAttribute('aria-busy');

      // Re-run the reveal animation on the new cards.
      if (window.observeReveals) window.observeReveals(region);

      if (push) history.pushState({ menu: url }, '', url);
      region.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    // Category chips, sort options and page links are all plain links inside
    // the filter bar or pagination — one handler covers the lot.
    document.addEventListener('click', function (event) {
      const link = event.target.closest('#menu-filters a, #menu-pagination a');
      if (!link || link.target || event.metaKey || event.ctrlKey || event.shiftKey) return;
      event.preventDefault();
      loadMenu(link.href, true);
    });

    const searchForm = document.getElementById('menu-search');
    if (searchForm) {
      searchForm.addEventListener('submit', function (event) {
        event.preventDefault();
        const params = new URLSearchParams(new FormData(searchForm));
        loadMenu(searchForm.action + '?' + params.toString(), true);
      });

      // Sort is a select: submit its form rather than waiting for the Go button.
      const sort = searchForm.querySelector('[name="sort"]');
      if (sort) {
        sort.addEventListener('change', () => {
          searchForm.requestSubmit
            ? searchForm.requestSubmit()
            : searchForm.dispatchEvent(new Event('submit', { cancelable: true }));
        });
      }
    }

    // Back/forward should move through filter states, not out of the page.
    window.addEventListener('popstate', function (event) {
      if (event.state && event.state.menu) loadMenu(event.state.menu, false);
    });
  }
})();
