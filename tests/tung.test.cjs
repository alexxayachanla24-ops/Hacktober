const { test } = require('node:test');
const assert = require('node:assert/strict');
const { Chase } = require('../static/tung.js');

test('Tung moves toward the cursor and freezes the player on contact with a cooldown', () => {
  const game = new Chase();
  game.pointer = {x:400, y:200, active:true};
  game.advance(0.05, 100, 800, 600);
  assert.ok(game.x > 24);
  game.pointer = {x:game.x + 45, y:game.y + 45, active:true};
  assert.equal(game.advance(0.016, 200, 800, 600), true);
  assert.equal(game.frozenUntil, 1100);
  assert.equal(game.advance(0.016, 300, 800, 600), false);
  assert.equal(game.advance(0.016, 1200, 800, 600), false);
  assert.equal(game.advance(0.016, 3700, 800, 600), true);
});

test('twenty hits in a rolling five-second window trigger a six-second dance', () => {
  const game = new Chase();
  for(let i=0;i<19;i++) assert.equal(game.hit(i*240), false);
  assert.equal(game.hit(4560), true);
  assert.equal(game.danceUntil, 10560);
  assert.equal(game.hits.length, 0);
  assert.equal(game.hit(5000), false);
  assert.equal(game.danceUntil, 10560);
  game.pointer = {x:600, y:400, active:true};
  const x = game.x;
  game.advance(0.05, 5000, 800, 600);
  assert.equal(game.x, x);
  game.advance(0.05, 10600, 800, 600);
  assert.ok(game.x > x);
});

test('old hits expire instead of accumulating across the session', () => {
  const game = new Chase();
  for(let i=0;i<20;i++) assert.equal(game.hit(i*300), false);
  assert.equal(game.danceUntil, 0);
  game.advance(0.016, 12000, 800, 600);
  assert.equal(game.hits.length, 0);
});

test('throwing carries momentum, bounces off edges, and temporarily suspends chase', () => {
  const game = new Chase();
  game.x = 700; game.y = 100; game.vx = 1000; game.flightUntil = 2000;
  game.pointer = {x:0, y:0, active:true};
  game.advance(0.05, 100, 800, 600);
  assert.equal(game.x, 710);
  assert.ok(game.vx < 0);
  const speed = Math.abs(game.vx);
  game.advance(0.05, 150, 800, 600);
  assert.ok(game.x < 710);
  assert.ok(Math.abs(game.vx) < speed);
});

test('dragging prevents captures and resize keeps Tung inside the viewport', () => {
  const game = new Chase();
  game.dragging = true;
  game.pointer = {x:69, y:185, active:true};
  assert.equal(game.advance(0.05, 100, 800, 600), false);
  game.x = 900; game.y = 900;
  game.advance(0.05, 200, 390, 700);
  assert.equal(game.x, 300);
  assert.equal(game.y, 570);
  game.advance(0.05, 250, 50, 50);
  assert.equal(game.x, 0);
  assert.equal(game.y, 0);
});
