# Notify — recebimento de webhooks do SGE

O Notify é o complemento do [SGE](https://github.com/marcusvgcruz/sge) para
avisos. O SGE cuida do estoque e, a cada saída registrada, envia um POST para o
Notify. O Notify guarda o evento no banco e avisa na hora por dois canais:
WhatsApp (via CallMeBot) e e-mail (SMTP).

## Para quem serve

Para quem usa o SGE e quer saber da venda sem abrir a tela: o dono recebe a
mensagem no WhatsApp, a administração recebe o e-mail, e o evento fica registrado
para consulta depois.

## Como funciona

1. O SGE registra uma saída e faz `POST /api/v1/webhooks/order/`.
2. O Notify grava o evento na tabela `Webhook` (tipo do evento e o JSON recebido).
3. Calcula o valor da venda (`preço de venda × quantidade`) e o lucro
   (`valor da venda − custo × quantidade`).
4. Envia a mensagem de WhatsApp pelo CallMeBot.
5. Envia o e-mail em HTML para o endereço configurado.
6. Devolve o payload recebido acrescido de `total_value` e `profit_value`.

## Como rodar

```bash
git clone https://github.com/marcusvgcruz/notify.git
cd notify

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp app/.env.example .env     # edite as variáveis; o .env fica na raiz do projeto

python manage.py migrate
python manage.py runserver 8001
```

A porta 8001 é a que o SGE espera na configuração atual. Para usar outra, ajuste
a URL base em `services/notify.py` do SGE (ou aponte pelo proxy da sua rede).

## Configuração (`.env`)

| Variável | Para que serve |
| :--- | :--- |
| `CALLMEBOT_API_URL` | endereço do CallMeBot: `https://api.callmebot.com/whatsapp.php` |
| `CALLMEBOT_PHONE_NUMBER` | número com DDI e DDD que recebe o WhatsApp |
| `CALLMEBOT_API_KEY` | chave da API do CallMeBot |
| `EMAIL_HOST` | servidor SMTP do seu provedor de e-mail |
| `EMAIL_PORT` | porta SMTP (587 no exemplo) |
| `EMAIL_HOST_USER` | conta que envia o e-mail |
| `EMAIL_HOST_PASSWORD` | senha dessa conta |
| `EMAIL_ADMIN_RECEIVER` | quem recebe o e-mail de aviso |
| `SECRET_KEY` | chave de segurança do Django (obrigatória; gere uma nova, não reutilize a de outro projeto) |
| `DEBUG` | `True`/`False` — default `False` (seguro para produção) |
| `ALLOWED_HOSTS` | hosts permitidos, separados por vírgula — default `localhost,127.0.0.1` |

`EMAIL_ADMIN_RECEIVER` é obrigatória — quem recebe o e-mail de aviso. Ela já vem
no `.env.example`; preencha o endereço ao criar o seu `.env`, senão a aplicação
não sobe.

### Sobre o envio de e-mail

O `app/settings.py` usa o backend de console
(`django.core.mail.backends.console.EmailBackend`): a mensagem é impressa no
terminal onde o servidor roda e não sai por SMTP. Para enviar de verdade, troque
para `django.core.mail.backends.smtp.EmailBackend`; as variáveis `EMAIL_HOST`,
`EMAIL_PORT`, `EMAIL_HOST_USER` e `EMAIL_HOST_PASSWORD` já estão no `.env`.

No Django 6.1, definir `MAILERS` junto com as variáveis `EMAIL_HOST*` provoca
`ImproperlyConfigured` na subida — por isso o projeto fica no backend clássico.

## Endpoint

```
POST /api/v1/webhooks/order/
```

Exemplo de corpo, no formato que o SGE envia:

```json
{
  "event_type": "create_outflow",
  "timestamp": "2026-11-10 14:32:05",
  "product": "Camisa Polo M",
  "product_cost_price": 39.90,
  "product_selling_price": 89.90,
  "quantity": 2,
  "description": "Venda no balcão"
}
```

Resposta `200` com o mesmo conteúdo mais os dois totais calculados:

```json
{
  "event_type": "create_outflow",
  "timestamp": "2026-11-10 14:32:05",
  "product": "Camisa Polo M",
  "product_cost_price": 39.90,
  "product_selling_price": 89.90,
  "quantity": 2,
  "description": "Venda no balcão",
  "total_value": 179.8,
  "profit_value": 100.0
}
```

## Eventos

Hoje o único evento em uso é `create_outflow`, enviado a cada saída registrada no
SGE. O campo `event_type` é livre (até 50 caracteres) e o Notify grava qualquer
valor que chegar, mas a mensagem de WhatsApp e o template do e-mail são os de
saída — um evento novo exige ajuste em `webhooks/messages.py` e no template.

## Como apontar o SGE para o Notify

No SGE, a URL base fica em `services/notify.py`:

```python
self.__base_url = 'http://localhost:8001'
```

Com o Notify rodando na porta 8001, na mesma máquina do SGE, a configuração atual
já funciona. Para outro endereço, altere essa URL no SGE.

## Limites e cuidados

- O endpoint não tem autenticação. Rode em rede interna ou proteja com proxy
  reverso antes de expor na internet.
- Não há fila nem retentativa. Se o CallMeBot ou o SMTP falhar, a requisição
  retorna erro e o evento fica apenas se já tiver sido gravado.
- O e-mail, como está, não sai do servidor: o backend é o de console (veja a
  seção de configuração).
- O histórico fica no SQLite (`db.sqlite3`), na tabela `Webhook`, consultável
  pelo admin do Django.
- `SECRET_KEY`, `DEBUG` e `ALLOWED_HOSTS` vêm do `.env` (veja a tabela acima);
  `DEBUG` e `ALLOWED_HOSTS` têm defaults seguros (`False` e `localhost,127.0.0.1`),
  mas a `SECRET_KEY` é obrigatória — sem ela a aplicação não sobe. Nunca
  commite o `.env`.

## Estrutura

```
app/        settings, urls e wsgi/asgi
webhooks/   model Webhook, view do endpoint, mensagem e template do e-mail
services/   client do CallMeBot
```

## Licença

Repositório pessoal de Marcus Cruz, sem licença declarada.
