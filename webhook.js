const express = require('express');
const app = express();
app.use(express.json());

app.post('/webhook', (req, res) => {
    // Aqui você processa a notificação recebida
    console.log('Notificação recebida:', req.body);
    res.sendStatus(200); // Responde com sucesso
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Servidor rodando na porta ${PORT}`));
