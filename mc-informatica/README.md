# MC Informática — Loja Virtual

Site de vendas da MC Informática (loja de informática, assistência técnica, novos e usados).

Página estática, sem necessidade de servidor: basta abrir o `index.html` ou publicar a pasta
em qualquer hospedagem (Vercel, Netlify, GitHub Pages etc.). O site não realiza venda direta:
todos os anúncios e botões levam o cliente para o WhatsApp da loja, onde a negociação é fechada.

## Configurações importantes (arquivo `app.js`)

1. **Número do WhatsApp** — já configurado com o número da loja. Se precisar trocar, edite
   a linha abaixo (DDI + DDD, só dígitos):

   ```js
   const NUMERO_WHATSAPP = "5516996198688";
   ```

2. **Produtos** — edite a lista `PRODUTOS` no topo do `app.js`. Cada produto tem:

   | Campo       | Descrição                                                              |
   |-------------|------------------------------------------------------------------------|
   | `id`        | Identificador único, sem espaços (ex.: `notebook-i5-8gb`)              |
   | `nome`      | Nome exibido no card                                                   |
   | `categoria` | `notebooks`, `computadores`, `perifericos` ou `hardware`               |
   | `condicao`  | `novo` ou `usado` (usados também aparecem no filtro "Usados")          |
   | `descricao` | Texto curto do card                                                    |
   | `preco`     | Preço em reais (ex.: `2499.00`)                                        |
   | `imagem`    | Caminho da foto (ex.: `img/notebook.jpg`). Vazio `""` mostra um ícone  |
   | `icone`     | Classe Font Awesome usada quando não há foto                           |

3. **Fotos dos produtos** — coloque as imagens na pasta `img/` e aponte o campo `imagem`.

## Logo

A logo atual (`img/logo.svg`) é uma versão vetorial recriada a partir da arte oficial.
Para usar a arte original, salve o arquivo como `img/logo.png` e troque as referências
`img/logo.svg` no `index.html` (cabeçalho, hero, rodapé e favicon).

## Contatos do rodapé

E-mail e horários de atendimento são editados direto no `index.html`, na seção `<footer>`.
