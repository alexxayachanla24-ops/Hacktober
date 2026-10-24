/* Cursor chase physics are separate from the DOM so timing stays testable. */
(() => {
  class Chase {
    constructor() {
      Object.assign(this, { x: 24, y: 140, vx: 0, vy: 0, dragging: false,
        flightUntil: 0, danceUntil: 0, frozenUntil: 0, immuneUntil: 0,
        pointer: { x: 0, y: 0, active: false }, hits: [] });
    }
    hit(now) {
      if (now < this.danceUntil) return false;
      this.hits = this.hits.filter(time => now - time <= 5000);
      this.hits.push(now);
      if (this.hits.length < 20) return false;
      this.hits = [];
      this.danceUntil = now + 6000;
      this.frozenUntil = 0;
      this.immuneUntil = this.danceUntil + 1500;
      this.vx = this.vy = 0;
      return true;
    }
    advance(dt, now, width, height) {
      dt = Math.min(Math.max(dt, 0), 0.05);
      const w = Math.max(0, width - 90), h = Math.max(0, height - 130);
      let caught = false;
      if (!this.dragging && now >= this.danceUntil && now >= this.frozenUntil) {
        if (now < this.flightUntil) {
          this.x += this.vx * dt; this.y += this.vy * dt;
          if (this.x < 0 || this.x > w) this.vx *= -0.7;
          if (this.y < 0 || this.y > h) this.vy *= -0.7;
          this.vx *= Math.exp(-1.7 * dt); this.vy *= Math.exp(-1.7 * dt);
        } else if (this.pointer.active) {
          const dx = this.pointer.x - (this.x + 45), dy = this.pointer.y - (this.y + 45);
          const distance = Math.hypot(dx, dy);
          const travel = Math.min(distance, 170 * dt);
          if (distance) { this.x += dx / distance * travel; this.y += dy / distance * travel; }
          if (distance <= 34 && now >= this.immuneUntil) {
            this.frozenUntil = now + 900;
            this.immuneUntil = now + 3500;
            caught = true;
          }
        }
      }
      this.x = Math.max(0, Math.min(w, this.x));
      this.y = Math.max(0, Math.min(h, this.y));
      this.hits = this.hits.filter(time => now - time <= 5000);
      return caught;
    }
  }

  function mount({ app, onHit = () => {}, onCatch = () => {}, onDance = () => {} }) {
    const game = new Chase(), controller = new AbortController();
    const listen = (el, event, handler, options = {}) => el.addEventListener(event, handler,
      { ...options, signal: controller.signal });
    const el = document.createElement('img');
    el.className = 'walker'; el.src = '/static/sources/walker.png';
    el.alt = 'Tung Tung Sahur'; el.draggable = false; el.tabIndex = 0;
    el.setAttribute('role', 'button');
    el.setAttribute('aria-label', 'Tung Tung: grab and throw, or hit 20 times in five seconds to dance');
    const hud = document.createElement('div');
    hud.className = 'tung-hud';
    const notice = document.createElement('div');
    notice.className = 'tung-freeze'; notice.hidden = true;
    notice.setAttribute('role', 'status');
    notice.textContent = '🥶 CAUGHT! Frozen for a moment… Escape to break free.';
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let raf = 0, last = performance.now(), pointerId = null, sample = null;
    let savedInert = null, shakeUntil = 0, facing = 1;
    document.body.append(el, hud, notice);

    function thaw() {
      notice.hidden = true;
      if (savedInert !== null) { app.inert = savedInert; savedInert = null; }
      document.body.classList.remove('tung-frozen');
    }
    function hit() {
      const dancing = game.hit(performance.now());
      if (dancing) { thaw(); onDance(); }
      else if (performance.now() >= game.danceUntil) onHit();
    }
    function release(event, cancelled = false) {
      if (pointerId !== event.pointerId) return;
      if (el.hasPointerCapture(pointerId)) el.releasePointerCapture(pointerId);
      game.dragging = false;
      if (cancelled || !sample || performance.now() - sample.time > 120) game.vx = game.vy = 0;
      game.flightUntil = performance.now() + (Math.hypot(game.vx, game.vy) > 80 ? 1800 : 0);
      game.immuneUntil = Math.max(game.immuneUntil, performance.now() + 1000);
      if (event.pointerType === 'touch') game.pointer.active = false;
      pointerId = null; sample = null;
    }
    listen(window, 'pointermove', event => {
      if (event.pointerType !== 'touch') game.pointer = { x: event.clientX, y: event.clientY, active: true };
    }, { passive: true });
    listen(document, 'pointerout', event => { if (!event.relatedTarget) game.pointer.active = false; });
    listen(el, 'pointerdown', event => {
      if (event.button !== 0 || pointerId !== null) return;
      event.preventDefault();
      hit();
      pointerId = event.pointerId; el.setPointerCapture(pointerId);
      game.dragging = true; game.vx = game.vy = 0;
      game.frozenUntil = 0; thaw();
      sample = { x: event.clientX, y: event.clientY, time: performance.now() };
    });
    listen(el, 'pointermove', event => {
      if (event.pointerId !== pointerId) return;
      const now = performance.now(), dt = Math.max((now - sample.time) / 1000, 1 / 240);
      const dx = event.clientX - sample.x, dy = event.clientY - sample.y;
      game.x += dx; game.y += dy;
      game.vx = Math.max(-1800, Math.min(1800, dx / dt));
      game.vy = Math.max(-1800, Math.min(1800, dy / dt));
      sample = { x: event.clientX, y: event.clientY, time: now };
    });
    listen(el, 'pointerup', event => release(event));
    listen(el, 'pointercancel', event => release(event, true));
    listen(el, 'lostpointercapture', event => { if (pointerId !== null) release(event, true); });
    listen(el, 'keydown', event => {
      if ((event.key === 'Enter' || event.key === ' ') && !event.repeat) { event.preventDefault(); hit(); }
    });
    listen(window, 'keydown', event => {
      if (performance.now() >= game.frozenUntil) return;
      if (event.key === 'Escape') { game.frozenUntil = 0; thaw(); }
      else if (event.target !== el) { event.preventDefault(); event.stopImmediatePropagation(); }
    }, { capture: true });
    listen(window, 'blur', () => {
      game.pointer.active = false; game.dragging = false; game.vx = game.vy = 0;
      if (pointerId !== null) release({pointerId}, true);
      game.frozenUntil = 0; thaw();
    });

    function step(now) {
      const caught = !document.hidden && game.advance((now - last) / 1000, now, innerWidth, innerHeight);
      last = now;
      if (caught) {
        savedInert = app.inert; app.inert = true; notice.hidden = false;
        document.body.classList.add('tung-frozen');
        shakeUntil = now + 450; onCatch();
      }
      if (now >= game.frozenUntil) thaw();
      document.body.classList.toggle('screen-shake', now < shakeUntil && !reducedMotion);
      const dancing = now < game.danceUntil;
      el.dataset.dancing = String(dancing);
      el.dataset.dragging = String(game.dragging);
      if (game.pointer.active && !dancing) facing = game.pointer.x > game.x + 45 ? 1 : -1;
      const beat = dancing && !reducedMotion ? Math.sin(now / 85) : 0;
      const jump = dancing && !reducedMotion ? -Math.abs(Math.sin(now / 110)) * 20 : 0;
      el.style.transform = `translate(${game.x}px,${game.y + jump}px) rotate(${beat * 22}deg) scaleX(${facing})`;
      hud.textContent = dancing ? '🕺 DANCE MODE! You broke Tung Tung.' :
        game.hits.length ? `🥊 ${game.hits.length}/20 hits · keep going!` : 'Grab & throw Tung Tung · 20 hits in 5s = dance';
      raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf); controller.abort(); thaw();
      document.body.classList.remove('screen-shake');
      el.remove(); hud.remove(); notice.remove();
    };
  }
  const api = { Chase, mount };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else globalThis.TungGame = api;
})();
