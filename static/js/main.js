// FarmKart - Main JS
const IS_LOGGED_IN = document.body.dataset.loggedIn === 'true';
let cartState = {};

console.log('FarmKart JS loaded. Logged in:', IS_LOGGED_IN);

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash').forEach(f => {
    setTimeout(() => { f.style.opacity='0'; f.style.transition='all 0.4s'; setTimeout(()=>f.remove(),400); }, 3500);
  });
  if (IS_LOGGED_IN) fetchCartState();
});

async function fetchCartState() {
  try {
    const res = await fetch('/api/cart-items');
    if (!res.ok) return;
    const data = await res.json();
    cartState = data.items;
    updateAllButtons();
    updateCartBadgeFromState();
  } catch(e) { console.error('fetchCartState error:', e); }
}

function updateAllButtons() {
  document.querySelectorAll('.add-btn-wrap').forEach(wrap => {
    const pid = parseInt(wrap.dataset.pid);
    if (cartState[pid] > 0) renderQty(wrap, pid, cartState[pid]);
    else renderAdd(wrap, pid);
  });
}

function renderAdd(wrap, pid) {
  wrap.innerHTML = `<button class="btn btn-primary btn-sm" onclick="handleAdd(${pid}, this)">+ Add</button>`;
}

function renderQty(wrap, pid, qty) {
  wrap.innerHTML = `
    <div class="qty-ctrl">
      <button class="qty-btn-round" onclick="handleQty(${pid},-1,this)">−</button>
      <span class="qty-num" id="qn-${pid}">${qty}</span>
      <button class="qty-btn-round" onclick="handleQty(${pid},1,this)">+</button>
    </div>`;
}

async function handleAdd(pid, btn) {
  console.log('handleAdd called, pid:', pid, 'logged in:', IS_LOGGED_IN);

  if (!IS_LOGGED_IN) {
    showToast('Please login first', 'error');
    setTimeout(() => window.location.href = '/login', 1200);
    return;
  }

  const wrap = btn.closest('.add-btn-wrap');

  // Show qty immediately (optimistic)
  cartState[pid] = 1;
  renderQty(wrap, pid, 1);
  updateCartBadgeFromState();
  showToast('Added to cart! 🛒', 'success');

  try {
    const fd = new FormData();
    fd.append('product_id', pid);
    fd.append('quantity', 1);

    const res = await fetch('/cart/add', {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: fd
    });

    console.log('cart/add response status:', res.status, 'redirected:', res.redirected);

    if (res.redirected) {
      console.log('Redirected to:', res.url);
      // Session issue — reload to login
      window.location.href = '/login';
      return;
    }

    const text = await res.text();
    console.log('Response text:', text);

    let data;
    try { data = JSON.parse(text); } catch(e) {
      console.error('JSON parse failed:', text);
      return;
    }

    if (!data.success) {
      console.error('Server returned success:false');
      delete cartState[pid];
      renderAdd(wrap, pid);
      updateCartBadgeFromState();
    }

  } catch(e) {
    console.error('fetch error:', e);
    // Hard fallback: form submit
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/cart/add';
    form.innerHTML = `<input type="hidden" name="product_id" value="${pid}"><input type="hidden" name="quantity" value="1">`;
    document.body.appendChild(form);
    form.submit();
  }
}

async function handleQty(pid, delta, btn) {
  const wrap = btn.closest('.add-btn-wrap');
  const current = cartState[pid] || 0;
  const newQty = current + delta;

  if (newQty <= 0) {
    delete cartState[pid];
    renderAdd(wrap, pid);
    updateCartBadgeFromState();
    try { await fetch(`/cart/remove-by-product/${pid}`, { method: 'POST' }); } catch(e) {}
    return;
  }

  cartState[pid] = newQty;
  const span = document.getElementById(`qn-${pid}`);
  if (span) span.textContent = newQty;
  updateCartBadgeFromState();

  try {
    const fd = new FormData();
    fd.append('product_id', pid);
    fd.append('new_qty', newQty);
    await fetch('/cart/update-qty', {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: fd
    });
  } catch(e) { console.error('update-qty error:', e); }
}

function updateCartBadgeFromState() {
  const total = Object.values(cartState).reduce((a, b) => a + b, 0);

  // Update navbar cart badge
  const badge = document.querySelector('.cart-badge');
  if (badge) {
    badge.textContent = total;
    badge.style.display = total > 0 ? 'inline-flex' : 'none';
  }

  // Update dashboard "Cart (N)" button
  const headerCount = document.getElementById('header-cart-count');
  if (headerCount) headerCount.textContent = total;
}

function showToast(msg, type = 'success') {
  document.querySelectorAll('.fk-toast').forEach(t => t.remove());
  const t = document.createElement('div');
  t.className = 'fk-toast';
  t.textContent = msg;
  t.style.cssText = `
    position:fixed;bottom:1.5rem;right:1.5rem;
    padding:.85rem 1.4rem;
    background:${type==='success'?'#166534':'#991b1b'};
    color:white;border-radius:10px;
    font-family:'DM Sans',sans-serif;font-size:.92rem;font-weight:500;
    box-shadow:0 6px 24px rgba(0,0,0,.18);
    z-index:9999;opacity:0;transform:translateY(16px);
    transition:all .25s ease;
  `;
  document.body.appendChild(t);
  requestAnimationFrame(() => { t.style.opacity='1'; t.style.transform='translateY(0)'; });
  setTimeout(() => { t.style.opacity='0'; t.style.transform='translateY(10px)'; setTimeout(()=>t.remove(),300); }, 2500);
}

async function initiatePayment(address) {
  if (!address.trim()) { showToast('Please enter delivery address','error'); return; }
  try {
    const res = await fetch('/create-order', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({address}) });
    const od = await res.json();
    const opts = {
      key:od.key, amount:od.amount, currency:od.currency,
      name:'FarmKart', description:'Fresh Farm Products', order_id:od.order_id,
      handler: async(r) => {
        const pr = await fetch('/payment-success', { method:'POST', headers:{'Content-Type':'application/json'},
          body:JSON.stringify({payment_id:r.razorpay_payment_id||'demo_'+Date.now(),address}) });
        const pd = await pr.json();
        if (pd.success) window.location.href = '/order-success/'+pd.order_id;
      },
      theme:{color:'#2d6a4f'},
      modal:{ondismiss:()=>{ if(confirm('Complete test order?')) completeDemoOrder(address); }}
    };
    if (typeof Razorpay!=='undefined') new Razorpay(opts).open();
    else completeDemoOrder(address);
  } catch(e) { showToast('Payment error','error'); }
}

async function completeDemoOrder(address) {
  const r = await fetch('/payment-success', { method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({payment_id:'demo_'+Date.now(),address}) });
  const d = await r.json();
  if (d.success) window.location.href = '/order-success/'+d.order_id;
}

function confirmDelete(form) { if(confirm('Delete this? Cannot be undone.')) form.submit(); }

document.querySelectorAll('.stat-value[data-value]').forEach(el => {
  const target = parseFloat(el.dataset.value); let cur=0; const step=target/40;
  const ti = setInterval(()=>{
    cur+=step; if(cur>=target){cur=target;clearInterval(ti);}
    el.textContent = el.dataset.value.includes('.')
      ? '₹'+cur.toLocaleString('en-IN',{maximumFractionDigits:0})
      : Math.round(cur).toLocaleString();
  },25);
});