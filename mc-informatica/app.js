/* ============================================================
   MC INFORMÁTICA — Loja
   ------------------------------------------------------------
   O site não realiza venda direta: todo anúncio leva o cliente
   para o WhatsApp da loja, onde a negociação é fechada.

   COMO EDITAR A LOJA:
   1. NUMERO_WHATSAPP: coloque o número da loja com DDI+DDD,
      só dígitos. Ex.: 5511999998888
   2. PRODUTOS: adicione/remova produtos na lista abaixo.
      - id: identificador único (sem espaços)
      - categoria: notebooks | computadores | perifericos | hardware
      - condicao: "novo" ou "usado" (usados também aparecem no
        filtro "Usados")
      - imagem: caminho ou URL da foto. Deixe "" para mostrar um
        ícone no lugar (coloque as fotos na pasta img/)
      - icone: classe Font Awesome usada quando não há foto
   ============================================================ */

const NUMERO_WHATSAPP = "5516996198688"; // WhatsApp da MC Informática

const PRODUTOS = [
    {
        id: "notebook-i5-8gb",
        nome: "Notebook Core i5 · 8GB · SSD 256GB",
        categoria: "notebooks",
        condicao: "novo",
        descricao: "Ideal para trabalho e estudos. Tela 15,6\", Windows 11 instalado.",
        preco: 2499.00,
        imagem: "",
        icone: "fa-solid fa-laptop"
    },
    {
        id: "notebook-usado-i3",
        nome: "Notebook Core i3 · 8GB · SSD 240GB (Seminovo)",
        categoria: "notebooks",
        condicao: "usado",
        descricao: "Seminovo revisado pela nossa assistência, com garantia da loja.",
        preco: 1299.00,
        imagem: "",
        icone: "fa-solid fa-laptop"
    },
    {
        id: "pc-completo-home",
        nome: "Computador Completo + Monitor 19\"",
        categoria: "computadores",
        condicao: "novo",
        descricao: "PC completo com monitor, teclado e mouse. Pronto para usar.",
        preco: 1899.00,
        imagem: "",
        icone: "fa-solid fa-desktop"
    },
    {
        id: "pc-gamer-entrada",
        nome: "PC Gamer · Ryzen 5 · 16GB · GTX 1650",
        categoria: "computadores",
        condicao: "novo",
        descricao: "Roda os jogos mais populares em Full HD. Montado e testado na loja.",
        preco: 3799.00,
        imagem: "",
        icone: "fa-solid fa-computer"
    },
    {
        id: "pc-usado-office",
        nome: "Computador para Escritório (Seminovo)",
        categoria: "computadores",
        condicao: "usado",
        descricao: "Core i5, 8GB, SSD 240GB. Revisado e com garantia da loja.",
        preco: 999.00,
        imagem: "",
        icone: "fa-solid fa-desktop"
    },
    {
        id: "monitor-24",
        nome: "Monitor LED 24\" Full HD",
        categoria: "perifericos",
        condicao: "novo",
        descricao: "Painel IPS, 75Hz, HDMI e VGA. Ótimo para trabalho e jogos.",
        preco: 649.00,
        imagem: "",
        icone: "fa-solid fa-tv"
    },
    {
        id: "kit-teclado-mouse",
        nome: "Kit Teclado e Mouse Sem Fio",
        categoria: "perifericos",
        condicao: "novo",
        descricao: "Conexão USB 2.4GHz, teclado ABNT2 silencioso.",
        preco: 119.00,
        imagem: "",
        icone: "fa-solid fa-keyboard"
    },
    {
        id: "headset-gamer",
        nome: "Headset Gamer com Microfone",
        categoria: "perifericos",
        condicao: "novo",
        descricao: "Som estéreo, microfone flexível e LED. Compatível com PC e console.",
        preco: 159.00,
        imagem: "",
        icone: "fa-solid fa-headphones"
    },
    {
        id: "impressora-multifuncional",
        nome: "Impressora Multifuncional Wi-Fi",
        categoria: "perifericos",
        condicao: "novo",
        descricao: "Imprime, copia e digitaliza. Tanque de tinta econômico.",
        preco: 899.00,
        imagem: "",
        icone: "fa-solid fa-print"
    },
    {
        id: "ssd-480",
        nome: "SSD 480GB SATA",
        categoria: "hardware",
        condicao: "novo",
        descricao: "Deixe seu computador até 10x mais rápido. Instalação disponível.",
        preco: 249.00,
        imagem: "",
        icone: "fa-solid fa-hard-drive"
    },
    {
        id: "memoria-8gb-ddr4",
        nome: "Memória RAM 8GB DDR4",
        categoria: "hardware",
        condicao: "novo",
        descricao: "2666MHz, para desktop ou notebook. Consulte compatibilidade.",
        preco: 149.00,
        imagem: "",
        icone: "fa-solid fa-memory"
    },
    {
        id: "fonte-500w",
        nome: "Fonte 500W 80 Plus",
        categoria: "hardware",
        condicao: "novo",
        descricao: "Certificação 80 Plus, proteção contra sobrecarga.",
        preco: 279.00,
        imagem: "",
        icone: "fa-solid fa-plug"
    }
];

/* ============================================================
   A partir daqui é o funcionamento da loja — normalmente não
   precisa mexer.
   ============================================================ */

const formatarPreco = (valor) =>
    valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

// ---------- WhatsApp ----------
function abrirWhatsApp(mensagem) {
    const url = `https://wa.me/${NUMERO_WHATSAPP}?text=${encodeURIComponent(mensagem)}`;
    window.open(url, "_blank");
}

// ---------- Renderização de produtos ----------
const gradeProdutos = document.getElementById("grade-produtos");

function renderizarProdutos(categoria = "todos") {
    const visiveis = PRODUTOS.filter((p) => {
        if (categoria === "todos") return true;
        if (categoria === "usados") return p.condicao === "usado";
        return p.categoria === categoria;
    });

    if (visiveis.length === 0) {
        gradeProdutos.innerHTML =
            '<p class="sem-produtos">Nenhum produto nesta categoria no momento. Fale com a gente no WhatsApp!</p>';
        return;
    }

    gradeProdutos.innerHTML = visiveis
        .map((p) => {
            const imagem = p.imagem
                ? `<img src="${p.imagem}" alt="${p.nome}" loading="lazy">`
                : `<i class="${p.icone} icone-placeholder" aria-hidden="true"></i>`;
            const selo =
                p.condicao === "usado"
                    ? '<span class="selo selo-usado">Usado</span>'
                    : '<span class="selo selo-novo">Novo</span>';

            return `
            <article class="produto">
                <div class="produto-imagem">${imagem}${selo}</div>
                <div class="produto-corpo">
                    <p class="produto-categoria">${nomeCategoria(p.categoria)}</p>
                    <h3 class="produto-nome">${p.nome}</h3>
                    <p class="produto-descricao">${p.descricao}</p>
                    <p class="produto-preco">${formatarPreco(p.preco)}</p>
                    <div class="produto-acoes">
                        <button class="btn-comprar-whats" data-id="${p.id}">
                            <i class="fa-brands fa-whatsapp"></i> Comprar pelo WhatsApp
                        </button>
                    </div>
                </div>
            </article>`;
        })
        .join("");
}

function nomeCategoria(slug) {
    const nomes = {
        notebooks: "Notebooks",
        computadores: "Computadores",
        perifericos: "Periféricos",
        hardware: "Hardware"
    };
    return nomes[slug] || slug;
}

gradeProdutos.addEventListener("click", (e) => {
    const botao = e.target.closest(".btn-comprar-whats");
    if (!botao) return;
    const produto = PRODUTOS.find((p) => p.id === botao.dataset.id);
    if (produto) {
        abrirWhatsApp(
            `Olá! Vi este anúncio no site da MC Informática:\n\n• ${produto.nome} — ${formatarPreco(produto.preco)}\n\nAinda está disponível?`
        );
    }
});

// ---------- Filtros ----------
document.getElementById("filtros").addEventListener("click", (e) => {
    const botao = e.target.closest(".filtro");
    if (!botao) return;
    document.querySelectorAll(".filtro").forEach((b) => b.classList.remove("ativo"));
    botao.classList.add("ativo");
    renderizarProdutos(botao.dataset.categoria);
});

// Links genéricos de WhatsApp (cabeçalho, rodapé, botão flutuante, serviços)
document.querySelectorAll("[data-whats]").forEach((el) => {
    el.addEventListener("click", (e) => {
        e.preventDefault();
        abrirWhatsApp(el.dataset.whats);
    });
});

// ---------- Menu mobile ----------
const nav = document.getElementById("nav");
document.getElementById("menu-toggle").addEventListener("click", () => {
    nav.classList.toggle("aberto");
});
nav.addEventListener("click", (e) => {
    if (e.target.tagName === "A") nav.classList.remove("aberto");
});

// ---------- Inicialização ----------
renderizarProdutos();
