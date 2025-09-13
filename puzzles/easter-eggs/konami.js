(() => {
  const target = [38,38,40,40,37,39,37,39,66,65];
  const pressed = [];
  const egg = document.getElementById('egg');
  const close = document.getElementById('close');
  const open = () => { if (egg) egg.style.display = 'flex'; };
  const hide = () => { if (egg) egg.style.display = 'none'; };

  window.addEventListener('keydown', (e) => {
    pressed.push(e.keyCode);
    if (pressed.length > target.length) pressed.shift();
    if (target.every((v,i)=>pressed[i]===v)) open();
  });

  if (egg) egg.addEventListener('click', (e)=>{ if (e.target===egg) hide(); });
  if (close) close.addEventListener('click', hide);
})();
