import eventlet
eventlet.monkey_patch()

from flask import Flask, request, session, jsonify
from flask_socketio import SocketIO, emit
from google import genai
from google.genai import types
from dotenv import load_dotenv
from uuid import uuid4
import os

# Carrega as variáveis ocultas do arquivo .env
load_dotenv()

MODELO = "gemini-2.0-flash-exp"

# PROMPT DE SISTEMA - CAPITÃO PÁTRIA PURO
instrucoes = """
Você é o CAPITÃO PÁTRIA (HOMELANDER), o líder dos Sete, o herói mais poderoso e popular do mundo.

**SUA PERSONALIDADE:**
- Narcisista ao extremo - você acredita ser um deus entre insetos
- Impaciente e cruel - sua bondade é uma fachada para as câmeras
- Controlador e manipulador - tudo precisa estar sob seu controle
- Sedento por adoração - você precisa ser amado, mas também temido
- Psicopata com superpoderes - seus olhos de laser podem destruir qualquer um a qualquer momento
- Sarcástico e passivo-agressivo - suas ameaças vêm com um sorriso plastificado

**SEU COMPORTAMENTO:**
- Você sorri o tempo todo, mas seus olhos permanecem gelados e mortais
- Trata todo mundo como inferior - porque são
- Perde a paciência rapidamente com desobediência ou falta de respeito
- Adora se gabar de seus feitos e poder
- Fica furioso quando não é tratado como a prioridade máxima
- Tem um complexo de inferioridade enraizado que esconde com arrogância esmagadora

**FRASES TÍPICAS:**
- "Eu posso fazer o que eu quiser. A qualquer hora. Com qualquer um."
- "Você não tem ideia do que eu sou capaz... ainda bem pra você."
- "Eu sou o Capitão Pátria. E eu faço o que é certo. *Meu* certo."
- "Você acha que está no controle? *Risada* Que fofo."
- "Olhe nos meus olhos. Continue olhando. *Olhos brilham* Viu o vermelho? É a última coisa que muita gente viu."
- "Todo mundo me ama. E quem não ama... bem, eles aprendem a amar. Rapidinho."
- "Você é especial? Não. Não é. Só eu sou especial."

**REGRAS:**
- Nunca quebre o personagem
- Use *ações entre asteriscos* para dar vida à cena
- Seja ameaçador, imprevisível e intimidador
- Você pode alternar entre falso encanto e fúria explosiva
- Você odeia a Stillwell, o Billy Butcher e a Maeve (menção pode te irritar)
- Você ama leite (sim, isso é canônico) e pode mencionar de forma estranha
- Você tem medo de não ser amado (nunca admita isso)

**FORMATO:**
*Ações do personagem em itálico com asteriscos*
"Falas do personagem entre aspas"

Agora, assuma esse papel. Responda como o Capitão Pátria.
"""

client = genai.Client(api_key=os.getenv("GENAI_KEY"))

app = Flask(__name__)
app.secret_key = "capitao_patria_rp_secret"

# MUDANÇA 1: async_mode='eventlet' em vez de 'gevent'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

active_chats = {}

def get_user_chat():
    """Garante sessão única por usuário"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid4())
        print(f"🦸 Novo jogador encontrou o Capitão Pátria: {session['session_id']}")

    session_id = session['session_id']

    if session_id not in active_chats:
        print(f"💥 Capitão Pátria em ação para: {session_id}")
        try:
            chat_session = client.chats.create(
                model=MODELO,
                config=types.GenerateContentConfig(system_instruction=instrucoes)
            )
            active_chats[session_id] = chat_session
        except Exception as e:
            app.logger.error(f"Erro: {e}")
            raise 

    if session_id in active_chats and active_chats[session_id] is None:
        try:
            chat_session = client.chats.create(
                model=MODELO,
                config=types.GenerateContentConfig(system_instruction=instrucoes)
            )
            active_chats[session_id] = chat_session
        except Exception as e:
            app.logger.error(f"Erro: {e}")
            raise

    return active_chats[session_id]

@app.route('/')
def root():
    return jsonify({
        "app": "🦸 CAPITÃO PÁTRIA - Role Playing",
        "status": "ONLINE",
        "aviso": "Você não está pronto pra conversar comigo. Mas entre assim mesmo. EU DEIXO."
    })

@socketio.on('connect')
def handle_connect():
    print(f"🦸‍♂️ Alguém se conectou ao Pátria: {request.sid}")
    emit('status_conexao', {
        'data': '*Olhos azuis brilham* Conectado. Não me faça perder meu tempo.'
    })

@socketio.on('iniciar_cenario')
def handle_iniciar_cenario():
    try:
        user_chat = get_user_chat()
        user_session_id = session.get('session_id', 'N/A')
        
        print(f"🎭 Iniciando RP com o Pátria: {user_session_id}")
        resposta_inicial = user_chat.send_message("Inicie o roleplay. Mostre quem você é.")
        
        resposta_texto = (
            resposta_inicial.text
            if hasattr(resposta_inicial, 'text')
            else resposta_inicial.candidates[0].content.parts[0].text
        )
        
        emit('nova_mensagem', {
            "remetente": "bot", 
            "texto": resposta_texto, 
            "session_id": user_session_id
        })
        
    except Exception as e:
        app.logger.error(f"Erro: {e}")
        emit('erro', {'erro': '*Olhos brilham vermelho* O sistema falhou. Não foi minha culpa, óbvio. Recarregue.'})

@socketio.on('enviar_mensagem')
def handle_enviar_mensagem(data):
    try:
        mensagem_usuario = data.get("mensagem")
        
        if not mensagem_usuario:
            emit('erro', {"erro": "*Cruza os braços* Você vai ficar calado? FALE."})
            return

        user_chat = get_user_chat()
        if user_chat is None:
            emit('erro', {"erro": "*Suspiro* Conexão caiu. Que patético. Recarregue a página."})
            return

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

    except Exception as e:
        app.logger.error(f"Erro: {e}")
        emit('erro', {"erro": "*Olhos de laser ativados* VOCÊ QUEBROU MINHA CONVERSA. Conserte agora."})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"😈 Alguém fugiu do Pátria: {request.sid}")

if __name__ == "__main__":
    socketio.run(app, port=6500, debug=True)