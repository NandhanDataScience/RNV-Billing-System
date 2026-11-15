const cart = new Map();
const rupees = n => '₹' + Number(n).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
document.getElementById('today').textContent = new Date().toLocaleDateString('en-IN',{weekday:'short',day:'2-digit',month:'short',year:'numeric'});
function addProduct(id){
 const card=document.querySelector(`.product-card[data-id="${id}"]`);
 const stock=Number(card.dataset.stock);
 const old=cart.get(id);
 if((old?.quantity||0)>=stock){alert('You have reached the available stock for this product.');return}
 if(old) old.quantity++; else cart.set(id,{id,name:card.querySelector('h3').textContent,price:Number(card.dataset.price),quantity:1,stock});
 renderCart();
}
function changeQty(id,delta){
 const item=cart.get(id); if(!item)return;
 item.quantity+=delta;
 if(item.quantity<=0)cart.delete(id);
 else if(item.quantity>item.stock){item.quantity=item.stock;alert('Stock limit reached.')}
 renderCart();
}
function renderCart(){
 const root=document.getElementById('bill-items');
 if(!cart.size){root.innerHTML='<div class="bill-empty"><span>＋</span><p>Your bill is empty</p><small>Add products from the catalogue</small></div>'}
 else root.innerHTML=[...cart.values()].map(i=>`<div class="bill-line"><div class="bill-line-info"><strong>${escapeHtml(i.name)}</strong><small>${rupees(i.price)} each</small></div><div class="qty-control"><button onclick="changeQty(${i.id},-1)">−</button><b>${i.quantity}</b><button onclick="changeQty(${i.id},1)">+</button></div><strong class="line-price">${rupees(i.price*i.quantity)}</strong></div>`).join('');
 const total=[...cart.values()].reduce((s,i)=>s+i.price*i.quantity,0);
 document.getElementById('subtotal').textContent=rupees(total);
 document.getElementById('grand-total').textContent=rupees(total);
 document.getElementById('checkout').disabled=!cart.size;
}
function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function checkout(){
 if(!cart.size)return;
 const button=document.getElementById('checkout');button.disabled=true;button.textContent='Saving sale...';
 try{
  const response=await fetch('/checkout',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':window.CSRF_TOKEN},body:JSON.stringify({customer:document.getElementById('customer').value,items:[...cart.values()].map(i=>({id:i.id,quantity:i.quantity}))})});
  const result=await response.json();
  if(!response.ok||!result.ok)throw new Error(result.message||'Could not save sale.');
  alert(`Sale completed!\nInvoice: ${result.invoice}\nTotal: ${rupees(result.total)}`);
  window.location.reload();
 }catch(e){alert(e.message);button.disabled=false;button.innerHTML='Complete sale <span>→</span>'}
}
const search=document.getElementById('search');
search.addEventListener('input',()=>{const q=search.value.toLowerCase();document.querySelectorAll('.product-card').forEach(c=>c.hidden=!c.dataset.name.includes(q))});
document.querySelectorAll('.category-pill').forEach(b=>b.addEventListener('click',()=>{
 document.querySelectorAll('.category-pill').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');
 document.querySelectorAll('.product-card').forEach(c=>c.hidden=!(b.dataset.category==='all'||c.dataset.category===b.dataset.category));
}));
renderCart();
