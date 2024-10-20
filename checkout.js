// Declaração global para evitar redefinições de 'totalValue'
let totalValue = 0;

// Instancia o SDK do Mercado Pago
const mp = new MercadoPago('APP_USR-671c40ea-a412-46ed-8444-621ee1788946AGO');

// Captura o Device ID
const deviceId = mp.device.create();

let freteReiniciado = false; // Variável para controlar se o frete foi reiniciado

// Evento de clique no botão "Finalizar Compra"
document.getElementById('submit-button').addEventListener('click', function (e) {
    e.preventDefault();

    // Limpa mensagens de erro
    document.querySelectorAll('.error-message').forEach(span => span.textContent = '');

    const nome = document.querySelector('input[name="nome"]').value.trim();
    const cpf = document.querySelector('input[name="cpf"]').value.trim();
    const email = document.querySelector('input[name="email"]').value.trim();
    const contato = document.querySelector('input[name="contato"]').value.trim();

    // Campos de endereço
    const rua = document.querySelector('input[name="rua"]').value.trim();
    const numero = document.querySelector('input[name="numero"]').value.trim();
    const bairro = document.querySelector('input[name="bairro"]').value.trim();
    const cidade = document.querySelector('input[name="cidade"]').value.trim();
    const estado = document.querySelector('input[name="estado"]').value.trim();
    const cep = document.querySelector('input[name="cep"]').value.trim();
    const complemento = document.querySelector('input[name="complemento"]').value.trim();

    const paymentMethodElement = document.querySelector('input[name="payment-method"]:checked');
    if (!paymentMethodElement) {
        alert("Por favor, selecione uma forma de pagamento.");
        return;
    }
    const paymentMethod = paymentMethodElement.value;

    const selectedFreight = document.querySelector('input[name="frete"]:checked');
    if (!selectedFreight) {
        alert("Por favor, selecione uma opção de frete.");
        return;
    }

    totalValue = Number(document.getElementById('total-com-frete').innerText.replace('R$ ', '').replace(',', '.'));

    let formIsValid = true;

    // Validações dos campos obrigatórios
    if (!nome) {
        document.getElementById('nome-error').textContent = "Nome é obrigatório.";
        formIsValid = false;
    }
    if (!cpf) {
        document.getElementById('cpf-error').textContent = "CPF é obrigatório.";
        formIsValid = false;
    }
    if (!email) {
        document.getElementById('email-error').textContent = "E-mail é obrigatório.";
        formIsValid = false;
    }
    if (!contato) {
        document.getElementById('contato-error').textContent = "Contato é obrigatório.";
        formIsValid = false;
    }
    if (!rua || !numero || !bairro || !cidade || !estado || !cep) {
        alert("Por favor, preencha todos os campos de endereço.");
        formIsValid = false;
    }
    if (!formIsValid) return;

    const [first_name, ...last_name_parts] = nome.split(' ');
    const last_name = last_name_parts.join(' ') || 'Sobrenome Não Informado';
    const freightValue = selectedFreight ? parseFloat(selectedFreight.value) : 0;

    const customer = {
        first_name: first_name,
        last_name: last_name,
        cpf: cpf,
        email: email,
        contato: contato,
        rua: rua,
        numero: numero,
        bairro: bairro,
        cidade: cidade,
        estado: estado,
        cep: cep,
        complemento: complemento
    };

    let items = JSON.parse(sessionStorage.getItem('cart')) || [];
    let directItem = null;

    // Verifica se é compra direta
    const isDirectPurchase = items.length === 0 && window.directPurchaseItem;
    if (isDirectPurchase) {
        directItem = window.directPurchaseItem;
    } else {
        items = items.map(item => ({
            id: item.productId,
            title: item.title,
            description: item.description || "Produto sem descrição",
            category_id: item.category_id || "others",
            quantity: item.quantity,
            unit_price: parseFloat(item.unit_price)
        }));
    }

    const external_reference = `order_${Date.now()}`;
    const date_of_expiration = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();

    const paymentData = {
        token: null,
        payment_method_id: paymentMethod,
        transaction_amount: totalValue,
        freight: freightValue,
        description: 'PEDIDO NOVO - VIDEOGAME',
        external_reference: external_reference,
        date_of_expiration: date_of_expiration,
        notification_url: 'https://your-notification-url.com',
        payer: {
            first_name: first_name,
            last_name: last_name,
            email: email,
            identification: {
                type: 'CPF',
                number: cpf.replace(/\D/g, '')
            },
            address: {
                zip_code: cep.replace(/\D/g, ''),
                street_name: rua,
                street_number: numero,
                neighborhood: bairro,
                city: cidade,
                federal_unit: estado
            }
        },
        additional_info: {
            items: isDirectPurchase ? [directItem] : items,
            device_id: deviceId
        }
    };

    if (paymentMethod === 'credito') {
        // Obtendo o token do cartão de crédito com o SDK do Mercado Pago
        const cardNumber = document.getElementById('cardNumber').value;
        const cardExpirationMonth = document.getElementById('cardExpirationMonth').value;
        const cardExpirationYear = document.getElementById('cardExpirationYear').value;
        const securityCode = document.getElementById('securityCode').value;
        const cardholderName = document.getElementById('cardholderName').value;

        if (!cardNumber || !cardExpirationMonth || !cardExpirationYear || !securityCode || !cardholderName) {
            alert("Por favor, preencha todos os campos do cartão.");
            return;
        }

        window.MercadoPago.createCardToken({
            cardNumber: cardNumber,
            cardExpirationMonth: cardExpirationMonth,
            cardExpirationYear: cardExpirationYear,
            securityCode: securityCode,
            cardholderName: cardholderName,
            identificationType: 'CPF',
            identificationNumber: cpf.replace(/\D/g, '')
        }, function (status, response) {
            if (status === 200 || status === 201) {
                paymentData.token = response.id;
                processarPagamento(paymentData);
            } else {
                alert('Erro ao gerar o token do cartão: ' + response.cause[0].description);
            }
        });
    } else {
        processarPagamento(paymentData);
    }
});

// Função para processar o pagamento
function processarPagamento(paymentData) {
    const backendUrl = 'https://eusobrisei.vercel.app'; // URL do backend

    fetch(`${backendUrl}/process_payment`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Idempotency-Key': paymentData.external_reference
        },
        body: JSON.stringify(paymentData)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errorData => {
                console.error("Erro na resposta do backend:", errorData);
                throw new Error(errorData.message || "Erro inesperado ao processar o pagamento.");
            });
        } else {
            return response.json();
        }
    })
    .then(data => {
        if (data.status === 'approved') {
            alert('Pagamento aprovado com sucesso!');
            emitirEtiqueta(customer, selectedFreight);
            window.location.href = '/success';
        } else if (data.status === 'pending' && paymentData.payment_method_id === 'pix') {
            document.getElementById('qr_code_image').src = `data:image/png;base64,${data.qr_code_base64}`;
            document.getElementById('qr_code_image').style.display = 'block';
            document.getElementById('pix_code').value = data.qr_code;
            document.getElementById('qr_code_container').style.display = 'block';
            alert("Pagamento pendente. Use o QR Code para finalizar.");
        } else {
            alert(`Erro no pagamento: ${data.message}`);
        }
    })
    .catch(error => {
        console.error("Erro no frontend:", error.message);
        alert(`Erro ao finalizar compra: ${error.message}`);
    });
}

// Função para emitir etiqueta após pagamento aprovado
function emitirEtiqueta(customer, selectedFreight) {
    const remetente = {
        nome: 'Loja Exemplo',
        cpf: '123.456.789-00',
        contato: '11 99999-9999',
        rua: 'Rua do Remetente',
        numero: '100',
        bairro: 'Centro',
        cidade: 'São Paulo',
        estado: 'SP',
        cep: '01000-000'
    };

    const pacote = {
        height: 3,
        width: 11,
        length: 16,
        weight: 0.3
    };

    const backendUrl = 'https://eusobrisei.vercel.app';

    fetch(`${backendUrl}/emitir_etiqueta`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            destinatario: customer,
            remetente: remetente,
            pacote: pacote,
            servico: selectedFreight.value
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.label_url) {
            window.open(data.label_url, '_blank');
        } else {
            alert('Erro ao emitir a etiqueta.');
        }
    })
    .catch(error => {
        console.error('Erro ao emitir a etiqueta:', error.message);
        alert('Erro ao emitir a etiqueta.');
    });
}

// Função para carregar os itens do carrinho
function carregarCarrinho() {
    let carrinho = JSON.parse(sessionStorage.getItem('cart')) || [];
    let listaItens = document.getElementById('items-list');
    listaItens.innerHTML = '';
    let total = 0;

    carrinho.forEach(item => {
        let tr = document.createElement('tr');

        let tdTitle = document.createElement('td');
        tdTitle.textContent = item.title;
        tr.appendChild(tdTitle);

        let tdQuantity = document.createElement('td');
        let inputQuantity = document.createElement('input');
        inputQuantity.type = 'number';
        inputQuantity.value = item.quantity;
        inputQuantity.min = '1';
        inputQuantity.onchange = function () { updateQuantity(this, item.productId); };
        tdQuantity.appendChild(inputQuantity);
        tr.appendChild(tdQuantity);

        let tdUnitPrice = document.createElement('td');
        tdUnitPrice.textContent = `R$ ${item.unit_price.toFixed(2)}`;
        tr.appendChild(tdUnitPrice);

        let tdTotalPrice = document.createElement('td');
        tdTotalPrice.textContent = `R$ ${(item.unit_price * item.quantity).toFixed(2)}`;
        tr.appendChild(tdTotalPrice);

        let tdRemove = document.createElement('td');
        let btnRemove = document.createElement('button');
        btnRemove.textContent = 'Remover';
        btnRemove.className = 'btn-remove';
        btnRemove.onclick = function () {
            removeItem(item.productId);
        };
        tdRemove.appendChild(btnRemove);
        tr.appendChild(tdRemove);

        listaItens.appendChild(tr);

        total += item.unit_price * item.quantity;
    });

    document.getElementById('total-price').innerText = total.toFixed(2);

    // Atualizar o total com o frete selecionado
    const selectedFreight = document.querySelector('input[name="frete"]:checked');
    if (selectedFreight) {
        const freightValue = parseFloat(selectedFreight.value);
        document.getElementById('total-com-frete').innerText = (total + freightValue).toFixed(2);
    } else {
        document.getElementById('total-com-frete').innerText = total.toFixed(2);
    }
}

// Função para atualizar a quantidade de um item
function updateQuantity(input, productId) {
    let carrinho = JSON.parse(sessionStorage.getItem('cart')) || [];

    let item = carrinho.find(item => item.productId === productId);
    if (item) {
        item.quantity = parseInt(input.value);
    }

    sessionStorage.setItem('cart', JSON.stringify(carrinho));
    carregarCarrinho();

    // Reinicia o frete após alteração de itens
    if (!freteReiniciado) {
        alert("A quantidade de itens foi alterada. Por favor, recalcule o frete.");
        document.querySelector('input[name="frete"]:checked').checked = false;
        document.getElementById('frete-result').innerHTML = '';
        document.getElementById('total-com-frete').innerText = document.getElementById('total-price').innerText;
        freteReiniciado = true;
    }
}

// Função para remover um item do carrinho
function removeItem(productId) {
    let carrinho = JSON.parse(sessionStorage.getItem('cart')) || [];
    carrinho = carrinho.filter(item => item.productId !== productId);
    sessionStorage.setItem('cart', JSON.stringify(carrinho));
    carregarCarrinho();

    // Reinicia o frete após remoção de itens
    if (!freteReiniciado) {
        alert("Um item foi removido. Por favor, recalcule o frete.");
        document.querySelector('input[name="frete"]:checked').checked = false;
        document.getElementById('frete-result').innerHTML = '';
        document.getElementById('total-com-frete').innerText = document.getElementById('total-price').innerText;
        freteReiniciado = true;
    }
}

// Função para calcular o frete com Super Frete
function calcularFrete() {
    let cep = document.querySelector('input[name="cep"]').value;
    const cleanedCep = cep.replace(/\D/g, '');

    if (cleanedCep.length !== 8) {
        alert("CEP inválido. Por favor, insira um CEP correto.");
        return;
    }

    const backendUrl = 'https://eusobrisei.vercel.app';

    fetch(`${backendUrl}/calculate_shipping`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            from_postal_code: '14340-000',
            to_postal_code: cleanedCep,
            services: '1,2,17',
            package: {
                height: 3,
                width: 11,
                length: 16,
                weight: 0.3
            },
            options: {
                own_hand: false,
                receipt: false,
                insurance_value: 100.00
            }
        })
    })
    .then(response => response.json())
    .then(data => {
        if (Array.isArray(data) && data.length > 0) {
            let freteOptions = data.map((item, index) => {
                return `
                    <label>
                        <input type="radio" name="frete" value="${item.price}" data-index="${index}" onchange="atualizarFrete(${item.price})">
                        Serviço: ${item.name} - Valor: R$ ${item.price.toFixed(2)} - Prazo de entrega: ${item.delivery_time} dias úteis
                    </label>
                `;
            }).join('');

            document.getElementById('frete-result').innerHTML = freteOptions;
        } else {
            alert("Não foi possível calcular o frete.");
        }
    })
    .catch(error => {
        alert("Erro ao calcular o frete. Verifique o CEP e tente novamente.");
    });
}

// Função para atualizar o valor do frete no total
function atualizarFrete(valorFrete) {
    totalValue = parseFloat(document.getElementById('total-price').innerText.replace("R$ ", ""));
    document.getElementById('frete-price').innerText = `R$ ${valorFrete.toFixed(2)}`;
    document.getElementById('total-com-frete').innerText = `R$ ${(totalValue + valorFrete).toFixed(2)}`;
}

// Carregar o carrinho ao abrir a página
carregarCarrinho();

// Exibir campos de cartão apenas se "Cartão de Crédito" ou "Cartão de Débito" for selecionado
document.querySelectorAll('input[name="payment-method"]').forEach((radio) => {
    radio.addEventListener('change', function () {
        const cardInfo = document.getElementById('card-info');
        const cardFields = document.querySelectorAll('#cardNumber, #cardExpirationMonth, #cardExpirationYear, #securityCode, #cardholderName');
        const parcelasField = document.getElementById('installments');

        if (this.value === 'credito') {
            cardInfo.style.display = 'block';
            cardFields.forEach(field => {
                field.removeAttribute('disabled');
                field.setAttribute('required', 'required');
            });

            fetchInstallments(); // Obter as opções de parcelamento
        } else {
            cardInfo.style.display = 'none';
            cardFields.forEach(field => {
                field.removeAttribute('required');
                field.setAttribute('disabled', 'disabled');
            });

            parcelasField.style.display = 'none'; // Esconde o campo de parcelas
        }

        document.getElementById('qr_code_image').style.display = 'none';
        document.getElementById('pix_code').style.display = 'none';
        document.getElementById('qr_code_container').style.display = 'none';
    });
});

// Função para buscar as opções de parcelamento com base no valor total
function fetchInstallments() {
    const cardBin = document.getElementById('cardNumber').value.substring(0, 6);
    totalValue = Number(document.getElementById('total-com-frete').innerText.replace('R$', '').replace(',', '.')).toFixed(2);

    // Verificações de BIN e total
    if (!cardBin || cardBin.length < 6) {
        console.error("Erro: BIN do cartão inválido:", cardBin);
        alert("Erro: BIN do cartão inválido.");
        return;
    }

    if (isNaN(totalValue) || totalValue <= 0) {
        console.error("Erro: Valor total inválido:", totalValue);
        alert("Erro: Valor total inválido.");
        return;
    }

    console.log("Enviando BIN:", cardBin, " e valor total:", totalValue);

    // Faz a chamada para o backend
    fetch('https://eusobrisei.vercel.app/get_installments', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            bin: cardBin,
            amount: parseFloat(totalValue)
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Erro ao buscar parcelas: ${response.statusText}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Parcelas recebidas:', data);
        // Aqui você pode processar as parcelas recebidas e preencher o campo de parcelas
    })
    .catch(error => {
        console.error('Erro ao buscar parcelas:', error);
        alert('Erro ao buscar parcelas.');
    });
}
