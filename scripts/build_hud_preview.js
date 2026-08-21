const fs = require("fs");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const templatePath = path.join(projectRoot, "templates", "index.html");
const standaloneOutputPath = path.join(projectRoot, "KOKUSAI_PREVIEW_HUD.html");

function renderAdminBlocks(source) {
  const blockPattern = /{%\s*(if\s+[^%]+|else|endif)\s*%}/g;
  const stack = [];
  const output = [];
  let cursor = 0;
  let active = true;

  for (const match of source.matchAll(blockPattern)) {
    if (active) output.push(source.slice(cursor, match.index));

    const command = match[1].trim();
    if (command.startsWith("if ")) {
      const conditionName = command.slice(3).trim();
      const condition = conditionName === "is_admin";
      stack.push({ parentActive: active, condition });
      active = active && condition;
    } else if (command === "else") {
      const current = stack[stack.length - 1];
      if (!current) throw new Error("Bloco Jinja com else sem if.");
      active = current.parentActive && !current.condition;
    } else {
      const current = stack.pop();
      if (!current) throw new Error("Bloco Jinja com endif sem if.");
      active = current.parentActive;
    }

    cursor = match.index + match[0].length;
  }

  if (stack.length) throw new Error("Bloco Jinja sem fechamento.");
  if (active) output.push(source.slice(cursor));
  return output.join("");
}

function renderExpression(expression) {
  const value = expression.trim();
  if (value === "csrf_token") return "kokusai-preview";
  if (value === "current_user.role") return "admin";
  if (value === "current_user.display_name") return "Kokusai";
  if (value.includes("if is_admin else")) {
    const firstValue = value.match(/^(["'])(.*?)\1\s+if\s+is_admin\s+else/);
    return firstValue ? firstValue[2] : "";
  }
  return "";
}

function renderTemplate(source) {
  let html = renderAdminBlocks(source);

  html = html.replace(
    /{{\s*url_for\('static',\s*filename='([^']+)'\)\s*}}/g,
    "static/$1",
  );
  html = html.replace(/{{\s*url_for\('[^']+'[^)]*\)\s*}}/g, "#");
  html = html.replace(/{{\s*([^}]+)\s*}}/g, (_, expression) => renderExpression(expression));
  html = html.replace(/\s*<link rel="preconnect" href="https:\/\/fonts\.[^"]+"[^>]*>/g, "");
  html = html.replace(/\s*<link href="https:\/\/fonts\.googleapis\.com[^"]+" rel="stylesheet">/g, "");
  html = html.replace(
    "<title>Kokusai | Compras, Vendas, Encomendas, Relatórios, Famílias, Metas e Craft</title>",
    "<title>Prévia da HUD | Kokusai</title>",
  );

  const previewStyles = `
  <style>
    .preview-mode-banner{
      position:fixed;
      right:18px;
      bottom:18px;
      z-index:9999;
      display:flex;
      align-items:center;
      gap:9px;
      padding:9px 12px;
      border:1px solid rgba(217,45,69,.28);
      border-radius:10px;
      background:rgba(13,14,17,.94);
      color:#d9dadd;
      box-shadow:0 14px 38px rgba(0,0,0,.34);
      backdrop-filter:blur(12px);
      font:700 11px/1.2 Inter,system-ui,sans-serif;
    }
    .preview-mode-banner::before{
      content:"";
      width:7px;
      height:7px;
      border-radius:50%;
      background:#d92d45;
      box-shadow:0 0 12px rgba(217,45,69,.55);
    }
    .preview-mode-banner small{color:#858a94;font-size:9px;font-weight:600}
    @media(max-width:520px){
      .preview-mode-banner{right:10px;bottom:10px;left:10px;justify-content:center}
    }
  </style>`;

  const previewBanner = `
  <div class="preview-mode-banner" role="status">
    Prévia visual <small>dados simulados · nada será salvo</small>
  </div>`;

  html = html.replace("</head>", `${previewStyles}\n</head>`);
  html = html.replace(/(<body[^>]*>)/, `$1${previewBanner}`);
  html = html.replace(
    /<script src="static\/js\/app\.js[^>]*><\/script>/,
    `${mockBackendScript()}\n  <script src="static/js/app.js?v=preview-hud"></script>`,
  );

  return html;
}

function mockBackendScript() {
  return `  <script>
    (() => {
      const families = [
        {id:"fam-ruptura",nome:"Ruptura",icone:"💥",mercado:"Aberto",responsavel_contato:"Larissa",preco_venda_para_familia:"L85 — R$ 165.000",preco_compra_da_familia:"Materiais conforme tabela",contato:"Contato reservado 01",contato_2:"Contato reservado 02",flyer_url:"static/images/flyers/leviata.webp",observacao:"Condições especiais para pedidos em quantidade."},
        {id:"fam-distrito",nome:"Distrito",icone:"🏙️",mercado:"Aberto",responsavel_contato:"Wanda",preco_venda_para_familia:"Tabela especial",preco_compra_da_familia:"Sob consulta",flyer_url:"static/images/flyers/distrito.webp"},
        {id:"fam-ballas",nome:"Ballas",icone:"🟣",mercado:"Aberto",responsavel_contato:"Matheus",preco_venda_para_familia:"Tabela padrão",preco_compra_da_familia:"Materiais",flyer_url:"static/images/flyers/ballas.webp"},
        {id:"fam-hells",nome:"Hells",icone:"🏴",mercado:"Aberto",responsavel_contato:"Theo",preco_venda_para_familia:"Tabela padrão",preco_compra_da_familia:"Sob consulta",flyer_url:"static/images/flyers/hells.webp"},
        {id:"fam-chaos",nome:"Chaos",icone:"🌀",mercado:"Em negociação",responsavel_contato:"A definir",preco_venda_para_familia:"Não informado",preco_compra_da_familia:"Não informado"},
        {id:"fam-nox",nome:"Nox",icone:"🌑",mercado:"Sem mercado",responsavel_contato:"A definir",preco_venda_para_familia:"Não informado",preco_compra_da_familia:"Não informado"}
      ];

      const purchases = [
        {id:"c1",data:"20/08/2026 10:20",produto:"Material",quem_pediu:"Estoque",quem_vendeu:"Ruptura",quantidade:100,tipo_dinheiro:"Dinheiro limpo",percentual_dinheiro_sujo:0,valor_total:750000,observacao:"Reposição semanal",familia_id:"fam-ruptura",familia_nome:"Ruptura",familia_icone:"💥",familia_responsavel:"Larissa"},
        {id:"c2",data:"19/08/2026 22:10",produto:"Componentes",quem_pediu:"Produção",quem_vendeu:"Ballas",quantidade:60,tipo_dinheiro:"Dinheiro sujo",percentual_dinheiro_sujo:20,valor_total:540000,observacao:"Produção de L85",familia_id:"fam-ballas",familia_nome:"Ballas",familia_icone:"🟣",familia_responsavel:"Matheus"}
      ];

      const sales = [
        {id:"v1",data:"20/08/2026 13:40",produto:"5x L85",quem_compra:"Ruptura",quem_vende:"Kokusai",quantidade:5,tipo_dinheiro:"Dinheiro sujo",percentual_dinheiro_sujo:20,valor_total:990000,familia_id:"fam-ruptura",familia_nome:"Ruptura",familia_icone:"💥",familia_responsavel:"Larissa"},
        {id:"v2",data:"18/08/2026 18:30",produto:"2x Seringa",quem_compra:"Distrito",quem_vende:"Kokusai",quantidade:2,tipo_dinheiro:"Dinheiro limpo",percentual_dinheiro_sujo:0,valor_total:330000,familia_id:"fam-distrito",familia_nome:"Distrito",familia_icone:"🏙️",familia_responsavel:"Wanda"}
      ];

      const orders = [
        {id:"enc-1",data:"20/08/2026 14:20",familia_id:"fam-ruptura",familia_nome:"Ruptura",familia_icone:"💥",familia_responsavel:"Larissa",quem_pediu:"Ruptura",o_que_pediu:"5x L85 + 2x Seringa",para_quando:"2026-08-21T20:00:00",prazo_iso:"2026-08-21T20:00:00",para_quando_exibicao:"21/08/2026 às 20:00",quem_negociou:"Larissa",tipo_dinheiro:"Dinheiro sujo",percentual_dinheiro_sujo:20,valor:1320000,prioridade:true,observacao:"Separar o lote e confirmar o ponto de entrega antes de sair.",itens:[{produto:"L85",quantidade:5,valor_unitario:165000},{produto:"Seringa",quantidade:2,valor_unitario:165000}]},
        {id:"enc-2",data:"20/08/2026 11:05",familia_id:"fam-distrito",familia_nome:"Distrito",familia_icone:"🏙️",familia_responsavel:"Wanda",quem_pediu:"Distrito",o_que_pediu:"10x L85",para_quando:"2026-08-22T23:59:00",prazo_iso:"2026-08-22T23:59:00",para_quando_exibicao:"22/08/2026 às 23:59",quem_negociou:"Wanda",tipo_dinheiro:"Dinheiro limpo",percentual_dinheiro_sujo:0,valor:1650000,prioridade:false,observacao:"",itens:[{produto:"L85",quantidade:10,valor_unitario:165000}]},
        {id:"enc-3",data:"19/08/2026 19:10",familia_id:"fam-ballas",familia_nome:"Ballas",familia_icone:"🟣",familia_responsavel:"Matheus",quem_pediu:"Ballas",o_que_pediu:"3x Seringa",para_quando:"2026-08-25T18:30:00",prazo_iso:"2026-08-25T18:30:00",para_quando_exibicao:"25/08/2026 às 18:30",quem_negociou:"Matheus",tipo_dinheiro:"Dinheiro limpo",percentual_dinheiro_sujo:0,valor:495000,prioridade:false,observacao:"Entregar somente ao responsável cadastrado.",itens:[{produto:"Seringa",quantidade:3,valor_unitario:165000}]}
      ];

      const meetings = [
        {id:"reu-1",titulo:"Alinhamento de parceria",gangue:"Ruptura",icone:"💥",data:"2026-08-21",horario:"21:00",local:"Base Kokusai",pauta:"Revisar condições e próximos pedidos.",status:"Agendada",responsavel_contato:"Larissa"},
        {id:"reu-2",titulo:"Revisão de mercado",gangue:"Distrito",icone:"🏙️",data:"2026-08-22",horario:"20:30",local:"Distrito",pauta:"Atualização da tabela.",status:"Aguardando confirmação",responsavel_contato:"Wanda"},
        {id:"reu-3",titulo:"Apresentação comercial",gangue:"Ballas",icone:"🟣",data:"2026-08-25",horario:"22:00",local:"A combinar",pauta:"Novos produtos.",status:"Agendada",responsavel_contato:"Matheus"}
      ];

      const rooms = [
        {user_id:"meta-amara",display_name:"Amara",username:"amara",status:"Pago",photo_count:2,consecutive_unpaid_weeks:0,payment_warning:false},
        {user_id:"meta-astrid",display_name:"Astrid",username:"astrid",status:"Pago",photo_count:2,consecutive_unpaid_weeks:0,payment_warning:false},
        {user_id:"meta-gohan",display_name:"Gohan",username:"gohan",status:"Enviado",photo_count:3,consecutive_unpaid_weeks:0,payment_warning:false},
        {user_id:"meta-kiyomi",display_name:"Kiyomi",username:"kiyomi",status:"Pendente",photo_count:0,consecutive_unpaid_weeks:0,payment_warning:false},
        {user_id:"meta-kiyotaka",display_name:"Kiyotaka",username:"kiyotaka",status:"Pendente",photo_count:0,consecutive_unpaid_weeks:0,payment_warning:false},
        {user_id:"meta-matheus",display_name:"Matheus",username:"matheus",status:"Não pago",photo_count:0,consecutive_unpaid_weeks:2,payment_warning:false},
        {user_id:"meta-philippe",display_name:"Philippe",username:"philippe",status:"Não pago",photo_count:0,consecutive_unpaid_weeks:3,payment_warning:true},
        {user_id:"meta-wanda",display_name:"Wanda",username:"wanda",status:"Pago",photo_count:1,consecutive_unpaid_weeks:0,payment_warning:false},
        {user_id:"meta-yuri",display_name:"Yuri",username:"yuri",status:"Pendente",photo_count:0,consecutive_unpaid_weeks:0,payment_warning:false}
      ];

      const report = {
        mes:"2026-08",
        mes_label:"agosto de 2026",
        gerado_em:"20/08/2026 16:20",
        resumo:{gangues:3,total_gasto:3217500,compras:5,encomendas_finalizadas:3,encomendas_pendentes:2,valor_pendente:850000,vendas_sem_familia:0,valor_sem_familia:0},
        ranking:[
          {posicao:1,familia_id:"fam-ruptura",nome:"Ruptura",icone:"💥",responsavel_contato:"Larissa",total_gasto:1472500,compras:3,compras_diretas:1,encomendas_finalizadas:2,encomendas_pendentes:1,valor_pendente:330000,itens_comprados:9},
          {posicao:2,familia_id:"fam-distrito",nome:"Distrito",icone:"🏙️",responsavel_contato:"Wanda",total_gasto:1075000,compras:1,compras_diretas:1,encomendas_finalizadas:1,encomendas_pendentes:0,valor_pendente:0,itens_comprados:6},
          {posicao:3,familia_id:"fam-ballas",nome:"Ballas",icone:"🟣",responsavel_contato:"Matheus",total_gasto:670000,compras:1,compras_diretas:0,encomendas_finalizadas:0,encomendas_pendentes:1,valor_pendente:520000,itens_comprados:4}
        ]
      };

      const jsonResponse = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), {
        status,
        headers:{"Content-Type":"application/json;charset=UTF-8"}
      }));

      window.fetch = (input, options = {}) => {
        const rawUrl = typeof input === "string" ? input : input.url;
        const url = rawUrl.replace(/^https?:\\/\\/[^/]+/, "");
        const method = String(options.method || "GET").toUpperCase();

        if (method !== "GET") return jsonResponse({message:"Ação simulada na prévia visual."});
        if (url === "/health") return jsonResponse({ok:true});
        if (url === "/api/resumo") return jsonResponse({total_registros:14,valor_movimentado:4825000});
        if (url === "/api/resumo-vendas") return jsonResponse({total_registros:23,valor_movimentado:7280000});
        if (url === "/api/resumo-encomendas") return jsonResponse({total_registros:3,valor_movimentado:3465000});
        if (url === "/api/resumo-metas") return jsonResponse({total:31,pagos:24,nao_pagos:2,faltam_confirmar:5,confirmados:26,semana_label:"14/08/2026 até 19/08/2026"});
        if (url === "/api/compras") return jsonResponse(purchases);
        if (url === "/api/vendas") return jsonResponse(sales);
        if (url === "/api/encomendas") return jsonResponse(orders);
        if (url === "/api/familias") return jsonResponse(families);
        if (url === "/api/reunioes") return jsonResponse(meetings);
        if (url.startsWith("/api/relatorios/gangues")) return jsonResponse(report);
        if (url === "/api/meta-rooms") return jsonResponse({
          rooms,
          week:{semana_inicio:"2026-08-14",semana_label:"14/08/2026 até 19/08/2026",prazo_pagamento:"19/08/2026 às 23:59",data_conferencia:"20/08/2026",closed:false,review_mode:true,can_finalize:false}
        });
        if (/^\\/api\\/meta-rooms\\/[^/?]+/.test(url)) {
          const memberId = url.split("/")[3].split("?")[0];
          const member = rooms.find(item => item.user_id === memberId) || rooms[0];
          return jsonResponse({
            member,
            submission:{id:"submission-preview",week_start:"14/08/2026",week_end:"19/08/2026",status:member.status,admin_note:""},
            photos:[],
            history:[{week_start:"07/08/2026",week_end:"12/08/2026",photo_count:2,status:member.payment_warning ? "Não pago" : "Pago",reviewed_at:"13/08/2026 18:40"}],
            payment_monitor:{consecutive_unpaid_weeks:member.consecutive_unpaid_weeks || 0,warning:Boolean(member.payment_warning),warning_threshold:3},
            limits:{max_photos:10,max_file_mb:10}
          });
        }
        return jsonResponse({message:"Conteúdo simulado."});
      };
    })();
  </script>`;
}

function fileDataUri(relativePath) {
  const absolutePath = path.join(projectRoot, relativePath);
  const extension = path.extname(relativePath).toLowerCase();
  const mimeTypes = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
  };
  const mimeType = mimeTypes[extension];
  if (!mimeType) throw new Error(`Formato não suportado na prévia: ${relativePath}`);
  return `data:${mimeType};base64,${fs.readFileSync(absolutePath).toString("base64")}`;
}

function buildStandalonePreview(previewHtml) {
  const baseCss = fs.readFileSync(path.join(projectRoot, "static", "css", "style.css"), "utf8");
  const hudCss = fs.readFileSync(path.join(projectRoot, "static", "css", "hud.css"), "utf8");
  const appJs = fs.readFileSync(path.join(projectRoot, "static", "js", "app.js"), "utf8");
  const embeddedImages = [
    "static/images/kokusai-logo.webp",
    "static/images/flyers/leviata.webp",
    "static/images/flyers/distrito.webp",
    "static/images/flyers/ballas.webp",
    "static/images/flyers/hells.webp",
  ];

  let standalone = previewHtml;
  standalone = standalone.replace(
    /<link rel="stylesheet" href="static\/css\/style\.css[^"]*"\s*\/>/,
    `<style data-preview-source="style.css">\n${baseCss}\n</style>`,
  );
  standalone = standalone.replace(
    /<link rel="stylesheet" href="static\/css\/hud\.css[^"]*"\s*\/>/,
    `<style data-preview-source="hud.css">\n${hudCss}\n</style>`,
  );

  for (const imagePath of embeddedImages) {
    standalone = standalone.replaceAll(imagePath, fileDataUri(imagePath));
  }

  standalone = standalone.replace(
    /<script src="static\/js\/app\.js[^"]*"><\/script>/,
    `<script data-preview-source="app.js">\n${appJs}\n</script>`,
  );
  standalone = standalone.replace(
    "Prévia visual <small>dados simulados · nada será salvo</small>",
    "Prévia independente <small>visual completo · nada será salvo</small>",
  );
  return standalone;
}

const source = fs.readFileSync(templatePath, "utf8");
const preview = renderTemplate(source);
const standalonePreview = buildStandalonePreview(preview);
fs.writeFileSync(standaloneOutputPath, standalonePreview, "utf8");
console.log(standaloneOutputPath);
