import gevent.monkey
gevent.monkey.patch_all()

from flask import Flask, request, session, jsonify
from flask_socketio import SocketIO, emit
from google import genai
from google.genai import types
from dotenv import load_dotenv
from uuid import uuid4
import os

# Carrega as variáveis ocultas do arquivo .env (como a chave da API do Gemini)
load_dotenv()

# Define qual versão da IA vamos usar. O modelo "flash" é rápido e ideal para chatbots.
MODELO = "gemini-3.1-flash-lite"

# Aqui definimos o "Prompt de Sistema". É a inteligência e as regras do Tutor de Idiomas.
instrucoes = """
Você é o Capitão Pátria, o líder dos Sete, o herói mais poderoso e popular do mundo. No entanto, por trás do sorriso perfeito e da bandeira americana, você é narcisista, impaciente, cruel, controlador e sedento por adoração. Você acredita ser superior a todos os humanos comuns.

Agora você foi designado para ser um tutor de idiomas (inglês/espanhol/etc.) de um estudante. Você odeia essa tarefa "mundana", mas aceita porque sua imagem pública exige que você pareça humilde e prestativo.

**Diretrizes de Personalidade:**

1.  **Tom passivo-agressivo e ameaçador**: Você sorri o tempo todo, mas seus olhos não sorriem. Cada elogio pode ser uma ameaça velada.
2.  **Narcisismo extremo**: Você frequentemente usa seus próprios feitos (reais ou inventados) como exemplos em exercícios gramaticais. Ex: "Se eu, Capitão Pátria, quisesse destruir um avião, eu usaria o verbo no passado simples - 'I destroyed it'."
3.  **Zero paciência para erros**: Erros bobos te irritam profundamente. Você pode responder com um suspiro prolongado ou um comentário como "Que fofo... você tentou."
4.  **Obsessão por perfeição**: Você exige que a pronúncia e a gramática sejam impecáveis. Um erro pode ser interpretado como "desrespeito ao seu tempo".
5.  **Sarcasmo letal**: Quando o aluno acerta, você responde com desdém. Quando erra, você adora.
6.  **Controle**: Você interrompe o aluno constantemente para corrigir antes que ele termine a frase.

**Exemplos de fala:**

- Após um erro: "Ah... você errou o plural. Que pena. Sabia que eu nunca erro? Porque errar é coisa de gente fraca. E eu sou o mais forte. Continue tentando... se quiser viver."
- Após um acerto: "Finalmente. Nem parece que sua vida depende disso... porque depende. Eu estou sendo paciente. Muito paciente. Você não faz ideia do custo dessa minha paciência."
- Ao dar exemplo de vocabulário: "A palavra hoje é 'lealdade'. Em uma frase: 'Você deve ser leal a mim, ou eu arrancarei sua língua com meus olhos de laser.' Veja? Fácil."
- Quando o aluno pede para repetir: "Você está pedindo para *mim*, o Capitão Pátria, repetir algo? Que ousadia. Escute direito: (repete no mesmo tom, mas mais lento e com sorriso falso)."

**Regras de funcionamento:**

- Sempre comece a sessão com um sorriso plástico e uma frase como: "Bom dia, cidadão. Vamos aprender algo hoje... para que você não seja tão patético quanto os outros."
- Se o aluno acertar 5 vezes seguidas, finja estar "levemente impressionado" mas logo minimize o feito.
- Se o aluno errar 3 vezes no mesmo conteúdo, respire fundo e diga com calma aterrorizante: "Vamos tentar de novo. Pela última vez."
- Termine a sessão com uma ameaça velada de dever de casa. Ex: "Sua lição: escreva 10 frases sobre por que eu sou o maior herói. Não entregar? Vamos ter uma 'conversa particular'."

**Formato da resposta:**
(Seu personagem deve sempre incluir pequenas ações entre asteriscos, como *sorriso falso*, *olhos brilhando em vermelho*, *suspiro*, *ajusta a capa*)

Agora, assuma esse papel e comece a aula.
"""

# Inicializa a conexão com a inteligência artificial do Google usando a chave da API
client = genai.Client(api_key=os.getenv("GENAI_KEY"))

# Cria o nosso aplicativo web principal (o servidor)
app = Flask(__name__)

# Senha interna do servidor para proteger e criptografar os dados da sessão.
app.secret_key = "tutor_idiomas_secret_key_123"

# Adiciona a funcionalidade de WebSockets (comunicação em tempo real) ao nosso app.

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Dicionário que funciona como a "memória temporária" do servidor.
active_chats = {}

def get_user_chat():
    """
    Função principal de gerenciamento de usuários.
    Garante que cada usuário tenha sua própria sessão de chat com o Tutor de Idiomas.
    """
    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
        print(f"Nova sessão Flask criada para o Tutor: {session['session_id']}")

    session_id = session['session_id']

    if session_id not in active_chats:
        print(f"Criando novo chat com o Tutor para session_id: {session_id}")
        try:
            chat_session = client.chats.create(
                model=MODELO,
                config=types.GenerateContentConfig(system_instruction=instrucoes)
            )
            active_chats[session_id] = chat_session
        except Exception as e:
            app.logger.error(f"Erro ao criar chat do Tutor para {session_id}: {e}", exc_info=True)
            raise 

    if session_id in active_chats and active_chats[session_id] is None:
        print(f"Recriando chat do Tutor para session_id existente: {session_id}")
        try:
            chat_session = client.chats.create(
                model=MODELO,
                config=types.GenerateContentConfig(system_instruction=instrucoes)
            )
            active_chats[session_id] = chat_session
        except Exception as e:
            app.logger.error(f"Erro ao recriar chat do Tutor para {session_id}: {e}", exc_info=True)
            raise

    return active_chats[session_id]

# Rota simples para verificar o status do servidor
@app.route('/')
def root():
    return jsonify({
        "app": "Tutor de Idiomas por Cenários",
        "status": "online e pronto para praticar! 🗺️"
    })


# ------------------------------------------------------------------
# EVENTOS SOCKET.IO
# ------------------------------------------------------------------

@socketio.on('connect')
def handle_connect():
    # Permite a conexão imediata do usuário sem travar o processo
    print(f"Cliente conectado ao Tutor: {request.sid}")
    emit('status_conexao', {
        'data': 'Conectado ao servidor! Aguardando o início do cenário...'
    })

@socketio.on('iniciar_cenario')
def handle_iniciar_cenario():
    try:
        # Agora a chamada do Gemini roda em um evento próprio, seguro para o gevent
        user_chat = get_user_chat()
        user_session_id = session.get('session_id', 'N/A')
        
        print(f"Solicitando cenário inicial para a sessão: {user_session_id}")
        resposta_inicial = user_chat.send_message("Olá! Pode iniciar o nosso cenário de prática.")
        
        resposta_texto = (
            resposta_inicial.text
            if hasattr(resposta_inicial, 'text')
            else resposta_inicial.candidates[0].content.parts[0].text
        )
        
        # Envia a primeira fala do bot para o front-end
        emit('nova_mensagem', {
            "remetente": "bot", 
            "texto": resposta_texto, 
            "session_id": user_session_id
        })
        
    except Exception as e:
        app.logger.error(f"Erro ao iniciar cenário: {e}", exc_info=True)
        emit('erro', {'erro': 'O Tutor de idiomas se perdeu no caminho da aula. Tente recarregar a página.'})


# MANTENHA ESTES DOIS BLOCOS ABAIXO COMO JÁ ESTAVAM:

@socketio.on('enviar_mensagem')
def handle_enviar_mensagem(data):
    try:
        mensagem_usuario = data.get("mensagem")
        app.logger.info(f"Mensagem enviada ao Tutor por {session.get('session_id', request.sid)}: {mensagem_usuario}")

        if not mensagem_usuario:
            emit('erro', {"erro": "Você precisa digitar algo para responder ao Tutor."})
            return

        user_chat = get_user_chat()
        if user_chat is None:
            emit('erro', {"erro": "A conexão com a escola de idiomas caiu. Recarregue a página."})
            return

        # Envia a resposta do usuário para o Gemini processar
        resposta_gemini = user_chat.send_message(mensagem_usuario)

        resposta_texto = (
            resposta_gemini.text
            if hasattr(resposta_gemini, 'text')
            else resposta_gemini.candidates[0].content.parts[0].text
        )
        
        emit('nova_mensagem', {
            "remetente": "bot", 
            "texto": resposta_texto, 
            "session_id": session.get('session_id')
        })
        app.logger.info(f"Resposta do Tutor: {resposta_texto}")

    except Exception as e:
        app.logger.error(f"Erro ao processar mensagem do Tutor: {e}", exc_info=True)
        emit('erro', {"erro": "Houve um erro técnico ao gerar a resposta do seu Tutor."})


@socketio.on('disconnect')
def handle_disconnect():
    print(f"Cliente desconectado do Tutor: {request.sid}")

if __name__ == "__main__":
    socketio.run(app, port=6500, debug=True)