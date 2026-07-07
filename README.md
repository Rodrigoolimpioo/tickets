# 🎫 Sistema Tickets

Sistema web de gerenciamento de chamados (tickets) para empresas de alimentação, com suporte aos sistemas **Teknisa**, **Kdápio (Callcenter)**, **Lumia** e **iFood**.

---

## ✅ Funcionalidades

- **Abertura de tickets** com nome, sistema afetado, descrição da ocorrência e anexo (foto/vídeo)
- **Numeração automática** no formato `TKT-0001`
- **Data/hora de Brasília** registrada automaticamente
- **Acompanhamento** com filtros por status, sistema e busca
- **Histórico** completo de atualizações em cada ticket
- **3 perfis de acesso**: Administrador, Supervisor, Funcionário
- **Controle de IP**: restrinja o acesso por endereço IP
- **Controle de horários**: defina janelas de acesso por dia da semana (horário de Brasília)
- **Armazenamento local** em arquivos JSON — sem banco de dados

---

## 🚀 Como rodar

### Pré-requisitos
- Python 3.9 ou superior
- pip

### Instalação
```bash
git clone https://github.com/seu-usuario/tickets_system.git
cd tickets_system
py -m pip install -r requirements.txt
```

### Iniciar o servidor
```bash
py app.py
```
Acesse em: **http://localhost:5000**

> No Windows, dê duplo clique em `iniciar.bat`.

---

## 👤 Usuários padrão

| Usuário | Senha | Perfil |
|---|---|---|
| `admin` | `admin123` | Administrador |
| `supervisor` | `super123` | Supervisor |
| `funcionario` | `func123` | Funcionário |

> ⚠️ Troque as senhas padrão após o primeiro acesso em **Configurações → Usuários**.

---

## 🔐 Perfis de Acesso

| Funcionalidade | Funcionário | Supervisor | Admin |
|---|:---:|:---:|:---:|
| Abrir ticket | ✅ | — | ✅ |
| Ver próprios tickets | ✅ | — | — |
| Ver todos os tickets | — | ✅ | ✅ |
| Atualizar status | — | ✅ | ✅ |
| Configurações / Usuários | — | — | ✅ |
| Controle de IP | — | — | ✅ |
| Controle de Horários | — | — | ✅ |

---

## 📁 Estrutura do Projeto

```
tickets_system/
├── backend/
│   ├── app.py                    # Application factory: registra os blueprints e os middlewares
│   ├── requirements.txt
│   ├── .env.example
│   ├── core/                      # Regras/infra compartilhadas por todos os controllers
│   │   ├── config.py              # Constantes, paths, módulos do sistema (PERMISSOES)
│   │   ├── security.py            # Hash de senha, CSRF, decorators de sessão e de JWT
│   │   ├── storage.py              # Leitura/gravação dos JSONs (users, tickets, config)
│   │   ├── time_utils.py
│   │   └── services/               # Regras de negócio reaproveitadas pelo web e pela API
│   │       ├── usuarios_service.py
│   │       └── perfis_service.py
│   ├── controllers/                 # Um controller (Blueprint) por módulo de tela/rota
│   │   ├── auth_controller.py       # /login /logout (sessão)
│   │   ├── dashboard_controller.py  # /dashboard
│   │   ├── tickets_controller.py    # /abrir-ticket /acompanhamento /ticket/...
│   │   ├── config_controller.py     # /configuracoes (ips, horários, sistemas, personalização)
│   │   ├── usuarios_controller.py   # CRUD de usuários (telas web)
│   │   ├── perfis_controller.py     # CRUD de perfis de acesso (telas web)
│   │   ├── misc_controller.py       # /meu-perfil /uploads/<f> /logo
│   │   └── api_controller.py        # /api/* — autenticação e CRUD via JWT (ver abaixo)
│   ├── data/                        # Dados locais (gerados automaticamente)
│   └── uploads/                     # Arquivos anexados aos tickets
├── frontend/
│   ├── templates/                   # HTML (Jinja2)
│   └── static/
│       ├── css/style.css
│       └── js/main.js
├── iniciar.bat                      # Atalho Windows
└── instalar.bat                     # Instalação Windows
```

As telas (Jinja2 + sessão/cookie) continuam funcionando exatamente como antes.
A API em `/api/*` é uma camada adicional, autenticada por token, pensada para
uma futura SPA, app mobile ou integração externa que precise do mesmo modelo
de permissões sem depender de cookies.

---

## 🔑 API com token JWT

Gerar um token informando usuário e senha — o token carrega como *claims*
o `role` e a lista de módulos (`permissoes`) liberados para aquele usuário,
de acordo com o perfil de acesso dele:

```bash
curl -X POST http://localhost:5000/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 28800,
  "user": { "id": "1", "username": "admin", "role": "admin", "permissoes": ["dashboard", "..."] }
}
```

Use o token no header `Authorization: Bearer <token>` nas chamadas seguintes:

| Rota | Método | Descrição |
|---|---|---|
| `/api/auth/token` | POST | Gera o token a partir de usuário/senha |
| `/api/auth/me` | GET | Retorna as claims do token atual |
| `/api/modulos` | GET | Lista os módulos do sistema e se o token tem acesso a cada um |
| `/api/stats` | GET | Estatísticas de tickets (respeita a permissão `dashboard`) |
| `/api/perfis` | GET/POST | Lista/cria perfis de acesso (somente admin) |
| `/api/perfis/<id>` | PUT/DELETE | Edita/exclui um perfil de acesso (somente admin) |
| `/api/usuarios` | GET/POST | Lista/cria usuários (somente admin) |
| `/api/usuarios/<id>/toggle` \| `/senha` \| `/perfil` | POST | Ativa/desativa, troca senha, troca perfil do usuário |
| `/api/usuarios/<id>` | DELETE | Exclui um usuário |

Os perfis de acesso (Admin / Supervisor / Funcionário, ou qualquer perfil
customizado criado depois) são **parametrizáveis a qualquer momento** — tanto
pela tela de Configurações → Perfis quanto pelos endpoints acima — e o
efeito é imediato tanto na sessão web quanto em qualquer token novo emitido.

---

## 🛠️ Tecnologias

- **Backend**: Python 3 + Flask (Blueprints por módulo) + PyJWT
- **Frontend**: HTML5 + Bootstrap 5 + FontAwesome 6
- **Armazenamento**: JSON local
- **Fuso horário**: `pytz` (America/Sao_Paulo)
