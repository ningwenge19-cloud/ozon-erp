
const $ = id => document.getElementById(id);
let token = localStorage.getItem("token") || "";
let me = JSON.parse(localStorage.getItem("me") || "null");

function api(path, options={}){
  options.headers = {"Content-Type":"application/json", ...(options.headers||{})};
  if(token) options.headers.Authorization = "Bearer " + token;
  return fetch("https://web-production-dafbd.up.railway.app" + path, options);
}
function toast(msg){ $("toast").innerText=msg; $("toast").classList.remove("hidden"); setTimeout(()=>$("toast").classList.add("hidden"),2600); }
function showAuth(){ $("authPage").classList.remove("hidden"); $("app").classList.add("hidden"); }
function showApp(){ $("authPage").classList.add("hidden"); $("app").classList.remove("hidden"); }
function switchAuth(t){
  document.querySelectorAll(".auth-tabs button").forEach(b=>b.classList.remove("active"));
  event.target.classList.add("active");
  $("loginBox").classList.toggle("hidden", t!=="login");
  $("registerBox").classList.toggle("hidden", t!=="register");
}
async function login(){
  const r = await api("/api/auth/login",{method:"POST",body:JSON.stringify({account:$("loginAccount").value,password:$("loginPassword").value})});
  const d = await r.json(); if(!r.ok) return toast(d.detail||"登录失败");
  token=d.token; me=d.user; localStorage.setItem("token",token); localStorage.setItem("me",JSON.stringify(me)); init();
}
async function register(){
  const r = await api("/api/auth/register",{method:"POST",body:JSON.stringify({username:$("regUsername").value,email:$("regEmail").value,password:$("regPassword").value})});
  const d = await r.json(); if(!r.ok) return toast(d.detail||"注册失败");
  token=d.token; me=d.user; localStorage.setItem("token",token); localStorage.setItem("me",JSON.stringify(me)); init();
}
function logout(){ localStorage.clear(); token=""; me=null; showAuth(); }

document.querySelectorAll(".nav[data-tab]").forEach(btn=>{
  btn.onclick = () => {
    document.querySelectorAll(".nav").forEach(x=>x.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".page").forEach(x=>x.classList.remove("active"));
    $(btn.dataset.tab).classList.add("active");
    $("pageTitle").innerText = btn.innerText;
    loadAll();
  };
});

function isAdmin(){ return me && me.role === "admin"; }
function applyRoleUI(){
  $("userInfo").innerText = `${me.username} · ${me.role}`;
  document.querySelectorAll(".admin-only").forEach(x=>x.classList.toggle("hidden", !isAdmin()));
}
async function init(){
  if(!token) return showAuth();
  const r = await api("/api/me");
  if(!r.ok) return logout();
  me = await r.json(); localStorage.setItem("me", JSON.stringify(me));
  showApp(); applyRoleUI(); await loadAll();
}
async function loadAll(){
  if(!token) return;
  loadDashboard(); loadOrders(); loadProducts(); loadTickets(); loadAISettings();
  if(isAdmin()) loadAdmin();
}
function table(el, headers, rows){
  el.innerHTML = "<thead><tr>"+headers.map(h=>`<th>${h}</th>`).join("")+"</tr></thead><tbody>"+rows.join("")+"</tbody>";
}
async function loadDashboard(){
  const r = await api("/api/dashboard"); if(!r.ok) return;
  const d = await r.json();
  $("stOrders").innerText=d.orders; $("stSales").innerText=d.sales_rub; $("stProfit").innerText=d.profit_cny; $("stProducts").innerText=d.products;
  table($("recentOrders"), ["订单号","状态","商品","数量","售价₽","利润¥"], d.recent_orders.map(o=>`<tr><td>${o.order_no}</td><td><span class="badge">${o.status}</span></td><td>${o.product}</td><td>${o.quantity}</td><td>${o.price_rub}</td><td>${o.profit_cny}</td></tr>`));
}
function calcProfit(){
  const price=Number($("pfPrice").value||0), cost=Number($("pfCost").value||0), ship=Number($("pfShip").value||0), comm=Number($("pfComm").value||0.15);
  const revenue=price*0.078; const profit=revenue-cost-ship-revenue*comm; const rate=revenue?profit/revenue*100:0;
  $("profitResult").innerText = `收入约：¥${revenue.toFixed(2)}\n成本：¥${cost.toFixed(2)}\n物流：¥${ship.toFixed(2)}\n佣金：¥${(revenue*comm).toFixed(2)}\n预计利润：¥${profit.toFixed(2)}\n利润率：${rate.toFixed(1)}%`;
}
async function saveOzon(){
  const body={client_id:$("ozonClient").value,api_key:$("ozonKey").value,sync_type:$("ozonType").value};
  const r=await api("/api/ozon/settings",{method:"POST",body:JSON.stringify(body)}); toast(r.ok?"已保存":"保存失败");
}
async function syncDemoOrders(){
  const r=await api("/api/ozon/sync-demo",{method:"POST"}); const d=await r.json(); toast(r.ok?`已导入 ${d.imported} 条演示订单`:d.detail); loadOrders(); loadDashboard();
}
async function loadOrders(){
  const r=await api("/api/orders"); if(!r.ok) return;
  const rows=await r.json();
  table($("ordersTable"), ["月份","订单号","状态","商品","SKU","数量","售价₽","利润¥"], rows.map(o=>`<tr><td>${o.month}</td><td>${o.order_no}</td><td>${o.status}</td><td>${o.product}</td><td>${o.sku}</td><td>${o.quantity}</td><td>${o.price_rub}</td><td>${o.profit_cny}</td></tr>`));
}
async function addProduct(){
  const body={title:$("pdTitle").value,category:$("pdCategory").value,cost_cny:+$("pdCost").value||0,weight_kg:+$("pdWeight").value||0,price_rub:+$("pdPrice").value||0,stock:+$("pdStock").value||0};
  const r=await api("/api/products",{method:"POST",body:JSON.stringify(body)}); toast(r.ok?"商品已保存":"保存失败"); loadProducts(); loadDashboard();
}
async function loadProducts(){
  const r=await api("/api/products"); if(!r.ok) return;
  const rows=await r.json();
  table($("productsTable"), ["商品","类目","成本¥","重量kg","售价₽","库存","状态","操作"], rows.map(p=>`<tr><td>${p.title}</td><td>${p.category}</td><td>${p.cost_cny}</td><td>${p.weight_kg}</td><td>${p.price_rub}</td><td>${p.stock}</td><td>${p.status}</td><td><button onclick="delProduct(${p.id})">删除</button></td></tr>`));
}
async function delProduct(id){ await api("/api/products/"+id,{method:"DELETE"}); loadProducts(); }
async function loadAISettings(){
  const r=await api("/api/ai/settings"); if(!r.ok) return;
  const d=await r.json(); $("aiBase").value=d.base_url||""; $("aiModel").value=d.model||""; $("aiImage").value=d.image_model||"";
}
async function saveAISettings(){
  const body={api_key:$("aiKey").value,base_url:$("aiBase").value,model:$("aiModel").value,image_model:$("aiImage").value};
  const r=await api("/api/ai/settings",{method:"POST",body:JSON.stringify(body)}); const d=await r.json(); toast(r.ok?"AI配置已保存":d.detail||"保存失败");
}
async function askAI(){
  $("aiAnswer").innerText="豆包正在思考中...";
  const r=await api("/api/doubao/chat",{method:"POST",body:JSON.stringify({message:$("aiMsg").value})});
  const d=await r.json(); $("aiAnswer").innerText = r.ok ? d.answer : (d.detail || JSON.stringify(d,null,2));
}
async function generateListing(){
  $("listingResult").innerText="正在生成...";
  const body={product_name:$("lsName").value,category:$("lsCat").value,keywords:$("lsKeywords").value,price_rub:$("lsPrice").value};
  const r=await api("/api/ai/listing",{method:"POST",body:JSON.stringify(body)}); const d=await r.json();
  $("listingResult").innerText = r.ok ? d.listing : (d.detail || JSON.stringify(d,null,2));
}
async function addTicket(){
  const r=await api("/api/tickets",{method:"POST",body:JSON.stringify({customer:$("tkCustomer").value,message:$("tkMessage").value})});
  toast(r.ok?"已新增":"新增失败"); loadTickets();
}
async function loadTickets(){
  const r=await api("/api/tickets"); if(!r.ok) return;
  const rows=await r.json();
  $("ticketsList").innerHTML = rows.map(t=>`<div class="ticket"><b>${t.customer}</b> <small>${t.created_at}</small><p>${t.message}</p><button onclick="aiReply(${t.id})">豆包生成回复</button>${t.ai_reply?`<pre class="ai-box">${t.ai_reply}</pre>`:""}</div>`).join("");
}
async function aiReply(id){
  const r=await api(`/api/tickets/${id}/ai-reply`,{method:"POST"}); const d=await r.json(); toast(r.ok?"已生成回复":d.detail||"生成失败"); loadTickets();
}
async function loadAdmin(){
  const r=await api("/api/admin/overview"); if(r.ok){ const d=await r.json(); $("adUsers").innerText=d.users; $("adOrders").innerText=d.orders; $("adProducts").innerText=d.products; $("auditLogs").innerHTML=d.logs.map(l=>`<p><b>${l.action}</b> · ${l.username||"-"} · ${l.detail||""} <small>${l.created_at}</small></p>`).join("");}
  const u=await api("/api/admin/users"); if(u.ok){ const rows=await u.json(); table($("adminUsers"),["ID","用户名","邮箱","角色","状态","操作"], rows.map(x=>`<tr><td>${x.id}</td><td>${x.username}</td><td>${x.email}</td><td>${x.role}</td><td>${x.status}</td><td><button onclick="setRole(${x.id},'${x.role==='admin'?'user':'admin'}')">切换角色</button><button onclick="setStatus(${x.id},'${x.status==='active'?'disabled':'active'}')">启停</button></td></tr>`));}
}
async function setRole(id,role){ await api(`/api/admin/users/${id}/role`,{method:"POST",body:JSON.stringify({role})}); loadAdmin(); }
async function setStatus(id,status){ await api(`/api/admin/users/${id}/status`,{method:"POST",body:JSON.stringify({status})}); loadAdmin(); }
init();
