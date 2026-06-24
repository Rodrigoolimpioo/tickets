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
├── app.py              # Backend Flask
├── requirements.txt
├── iniciar.bat         # Atalho Windows
├── instalar.bat        # Instalação Windows
├── data/               # Dados locais (gerados automaticamente)
├── uploads/            # Arquivos anexados aos tickets
├── templates/          # HTML (Jinja2)
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── abrir_ticket.html
│   ├── acompanhamento.html
│   ├── ver_ticket.html
│   ├── configuracoes.html
│   ├── acesso_negado.html
│   └── perfil.html
└── static/
    ├── css/style.css
    └── js/main.js
```

---

## 🛠️ Tecnologias

- **Backend**: Python 3 + Flask
- **Frontend**: HTML5 + Bootstrap 5 + FontAwesome 6
- **Armazenamento**: JSON local
- **Fuso horário**: `pytz` (America/Sao_Paulo)
