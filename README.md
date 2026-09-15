<div align="center">



\# 👻 FANTASMITA



\### 🌌 Bot oficial de \*\*El Eco del Vacío\*\*



Un bot de Discord creado para administrar, automatizar y darle vida a la comunidad \*\*El Eco del Vacío\*\*.



!\[Python](https://img.shields.io/badge/Python-3.11-blue?logo=python\&logoColor=white)

!\[Discord](https://img.shields.io/badge/Discord.py-2.7-5865F2?logo=discord\&logoColor=white)

!\[Status](https://img.shields.io/badge/Status-En%20Desarrollo-purple)

!\[License](https://img.shields.io/badge/Uso-Privado-darkred)



\---



\### 👻



\*\*Bienvenido al vacío.\*\*



\*Donde otros bots terminan... Fantasmita apenas comienza.\*



</div>



\## 🌌 ¿Qué es Fantasmita?



\*\*Fantasmita\*\* es un bot multifunción desarrollado especialmente para el servidor de Discord \*\*El Eco del Vacío\*\*.



El proyecto busca centralizar gran parte de la administración y las funciones de la comunidad en un solo bot, incluyendo sistemas de acceso, moderación, música, economía, progresión, tickets, canales de voz privados y herramientas administrativas.



El bot está desarrollado principalmente con \*\*Python\*\* y \*\*discord.py\*\*.



\---



\## ✨ Funcionalidades



\### 🚪 Sistema de acceso



\- 📜 Aceptación de términos

\- 📨 Solicitudes de acceso

\- 👑 Aprobación por el propietario

\- 🔐 Control automático de permisos

\- 🎭 Asignación de roles



\### 🛡️ Moderación y seguridad



\- 🔨 Herramientas de moderación

\- 🔒 Control de permisos

\- 📋 Registro de acciones

\- 🕵️ Sistema de auditoría

\- ⚠️ Manejo de errores



\### 🎫 Sistema de tickets



\- 🎟️ Creación automática de tickets

\- 🔐 Canales privados

\- ❌ Cierre de tickets

\- 🆘 Sistema de soporte



\### 🎧 Salas de voz privadas



\- ➕ Creación automática de salas

\- 🔒 Bloquear/desbloquear sala

\- 👥 Administración de usuarios

\- 🎛️ Panel de control de voz



\### 🎵 Sistema de música



\- ▶️ Reproducción de música

\- ⏸️ Controles de reproducción

\- 🎶 Integración con canales de voz

\- 🔊 Sistema basado en `yt-dlp`



\### 🪙 Economía y progresión



\- 💰 Sistema de economía

\- 📈 Progresión de usuarios

\- 🎮 Roles de comunidad

\- 🏆 Sistema competitivo



\### 👑 Panel del fundador



Herramientas especiales para la administración de \*\*El Eco del Vacío\*\*.



\- 🎭 Administración de roles

\- 👤 Selección de usuarios

\- ➕ Asignación de roles

\- ➖ Eliminación de roles

\- 📊 Auditoría

\- 🔐 Acceso restringido al propietario



\---



\## 🏗️ Estructura del proyecto



```text

Fantasmita/

│

├── main.py

├── selftest.py

├── requirements.txt

│

├── core/

│

├── views/

│

├── cogs/

│   ├── community

│   ├── economy

│   ├── moderation

│   ├── owner

│   ├── voice

│   ├── social

│   ├── tickets

│   ├── security

│   ├── events

│   ├── cleanup

│   ├── music

│   ├── progression

│   ├── competitive

│   └── integrations

│

├── data/

└── backups/

```



\---



\## ⚙️ Tecnologías



| Tecnología | Uso |

|---|---|

| 🐍 Python | Lenguaje principal |

| 🤖 discord.py | API de Discord |

| 🎵 yt-dlp | Sistema multimedia |

| 🔊 PyNaCl | Audio de Discord |

| 🎬 imageio-ffmpeg | Procesamiento de audio |

| 🗃️ SQLite | Base de datos |

| 🐙 GitHub | Control de versiones |



\---



\## 🚀 Instalación



\### 1. Clonar el repositorio



```bash

git clone https://github.com/abrahammoraxbox-ship-it/fantasmita.git

```



\### 2. Entrar al proyecto



```bash

cd fantasmita

```



\### 3. Instalar dependencias



```bash

pip install -r requirements.txt

```



\### 4. Configurar el token



El bot necesita la variable:



```text

DISCORD\_TOKEN

```



El token debe almacenarse de forma segura como variable de entorno o dentro de un archivo `.env` configurado para el entorno correspondiente.



> \[!CAUTION]

> \*\*Nunca publiques el token del bot en GitHub.\*\*

>

> El archivo `.env` debe permanecer fuera del repositorio mediante `.gitignore`.



\### 5. Iniciar Fantasmita



```bash

python main.py

```



\---



\## ☁️ Hosting



Fantasmita está preparado para ejecutarse en un servidor Python utilizando:



```text

Python 3.11+

```



El despliegue puede mantenerse sincronizado mediante GitHub:



```text

PyCharm / PC

&#x20;     │

&#x20;     │ git push

&#x20;     ▼

&#x20;  GitHub

&#x20;     │

&#x20;     │ git pull

&#x20;     ▼

&#x20;  Hosting

&#x20;     │

&#x20;     ▼

&#x20;👻 Fantasmita

```



De esta manera, los cambios realizados en el proyecto pueden versionarse en GitHub y posteriormente desplegarse en el servidor.



\---



\## 🔐 Seguridad



Este repositorio \*\*nunca debe contener\*\*:



```text

Discord Bot Token

GitHub Personal Access Token

Contraseñas

Credenciales privadas

Archivos .env con secretos

```



Ejemplo recomendado para `.gitignore`:



```gitignore

.env

\_\_pycache\_\_/

\*.pyc

data/\*.db

backups/

```



\---



\## 🧪 Self-Test



Fantasmita incorpora un sistema de comprobación durante el inicio para detectar problemas importantes antes de conectarse completamente a Discord.



```text

SELFTEST

&#x20;  ↓

Estructura

&#x20;  ↓

Seguridad

&#x20;  ↓

SQLite

&#x20;  ↓

Carga de módulos

&#x20;  ↓

👻 Fantasmita

```



\---



\## 🌌 El Eco del Vacío



Fantasmita fue desarrollado específicamente para:



> \*\*🌌 El Eco del Vacío\*\*



Una comunidad enfocada en gaming, conversación, eventos y entretenimiento.



\---



\## 👨‍💻 Autor



\*\*Carlos Abraham Mora Rentería\*\*



🎮 Xbox: `Abraham4821`  

📺 Twitch: `el\_\_fantasmita`  

🐙 GitHub: \[abrahammoraxbox-ship-it](https://github.com/abrahammoraxbox-ship-it)



\---



<div align="center">



\## 👻 FANTASMITA



\*\*El guardián de El Eco del Vacío\*\*



`Python • Discord.py • SQLite • GitHub`



🌌 \*\*EL ECO DEL VACÍO\*\* 🌌



</div>

