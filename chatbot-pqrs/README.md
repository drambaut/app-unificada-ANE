# 🤖 ANE - Asistente de Redacción de PQRs

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B)
![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-AI-8E75B2)
![License](https://img.shields.io/badge/License-MIT-green)

Este proyecto es una herramienta asistida por Inteligencia Artificial diseñada para facilitar a los operarios de la **Agencia Nacional del Espectro (ANE)** la radicación y respuesta de Peticiones, Quejas y Reclamos (PQRs). Utilizando procesamiento de lenguaje natural, el chatbot interactúa con el usuario, extrae las entidades clave y genera automáticamente un documento formal `.docx` listo para descargar.

## ✨ Características Principales

- **Interfaz Conversacional:** Un chat fluido impulsado por **Streamlit** que guía al usuario en la estructuración de su respuesta.
- **Extracción Inteligente:** Integración con **Google Gemini 2.5 Flash** para identificar automáticamente: Nombre, Cargo, Empresa, Ciudad, Asunto y los datos del Firmante.
- **Redacción Institucional:** El modelo está pre-configurado (System Prompt) para redactar el cuerpo de la carta utilizando el tono formal y jurídico de la ANE.
- **Generación Documental Dinámica:** Uso de `docxtpl` para inyectar los datos extraídos directamente en una plantilla oficial de Word.
- **Vista Previa y Edición:** Panel lateral que permite al usuario revisar y ajustar manualmente la información antes de generar el documento final.

## 📂 Estructura del Proyecto

```text
Chatbot-para-PQRs-ANE/
├── app/
│   └── main.py                 # Script principal de la aplicación Streamlit
├── templates/
│   └── plantillaPQR.docx       # Plantilla oficial de Word con etiquetas Jinja2
├── .env.example                # Variables de entorno de referencia
├── requirements.txt            # Dependencias del proyecto
└── README.md                   # Documentación
```

## 🚀 Instalación y Despliegue

### Requisitos previos
- Python 3.9 o superior.
- Una API Key de Google Gemini.

### Paso a paso

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/drambaut/Chatbot-para-PQRs---ANE.git
   cd Chatbot-para-PQRs-ANE
   ```

2. **Crear y activar un entorno virtual:**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instalar las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar las variables de entorno:**
   - Duplica el archivo `.env.example` y renómbralo a `.env`.
   - Reemplaza el valor con tu clave real:
     ```env
     GOOGLE_API_KEY=tu_api_key_aqui
     ```

5. **Ejecutar la aplicación:**
   ```bash
   streamlit run app/main.py
   ```

## 🧠 Funcionamiento del Prompt Engineering

El proyecto utiliza un enfoque de **Extracción de Datos Estructurados (JSON)**. A medida que el usuario conversa, el LLM es instruido para devolver un bloque JSON con las llaves exactas (`NOMBRE`, `EMPRESA`, `FIRMANTE_CARGO`, etc.) que hacen *match* con las variables contenidas en `plantillaPQR.docx`. Esto garantiza que los datos viajen desde el lenguaje natural hasta el documento de Word sin fricción.

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - mira el archivo [LICENSE](LICENSE) para más detalles.

---
*Desarrollado para optimizar la gestión documental y técnica.*