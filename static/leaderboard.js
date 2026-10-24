(() => {
  const $ = selector => document.querySelector(selector);
  let loading = false;
  function duration(seconds) {
    if (seconds === null || !Number.isFinite(seconds)) return '—';
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`;
    return `${Math.floor(seconds / 86400)}d ${Math.floor(seconds % 86400 / 3600)}h`;
  }
  function render(data) {
    $('#total-roommates').textContent = data.totals.roommates;
    $('#total-completed').textContent = data.totals.completed;
    $('#total-pending').textContent = data.totals.pending;
    $('#empty').hidden = data.roommates.length !== 0;
    $('#scores').hidden = data.roommates.length === 0;
    const champion = $('#champion');
    const leader = data.roommates[0];
    champion.hidden = !leader || leader.points === 0;
    champion.replaceChildren();
    if (leader && leader.points > 0) {
      const name = document.createElement('strong');
      name.textContent = `👑 ${leader.target}`;
      champion.append(name, `${leader.points} points · Household MVP. The mold fears you.`);
    }
    const rows = document.createDocumentFragment();
    data.roommates.forEach(member => {
      const row = document.createElement('tr');
      const values = [member.rank <= 3 ? ['🥇', '🥈', '🥉'][member.rank - 1] + ' ' + member.rank : member.rank,
        member.target, member.points, member.completed, member.pending, member.on_time,
        duration(member.fastest_seconds), duration(member.average_seconds)];
      values.forEach((value, index) => {
        const cell = document.createElement('td');
        cell.textContent = value;
        if (index === 1) cell.className = 'name';
        if (index === 2) cell.className = 'points';
        if (index === 4 && member.overdue) {
          const overdue = document.createElement('span');
          overdue.className = 'overdue'; overdue.textContent = `${member.overdue} overdue`;
          cell.append(overdue);
        }
        row.append(cell);
      });
      rows.append(row);
    });
    $('#rows').replaceChildren(rows);
  }
  async function load() {
    if (loading) return;
    loading = true;
    $('#refresh').disabled = true;
    try {
      const response = await fetch('/api/leaderboard', {signal: AbortSignal.timeout(10000)});
      if (!response.ok) throw new Error(`Server returned ${response.status}`);
      const data = await response.json();
      render(data);
      $('#status').textContent = 'Scores updated ' + new Date(data.updated_at * 1000).toLocaleTimeString();
    } catch (error) {
      $('#status').textContent = 'Could not refresh scores. Last loaded scores are kept. Use Refresh scores to try again.';
    } finally {
      loading = false;
      $('#refresh').disabled = false;
    }
  }
  $('#refresh').addEventListener('click', load);
  setInterval(() => { if (!document.hidden) load(); }, 10000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
  load();
})();
