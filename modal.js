// Inicializar o Mercado Pago
const mp = new MercadoPago('TEST-d8bbf77e-7c6d-4797-926c-f0657ab5fcf5');

// Abrir e fechar o modal
const openModalBtn = document.getElementById('openModalBtn');
const modal = document.getElementById('productModal');
const closeModalBtn = document.getElementById('closeModalBtn');

// Garantir que o modal não abra automaticamente ao carregar o site
openModalBtn.onclick = function () {
    modal.style.display = "flex";
}

closeModalBtn.onclick = function () {
    modal.style.display = "none";
}

window.onclick = function (event) {
    if (event.target == modal) {
        modal.style.display = "none";
    }
}

// Função para incluir o produto no carrinho
document.getElementById('addToCartBtn').addEventListener('click', function () {
    const productName = document.getElementById('productName').textContent;
    const productPrice = parseFloat(document.getElementById('productPrice').textContent.replace('Preço: R$ ', '').replace(',', '.'));
    const product = {
        title: productName,
        unit_price: productPrice,
        quantity: 1 // Inicialmente 1
    };

    // Carregar o carrinho do sessionStorage
    let cart = JSON.parse(sessionStorage.getItem('cart')) || [];

    // Verificar se o item já está no carrinho e atualizar a quantidade
    const existingItem = cart.find(item => item.title === product.title);
    if (existingItem) {
        existingItem.quantity += 1; // Aumenta a quantidade
    } else {
        cart.push(product); // Adiciona novo item
    }

    // Armazenar o carrinho atualizado no sessionStorage
    sessionStorage.setItem('cart', JSON.stringify(cart));
    alert('Produto adicionado ao carrinho!');
});

// Função para o botão Comprar
document.getElementById('buyBtn').addEventListener('click', function () {
    const productName = document.getElementById('productName').textContent;
    const productPrice = parseFloat(document.getElementById('productPrice').textContent.replace('Preço: R$ ', '').replace(',', '.'));
    const product = {
        title: productName,
        unit_price: productPrice,
        quantity: 1
    };

    // Zera o carrinho e armazena o novo produto
    let cart = [];
    cart.push(product);
    sessionStorage.setItem('cart', JSON.stringify(cart)); 
    window.location.href = 'checkout.html'; // Redireciona para a página de checkout
});

/* --- Alteração da exibição das imagens com setas para navegação --- */

// Função para criar o carrossel de imagens no modal
const images = [
    'https://via.placeholder.com/150/0000FF',
    'https://via.placeholder.com/150/FF0000',
    'https://via.placeholder.com/150/00FF00',
    'https://via.placeholder.com/150/FFFF00'
]; // Substitua pelos URLs reais das imagens do produto

let currentImageIndex = 0;
const imageElement = document.getElementById('productImage');
const prevImageBtn = document.createElement('button');
const nextImageBtn = document.createElement('button');

prevImageBtn.innerHTML = '&#10094;'; // Seta para esquerda
nextImageBtn.innerHTML = '&#10095;'; // Seta para direita

// Estilos para as setas de navegação
prevImageBtn.style.position = 'absolute';
prevImageBtn.style.left = '10px';
prevImageBtn.style.top = '50%';
prevImageBtn.style.background = 'rgba(0, 0, 0, 0.5)';
prevImageBtn.style.color = 'white';
prevImageBtn.style.border = 'none';
prevImageBtn.style.padding = '10px';
prevImageBtn.style.cursor = 'pointer';

nextImageBtn.style.position = 'absolute';
nextImageBtn.style.right = '10px';
nextImageBtn.style.top = '50%';
nextImageBtn.style.background = 'rgba(0, 0, 0, 0.5)';
nextImageBtn.style.color = 'white';
nextImageBtn.style.border = 'none';
nextImageBtn.style.padding = '10px';
nextImageBtn.style.cursor = 'pointer';

// Função para atualizar a imagem exibida
function updateImageDisplay() {
    imageElement.src = images[currentImageIndex];
}

// Eventos para as setas de navegação
prevImageBtn.onclick = function () {
    currentImageIndex = (currentImageIndex - 1 + images.length) % images.length; // Voltar imagem
    updateImageDisplay();
}

nextImageBtn.onclick = function () {
    currentImageIndex = (currentImageIndex + 1) % images.length; // Avançar imagem
    updateImageDisplay();
}

// Adicionar as setas ao modal
document.querySelector('.product-details').appendChild(prevImageBtn);
document.querySelector('.product-details').appendChild(nextImageBtn);

// Atualizar a exibição inicial da imagem
updateImageDisplay();
