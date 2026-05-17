
const $ = id => document.getElementById(id);
const token = () => localStorage.getItem("token") || "";
const api = (url, options={}) => {
  const sep = url.includes("?") ? "&" : "?";
  const full = token() ? url + sep + "token=" + encodeURIComponent(token()) : url;
  return fetch(full, {headers:{"Content-Type":"application/json",...(options.headers||{})},...options});
};

async function login(){
  const res = await fetch("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:$("loginUser").value,password:$("loginPass").value})});
  const d = await res.json();
  if(!res.ok){alert(d.detail||"登录失败");return;}
  localStorage.setItem("token", d.token); localStorage.setItem("role", d.role); localStorage.setItem("username", d.username);
  showApp();
}
function logout(){localStorage.clear();location.reload();}
function showApp(){ $("login").classList.add("hidden"); $("app").classList.remove("hidden"); $("userInfo").innerText = `${localStorage.username} · ${localStorage.role}`; calc(); }
if(token()) showApp();

document.querySelectorAll(".nav[data-tab]").forEach(btn=>{
  btn.onclick=()=>{
    document.querySelectorAll(".nav,.tab").forEach(x=>x.classList.remove("active"));
    btn.classList.add("active"); $(btn.dataset.tab).classList.add("active");
    if(btn.dataset.tab==="ops") loadOps();
    if(btn.dataset.tab==="inventory") loadInventory();
    if(btn.dataset.tab==="purchase") loadPurchases();
    if(btn.dataset.tab==="listing") loadListings();
    if(btn.dataset.tab==="aiProductUpload") loadProductAssets();
    if(btn.dataset.tab==="ali1688") load1688Candidates();
    if(btn.dataset.tab==="employees") loadEmployees();
    if(btn.dataset.tab==="aiAssistant") loadChatGPTSettings();
    if(btn.dataset.tab==="customerService") loadCustomerMessages();
    if(btn.dataset.tab==="ozonSync"){setDefaultSyncDates();loadOzonOrders();}
  };
});

const fields=["month","sku","product_name","fulfillment","purchase_cost_cny","weight_kg","domestic_shipping_cny","package_cost_cny","ad_cost_cny","ozon_price_rub","exchange_rate"];
function payload(){let p={};fields.forEach(f=>{let e=$(f);p[f]=e.type==="number"?Number(e.value||0):e.value});return p;}
async function calc(){
  if(!$("product_name")) return;
  const res = await fetch("/api/calc",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload())});
  const d = await res.json();
  $("category").innerText=d.category;$("commission_rate").innerText=(d.commission_rate*100).toFixed(2)+"%";$("logistics_channel").innerText=d.logistics_channel;
  $("logistics_fee").innerText="¥"+d.logistics_fee.toFixed(2);$("total_cost").innerText="¥"+d.total_cost.toFixed(2);$("net_profit").innerText="¥"+d.net_profit.toFixed(2);$("profit_rate").innerText=(d.profit_rate*100).toFixed(2)+"%";
}
fields.forEach(f=>setTimeout(()=>$(f)?.addEventListener("input",calc),0));
$("saveBtn").onclick=async()=>{await fetch("/api/products",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload())});alert("已保存");loadOps();};

function money(v){return "¥"+Number(v||0).toFixed(2)} function pct(v){return (Number(v||0)*100).toFixed(2)+"%"}
async function loadOps(){let r=await fetch("/api/operations");let rows=await r.json();let h=["月份","订单数","销售额","退款","广告费","采购成本","物流成本","平台费用","净利润","净利率"];let b=rows.map(x=>`<tr><td>${x.month}</td><td>${x.orders}</td><td>${money(x.sales)}</td><td>${money(x.refund)}</td><td>${money(x.ad_cost)}</td><td>${money(x.purchase_cost)}</td><td>${money(x.logistics_cost)}</td><td>${money(x.platform_fee)}</td><td>${money(x.net_profit)}</td><td>${pct(x.profit_rate)}</td></tr>`).join("");$("opsTable").innerHTML=`<thead><tr>${h.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${b}</tbody>`}
async function saveRefund(){await fetch("/api/refunds",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({month:$("refundMonth").value,amount_cny:Number($("refundAmount").value||0)})});loadOps();}

async function saveInventory(){await api("/api/inventory",{method:"POST",body:JSON.stringify({sku:$("inv_sku").value,product_name:$("inv_name").value,quantity:Number($("inv_qty").value||0),safety_stock:Number($("inv_safe").value||0),warehouse:$("inv_wh").value})});loadInventory();}
async function loadInventory(){let r=await api("/api/inventory");let rows=await r.json();let h=["SKU","商品","库存","安全库存","仓库","状态"];let b=rows.map(x=>`<tr><td>${x.sku}</td><td>${x.product_name}</td><td>${x.quantity}</td><td>${x.safety_stock}</td><td>${x.warehouse}</td><td>${x.quantity<=x.safety_stock?"需补货":"正常"}</td></tr>`).join("");$("inventoryTable").innerHTML=`<thead><tr>${h.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${b}</tbody>`}

async function savePurchase(){await api("/api/purchases",{method:"POST",body:JSON.stringify({sku:$("pur_sku").value,product_name:$("pur_name").value,supplier:$("pur_supplier").value,quantity:Number($("pur_qty").value||0),unit_cost_cny:Number($("pur_unit").value||0),status:$("pur_status").value})});loadPurchases();}
async function loadPurchases(){let r=await api("/api/purchases");let rows=await r.json();let h=["SKU","商品","供应商","数量","单价","总价","状态"];let b=rows.map(x=>`<tr><td>${x.sku}</td><td>${x.product_name}</td><td>${x.supplier}</td><td>${x.quantity}</td><td>${money(x.unit_cost_cny)}</td><td>${money(x.total_cost_cny)}</td><td>${x.status}</td></tr>`).join("");$("purchaseTable").innerHTML=`<thead><tr>${h.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${b}</tbody>`}

async function createListing(){let res=await api("/api/ozon/listings",{method:"POST",body:JSON.stringify({product_name:$("list_name").value,category:$("list_category").value,brand:$("list_brand").value,price_rub:Number($("list_price").value||0),weight_kg:Number($("list_weight").value||0),description:$("list_desc").value,images:[]})});let d=await res.json();$("ruTitle").innerText=d.ru_title||"-";loadListings();}
async function loadListings(){let r=await api("/api/ozon/listings");let rows=await r.json();let h=["中文名","俄语标题","类目","价格₽","状态"];let b=rows.map(x=>`<tr><td>${x.product_name}</td><td>${x.ru_title}</td><td>${x.category}</td><td>${x.price_rub}</td><td>${x.status}</td></tr>`).join("");$("listingTable").innerHTML=`<thead><tr>${h.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${b}</tbody>`}

async function search1688(){let r=await api("/api/1688/search",{method:"POST",body:JSON.stringify({keyword:$("ali_keyword").value,limit:20})});let d=await r.json();$("aliResult").innerHTML=`${d.message}<br><a target="_blank" href="${d.search_url}">打开1688搜索结果</a>`}

function setDefaultSyncDates(){let t=new Date(),p=new Date();p.setDate(t.getDate()-7);if(!$("sync_to").value)$("sync_to").value=t.toISOString().slice(0,10);if(!$("sync_from").value)$("sync_from").value=p.toISOString().slice(0,10);}
async function saveOzonSettings(){await fetch("/api/ozon/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({client_id:$("ozon_client_id").value,api_key:$("ozon_api_key").value,warehouse_id:""})});alert("已保存Ozon API配置");}
async function testOzon(){await saveOzonSettings();let r=await fetch("/api/ozon/test",{method:"POST"});alert(r.ok?"连接成功":"连接失败，请检查API Key");}
async function syncOzonOrders(){let r=await fetch("/api/ozon/sync-orders",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({date_from:$("sync_from").value,date_to:$("sync_to").value,source:$("sync_source").value,limit:100})});let d=await r.json();alert(r.ok?`同步完成：${d.synced_items}条`:"同步失败："+JSON.stringify(d));loadOzonOrders();}
async function loadOzonOrders(){let r=await fetch("/api/ozon/orders");let rows=await r.json();let h=["月份","订单号","状态","商品","SKU","数量","价格₽"];let b=rows.map(x=>`<tr><td>${x.month}</td><td>${x.posting_number}</td><td>${x.status}</td><td>${x.product_name}</td><td>${x.sku}</td><td>${x.quantity}</td><td>${x.price_rub}</td></tr>`).join("");$("ozonOrdersTable").innerHTML=`<thead><tr>${h.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${b}</tbody>`}

async function addEmployee(){await api("/api/employees",{method:"POST",body:JSON.stringify({username:$("emp_user").value,password:$("emp_pass").value,role:$("emp_role").value,is_active:1})});loadEmployees();}
async function loadEmployees(){let r=await api("/api/employees");let rows=await r.json();let h=["账号","角色","状态","创建时间"];let b=Array.isArray(rows)?rows.map(x=>`<tr><td>${x.username}</td><td>${x.role}</td><td>${x.is_active?"启用":"停用"}</td><td>${x.created_at}</td></tr>`).join(""):"<tr><td colspan='4'>仅管理员可查看</td></tr>";$("employeesTable").innerHTML=`<thead><tr>${h.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${b}</tbody>`}


async function loadChatGPTSettings(){
  const r = await api("/api/ai/settings");
  const d = await r.json();
  if(d.model) $("openai_model").value = d.model;
  if(d.image_model && $("openai_image_model")) $("openai_image_model").value = d.image_model;
}

async function saveChatGPTSettings(){
  if(!$("openai_api_key").value){
    alert("请填写 OpenChatGPT API Key");
    return;
  }
  const r = await api("/api/ai/settings", {
    method:"POST",
    body:JSON.stringify({
      api_key:$("openai_api_key").value,
      model:$("openai_model").value,
      image_model:$("openai_image_model").value
    })
  });
  alert(r.ok ? "ChatGPT配置已保存" : "保存失败");
}

async function generateChatGPTTitle(){
  const r = await api("/api/ai/ru-title", {
    method:"POST",
    body:JSON.stringify({
      product_name:$("ai_product_name").value,
      category:$("ai_category").value,
      keywords:$("ai_keywords").value
    })
  });
  const d = await r.json();
  if(!r.ok){ alert(d.detail || JSON.stringify(d)); return; }
  $("aiTitleResult").innerText = d.ru_title;
}

async function generateChatGPTListing(){
  const r = await api("/api/ai/listing", {
    method:"POST",
    body:JSON.stringify({
      product_name:$("ai_product_name").value,
      category:$("ai_category").value,
      selling_points:$("ai_keywords").value,
      price_rub:Number($("ai_price").value||0)
    })
  });
  const d = await r.json();
  if(!r.ok){ alert(d.detail || JSON.stringify(d)); return; }
  $("aiAnswer").innerText = d.listing;
}

async function askChatGPT(){
  const r = await api("/api/ai/chat", {
    method:"POST",
    body:JSON.stringify({
      message:$("aiMessage").value,
      context_type:"erp_chat"
    })
  });
  const d = await r.json();
  if(!r.ok){ alert(d.detail || JSON.stringify(d)); return; }
  $("aiAnswer").innerText = d.answer;
}


async function saveCustomerSettings(){
  const r = await api("/api/customer/settings", {
    method:"POST",
    body:JSON.stringify({
      ozon_chat_list_path:$("cs_list_path").value,
      ozon_chat_send_path:$("cs_send_path").value,
      auto_ai_reply:1,
      allow_direct_ozon_send:1
    })
  });
  alert(r.ok ? "客服API配置已保存" : "保存失败");
}

async function addLocalCustomerMessage(){
  if(!$("cs_message").value){ alert("请先填写客户问题"); return; }
  const r = await api("/api/customer/messages", {
    method:"POST",
    body:JSON.stringify({
      platform:"Ozon",
      chat_id:"",
      order_id:$("cs_order").value,
      customer_name:$("cs_customer").value,
      product_name:$("cs_product").value,
      message_text:$("cs_message").value,
      status:"未回复"
    })
  });
  const d = await r.json();
  if(!r.ok){ alert(d.detail || JSON.stringify(d)); return; }
  $("reply_message_id").value = d.id;
  $("reply_text").value = d.ai_reply;
  loadCustomerMessages();
}

async function loadCustomerMessages(){
  const r = await api("/api/customer/messages");
  const rows = await r.json();
  const h = ["ID","平台","状态","订单号","商品","客户问题","中文翻译","ChatGPT回复"];
  const b = Array.isArray(rows) ? rows.map(x=>`<tr onclick="selectCustomerMessage(${x.id})">
    <td>${x.id}</td><td>${x.platform||""}</td><td>${x.status||""}</td><td>${x.order_id||""}</td><td>${x.product_name||""}</td>
    <td>${x.message_text||""}</td><td>${x.translated_text||""}</td><td>${x.ai_reply||""}</td>
  </tr>`).join("") : `<tr><td colspan="8">${JSON.stringify(rows)}</td></tr>`;
  $("customerMessagesTable").innerHTML = `<thead><tr>${h.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${b}</tbody>`;
}

async function selectCustomerMessage(id){
  const r = await api("/api/customer/messages");
  const rows = await r.json();
  const item = rows.find(x=>x.id===id);
  if(item){
    $("reply_message_id").value = item.id;
    $("reply_text").value = item.ai_reply || item.reply_text || "";
  }
}

async function regenCustomerChatGPTReply(){
  if(!$("reply_message_id").value){ alert("请先选择消息ID"); return; }
  const r = await api("/api/customer/ai-reply", {
    method:"POST",
    body:JSON.stringify({message_id:Number($("reply_message_id").value),tone:"礼貌专业"})
  });
  const d = await r.json();
  if(!r.ok){ alert(d.detail || JSON.stringify(d)); return; }
  $("reply_text").value = d.ai_reply;
  loadCustomerMessages();
}

async function saveCustomerReply(sendToOzon){
  if(!$("reply_message_id").value || !$("reply_text").value){ alert("请选择消息并填写回复"); return; }
  const r = await api("/api/customer/reply", {
    method:"POST",
    body:JSON.stringify({
      message_id:Number($("reply_message_id").value),
      reply_text:$("reply_text").value,
      send_to_ozon:sendToOzon
    })
  });
  const d = await r.json();
  if(!r.ok){ alert(d.detail || JSON.stringify(d)); return; }
  alert(sendToOzon ? "已发送/保存回复" : "已保存回复");
  loadCustomerMessages();
}

async function syncOzonCustomerMessages(){
  const r = await api("/api/customer/sync-ozon", {method:"POST"});
  const d = await r.json();
  if(!r.ok){ alert(d.detail || JSON.stringify(d)); return; }
  alert("同步完成：" + d.synced + "条");
  loadCustomerMessages();
}


async function smartSearch1688(){
  if(!$("ali_keyword").value){ alert("请先输入采购关键词"); return; }
  const r = await api("/api/1688/smart-search", {
    method:"POST",
    body:JSON.stringify({
      keyword:$("ali_keyword").value,
      target_price_rub:Number($("ali_target_price").value||0),
      target_weight_kg:Number($("ali_weight").value||0),
      max_purchase_price_cny:Number($("ali_max_price").value||0),
      min_profit_rate:Number($("ali_min_profit").value||0.25),
      limit:20
    })
  });
  const d = await r.json();
  if(!r.ok){ alert(d.detail || JSON.stringify(d)); return; }
  $("aliBest").innerText = d.best ? `${d.best.title}｜评分 ${d.best.ai_score}｜预估利润率 ${(d.best.estimated_profit_rate*100).toFixed(2)}%` : "-";
  $("aliResult").innerHTML = `${d.notice}<br><a target="_blank" href="${d.search_url}">打开1688真实搜索页</a>`;
  render1688Candidates(d.items || []);
}

async function load1688Candidates(){
  const r = await api("/api/1688/candidates");
  const rows = await r.json();
  render1688Candidates(Array.isArray(rows) ? rows : []);
}

function render1688Candidates(rows){
  const h = ["评分","商品标题","采购价","运费","销量","复购率","店铺评分","地区","预估利润","预估利润率","推荐理由","链接"];
  const b = rows.map(x=>`<tr>
    <td>${Number(x.ai_score||0).toFixed(2)}</td>
    <td>${x.title||""}</td>
    <td>¥${Number(x.price_cny||0).toFixed(2)}</td>
    <td>¥${Number(x.shipping_cny||0).toFixed(2)}</td>
    <td>${x.monthly_sales||0}</td>
    <td>${Number(x.repurchase_rate||0).toFixed(1)}%</td>
    <td>${Number(x.shop_score||0).toFixed(1)}</td>
    <td>${x.location||""}</td>
    <td>¥${Number(x.estimated_profit||0).toFixed(2)}</td>
    <td>${(Number(x.estimated_profit_rate||0)*100).toFixed(2)}%</td>
    <td>${x.reason||""}</td>
    <td>${x.url ? `<a target="_blank" href="${x.url}">打开</a>` : ""}</td>
  </tr>`).join("");
  $("aliCandidatesTable").innerHTML = `<thead><tr>${h.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${b}</tbody>`;
}


function productAssetPayload(){
  return {
    product_name:$("asset_product_name").value,
    category:$("asset_category").value,
    material:$("asset_material").value,
    size:$("asset_size").value,
    color:$("asset_color").value,
    target_customer:$("asset_customer").value,
    selling_points:$("asset_points").value
  };
}

async function generateProductCopy(){
  if(!$("asset_product_name").value){ alert("请先填写商品名称"); return; }
  $("productCopyResult").innerText = "ChatGPT正在生成商品特点、俄语标题和Ozon描述...";
  const r = await api("/api/ai/product-copy", {
    method:"POST",
    body:JSON.stringify(productAssetPayload())
  });
  const d = await r.json();
  if(!r.ok){ alert(d.detail || JSON.stringify(d)); return; }
  $("productCopyResult").innerText = d.content;
  loadProductAssets();
}

async function generateProductImage(){
  if(!$("asset_product_name").value){ alert("请先填写商品名称"); return; }
  $("productCopyResult").innerText = "ChatGPT 正在生成商品图片，可能需要几十秒到2分钟...";
  const r = await api("/api/ai/product-image", {
    method:"POST",
    body:JSON.stringify({
      product_name:$("asset_product_name").value,
      category:$("asset_category").value,
      selling_points:$("asset_points").value,
      image_type:$("asset_image_type").value,
      size:$("asset_image_size").value,
      quality:$("asset_image_quality").value
    })
  });
  const d = await r.json();
  if(!r.ok){ alert(d.detail || JSON.stringify(d)); $("productCopyResult").innerText = ""; return; }
  $("productImageResult").src = d.image_url;
  $("productCopyResult").innerText = "图片已生成。生成提示词：\n" + d.prompt;
  loadProductAssets();
}

async function loadProductAssets(){
  const r = await api("/api/ai/product-assets");
  const rows = await r.json();
  const h = ["商品","类目","类型","图片","创建时间"];
  const b = Array.isArray(rows) ? rows.map(x=>`<tr>
    <td>${x.product_name||""}</td>
    <td>${x.category||""}</td>
    <td>${x.asset_type||""}</td>
    <td>${x.image_path ? `<a target="_blank" href="${x.image_path}">查看图片</a>` : "文案"}</td>
    <td>${x.created_at||""}</td>
  </tr>`).join("") : `<tr><td colspan="5">${JSON.stringify(rows)}</td></tr>`;
  $("productAssetsTable").innerHTML = `<thead><tr>${h.map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${b}</tbody>`;
}
