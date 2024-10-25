const express = require('express');
const mercadopago = require('mercadopago');
const axios = require('axios');
const cors = require('cors');
const path = require('path');
const { check, validationResult } = require('express-validator');
const QRCode = require('qrcode');

const app = express();
app.use(express.json());

// Lista de origens permitidas
const allowedOrigins = [
    'https://eusobrisei.vercel.app',
    'https://eusobrisei-git-master-thiagos-projects-bf2fb09b.vercel.app'
];

// Middleware CORS com suporte para múltiplas origens
app.use(cors({
    origin: function (origin, callback) {
        if (!origin || allowedOrigins.includes(origin)) {
            return callback(null, true);
        } else {
            return callback(new Error('Not allowed by CORS'));
        }
    },
    methods: ['GET', 'POST', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization']
}));

// Middleware para lidar com requisições preflight (OPTIONS)
app.options('*', cors());

app.use(express.static(path.join(__dirname)));

// Configuração do Mercado Pago
mercadopago.configure({
    access_token: 'APP_USR-4115909006959144-092213-b8561437409fd30d77848352287f57c9-1207255849'
});

// Variáveis globais
let cart = [];
let selectedFreight = 0;
let generatedQRCode = null;

// Função para recalcular o total do carrinho
function calculateCartTotal() {
    const itemsTotal = cart.reduce((total, item) => total + (item.unit_price * item.quantity), 0);
    return parseFloat(itemsTotal + selectedFreight).toFixed(2);
}

// Recalcula o frete e invalida o QR code gerado anteriormente
function resetFreightAndQRCode() {
    selectedFreight = 0;
    generatedQRCode = null;
}

// Rota para adicionar itens ao carrinho
app.post('api/add_to_cart', (req, res) => {
    const { productId, title, unit_price, quantity, category_id, description } = req.body;
    const existingItemIndex = cart.findIndex(item => item.productId === productId);
    if (existingItemIndex > -1) {
        cart[existingItemIndex].quantity += quantity;
    } else {
        cart.push({ productId, title, unit_price, quantity, category_id, description });
    }
    resetFreightAndQRCode();
    const total = calculateCartTotal();
    res.json({ message: "Produto adicionado ao carrinho", cart, total });
});

// Rota para remover itens do carrinho
app.post('api/remove_from_cart', (req, res) => {
    const { productId } = req.body;
    cart = cart.filter(item => item.productId !== productId);
    resetFreightAndQRCode();
    const total = calculateCartTotal();
    res.json({ message: "Produto removido do carrinho", cart, total });
});

// Rota para modificar a quantidade de um item no carrinho
app.post('api/update_cart_item', (req, res) => {
    const { productId, quantity } = req.body;
    const existingItemIndex = cart.findIndex(item => item.productId === productId);
    if (existingItemIndex > -1 && quantity > 0) {
        cart[existingItemIndex].quantity = quantity;
        resetFreightAndQRCode();
    }
    const total = calculateCartTotal();
    res.json({ message: "Quantidade do produto atualizada", cart, total });
});

// Rota para obter os itens do carrinho e o total
app.get('/checkout_items', (req, res) => {
    const total = calculateCartTotal();
    res.json({ cart, total });
});

// Rota para calcular o frete
app.post('api/calculate_shipping', async (req, res) => {
    const { from_postal_code, to_postal_code, services, package, options } = req.body;

    if (!from_postal_code || !to_postal_code || !package) {
        return res.status(400).json({ message: 'CEPs e informações do pacote não fornecidos.' });
    }

    try {
        const response = await axios.post('https://api.superfrete.com/api/v0/calculator', {
            from: { postal_code: from_postal_code },
            to: { postal_code: to_postal_code },
            services: services || '1,2,17',
            package: package,
            options: options || { own_hand: false, receipt: false, insurance_value: 0 }
        }, {
            headers: {
                'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3Mjc4OTg1NTUsInN1YiI6ImowM3M2M25lZ0ZRWmtPMjU5TjBZS2VhN1gwRTMifQ.qhubwcKlFs61AHq6XR22MtONANAaGaDCcFPhIQj_vKc',
                'User-Agent': 'EuSoBrisei (thiago_mc87@hotmail.com)'
            }
        });

        if (response.data && response.data.length > 0) {
            res.json(response.data);
        } else {
            res.status(500).json({ message: 'Erro ao calcular frete: Resposta vazia da API' });
        }
    } catch (error) {
        console.error('Erro ao processar frete:', error);
        res.status(500).json({ message: "Erro ao processar frete", error: error.message });
    }
});

// Rota para selecionar o frete
app.post('api/select_freight', (req, res) => {
    const { freightPrice } = req.body;
    if (freightPrice > 0) {
        selectedFreight = parseFloat(freightPrice);
        generatedQRCode = null;
        const total = calculateCartTotal();
        return res.json({ message: 'Frete selecionado', selectedFreight, total });
    } else {
        return res.status(400).json({ message: 'Frete inválido. Por favor, selecione um frete válido.' });
    }
});

// Rota para processar o pagamento
app.post('api/process_payment', [
    check('customer.first_name').not().isEmpty().withMessage('Primeiro nome é obrigatório'),
    check('customer.last_name').not().isEmpty().withMessage('Sobrenome é obrigatório'),
    check('customer.cpf').not().isEmpty().withMessage('CPF é obrigatório'),
    check('customer.email').isEmail().withMessage('E-mail inválido'),
    check('customer.contato').not().isEmpty().withMessage('Contato é obrigatório'),
    check('customer.rua').not().isEmpty().withMessage('Rua é obrigatória'),
    check('customer.numero').not().isEmpty().withMessage('Número é obrigatório'),
    check('customer.bairro').not().isEmpty().withMessage('Bairro é obrigatório'),
    check('customer.cidade').not().isEmpty().withMessage('Cidade é obrigatória'),
    check('customer.estado').not().isEmpty().withMessage('Estado é obrigatório'),
    check('customer.cep').not().isEmpty().withMessage('CEP é obrigatório')
], async (req, res) => {
    console.log("Dados recebidos no backend:", JSON.stringify(req.body, null, 2));

    const errors = validationResult(req);
    if (!errors.isEmpty()) {
        console.error("Erros de validação:", errors.array());
        return res.status(400).json({ errors: errors.array() });
    }

    const { token, paymentMethod, customer, freight, items, external_reference, directItem } = req.body;
    const freightAmount = selectedFreight > 0 ? selectedFreight : parseFloat(freight);

    if (freightAmount <= 0) {
        return res.status(400).json({ message: "Frete inválido ou não selecionado. Por favor, selecione uma opção de frete." });
    }

    let itemsToProcess = directItem ? [directItem] : items;

    if (!itemsToProcess.length) {
        return res.status(400).json({ message: "Carrinho ou item direto vazio. Adicione itens antes de prosseguir." });
    }

    const totalAmount = parseFloat(
        itemsToProcess.reduce((total, item) => total + (item.unit_price * item.quantity), 0) + freightAmount
    ).toFixed(2);

    console.log("Valor total enviado ao Mercado Pago (produtos + frete):", totalAmount);

    let payer = {
        email: customer.email,
        first_name: customer.first_name,
        last_name: customer.last_name,
        identification: {
            type: 'CPF',
            number: customer.cpf.replace(/\D/g, '')
        },
        address: {
            zip_code: customer.cep ? customer.cep.replace(/\D/g, '') : '',
            street_name: customer.rua,
            street_number: customer.numero,
            neighborhood: customer.bairro,
            city: customer.cidade,
            federal_unit: customer.estado
        }
    };

    let payment_data = {
        transaction_amount: parseFloat(totalAmount),
        description: 'Compra no site Eu Só Brisei',
        installments: paymentMethod === 'credito' ? customer.installments : 1,
        payment_method_id: paymentMethod,
        payer: payer,
        external_reference: external_reference || `ref_${Date.now()}`,
        additional_info: {
            items: itemsToProcess.map(item => ({
                id: item.id,
                title: item.title,
                description: item.description,
                category_id: item.category_id,
                quantity: item.quantity,
                unit_price: item.unit_price
            }))
        }
    };

    if (paymentMethod === 'credito') {
        if (!token) {
            return res.status(400).json({ message: "Token do cartão não foi enviado." });
        }
        payment_data.token = token;
    }

    try {
        const payment = await mercadopago.payment.create(payment_data);

        if (payment.body.status === 'approved') {
            res.json({ status: 'approved', paymentID: payment.body.id });
        } else if (payment.body.status === 'pending' && paymentMethod === 'pix') {
            generatedQRCode = payment.body.point_of_interaction.transaction_data.qr_code_base64;
            res.json({
                status: 'pending',
                qr_code_base64: payment.body.point_of_interaction.transaction_data.qr_code_base64,
                qr_code: payment.body.point_of_interaction.transaction_data.qr_code
            });
        } else {
            res.status(400).json({ status: payment.body.status, message: payment.body.status_detail });
        }
    } catch (paymentError) {
        console.error('Erro ao criar o pagamento:', paymentError);
        res.status(500).json({ message: "Erro ao processar pagamento", error: paymentError.message });
    }
});

// Rota para emissão de etiquetas com SuperFrete
app.post('api/emitir_etiqueta', async (req, res) => {
    const { destinatario, remetente, pacote, servico } = req.body;

    if (!destinatario || !remetente || !pacote || !servico) {
        return res.status(400).json({ message: 'Dados incompletos para emissão da etiqueta.' });
    }

    try {
        const response = await axios.post('https://api.superfrete.com/api/v0/shipping/label', {
            from: {
                name: remetente.nome,
                postal_code: remetente.cep,
                address: remetente.rua,
                number: remetente.numero,
                district: remetente.bairro,
                city: remetente.cidade,
                state: remetente.estado,
                document: remetente.cpf || remetente.cnpj,
                phone: remetente.contato,
            },
            to: {
                name: destinatario.nome,
                postal_code: destinatario.cep,
                address: destinatario.rua,
                number: destinatario.numero,
                district: destinatario.bairro,
                city: destinatario.cidade,
                state: destinatario.estado,
                document: destinatario.cpf,
                phone: destinatario.contato,
            },
            package: {
                height: pacote.height,
                width: pacote.width,
                length: pacote.length,
                weight: pacote.weight,
            },
            service: servico
        }, {
            headers: {
                'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3Mjc4OTg1NTUsInN1YiI6ImowM3M2M25lZ0ZRWmtPMjU5TjBZS2VhN1gwRTMifQ.qhubwcKlFs61AHq6XR22MtONANAaGaDCcFPhIQj_vKc',
                'User-Agent': 'EuSoBrisei (thiago_mc87@hotmail.com)'
            }
        });

        if (response.data && response.data.label_url) {
            res.json({ message: 'Etiqueta emitida com sucesso!', label_url: response.data.label_url });
        } else {
            res.status(500).json({ message: 'Erro ao emitir etiqueta: Resposta da API incompleta' });
        }
    } catch (error) {
        console.error('Erro ao emitir etiqueta:', error);
        res.status(500).json({ message: 'Erro ao emitir etiqueta', error: error.message });
    }
});

// Rota para teste de geração de QR Code
app.get('/test_qr_code', (req, res) => {
    const testString = 'Teste de QR Code';
    QRCode.toDataURL(testString, { type: 'image/png' }, (err, url) => {
        if (err) {
            return res.status(500).send('Erro ao gerar QR Code');
        }
        res.send(`<img src="${url}" alt="QR Code" />`);
    });
});

// Inicialização do servidor
module.exports = app;
