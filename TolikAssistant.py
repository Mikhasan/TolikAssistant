"""
Голосовой ассистент "Толик" на базе GigaChat + Silero TTS + speech_recognition.
"""

import os
import sys
import json
import uuid
import subprocess

import torch
import torchaudio
import requests
import speech_recognition as sr

try:
    from dotenv import load_dotenv
    load_dotenv()  # подхватит .env, если он есть рядом со скриптом
except ImportError:
    pass  # dotenv не обязателен, если ключ задан через export

# Ключ авторизации GigaChat (вставлять ваш)

AUTH_KEY = os.environ.get("GIGACHAT_AUTH_KEY")

if not AUTH_KEY:
    sys.exit(
        "Ошибка: не задана переменная окружения GIGACHAT_AUTH_KEY.\n"
        "Задайте её через `export GIGACHAT_AUTH_KEY=...` или файл .env "
        "(см. .env.example)."
    )

GIGACHAT_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

# Сертификат Минцифры нужен, если verify=True падает с SSL-ошибкой на вашей
# машине. Скачивается с https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer
# Путь можно тоже вынести в переменную окружения.
CA_BUNDLE_PATH = os.environ.get("GIGACHAT_CA_BUNDLE")  # может быть None


def get_token(auth_token: str, scope: str = "GIGACHAT_API_PERS"):
    """
    Получить OAuth access_token для GigaChat.
    Возвращает requests.Response при успехе или None при ошибке
    (вместо "1", чтобы можно было делать `if response is None`).
    """
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {auth_token}",
    }
    payload = {"scope": scope}

    try:
        response = requests.post(
            GIGACHAT_OAUTH_URL,
            headers=headers,
            data=payload,
            verify=CA_BUNDLE_PATH if CA_BUNDLE_PATH else True,
            timeout=10,
        )
        response.raise_for_status()
        return response
    except requests.exceptions.SSLError:
        print(
            "SSL-ошибка при получении токена. Если вы в РФ и используете "
            "сертификат Минцифры, задайте GIGACHAT_CA_BUNDLE=путь_к_сертификату."
        )
        return None
    except requests.exceptions.RequestException as exc:
        print(f"Ошибка при получении токена: {exc}")
        return None


def get_chat_completion(auth_token, user_message, conversation_history=None):
    """
    Отправить сообщение пользователя в GigaChat с учётом истории диалога.
    Возвращает (response, updated_history) или (None, history) при ошибке.
    """
    if conversation_history is None:
        conversation_history = []

    conversation_history.append({"role": "user", "content": user_message})

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {auth_token}",
    }
    payload = {
        "model": "GigaChat",
        "messages": conversation_history,
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            GIGACHAT_CHAT_URL,
            headers=headers,
            data=json.dumps(payload),
            verify=CA_BUNDLE_PATH if CA_BUNDLE_PATH else True,
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        print(f"Ошибка при обращении к GigaChat: {exc}")
        return None, conversation_history

    try:
        assistant_message = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError):
        print("Некорректный ответ от GigaChat, пропускаем.")
        return None, conversation_history

    conversation_history.append({"role": "assistant", "content": assistant_message})
    return response, conversation_history


def save_audio(audioout, sample_rate, path):
    torchaudio.save(path, audioout.unsqueeze(0), sample_rate)


def play_audio(path):
    subprocess.call(["play", path])


def listen(prompt_text, mic_index=2, language="ru-RU", timeout=None, phrase_time_limit=None):
    """
    Единая функция распознавания речи (заменяет zapicbidet / zapicbidetTolik,
    которые дублировали друг друга).
    prompt_text печатается в консоль, чтобы пользователь понимал, чего ждёт ассистент.
    Возвращает распознанный текст (в нижнем регистре) или "" при ошибке/тишине.
    """
    r = sr.Recognizer()
    try:
        mic = sr.Microphone(device_index=mic_index)
    except OSError:
        print(f"Не найден микрофон с индексом {mic_index}.")
        print("Доступные микрофоны:", sr.Microphone.list_microphone_names())
        return ""

    print(prompt_text)
    with mic as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            print("Не услышал речи (тайм-аут).")
            return ""

    try:
        text = r.recognize_google(audio, language=language)
        return text.lower()
    except sr.UnknownValueError:
        print("Не удалось распознать речь.")
        return ""
    except sr.RequestError as exc:
        print(f"Ошибка сервиса распознавания речи: {exc}")
        return ""


def contains_any(text: str, words) -> bool:
    """Регистронезависимая проверка на вхождение любого из слов в текст."""
    text_low = text.lower()
    return any(word.lower().rstrip(".") in text_low for word in words)


def speak(model, text, sample_rate, speaker, put_accent, out_path="output.mp3"):
    audioout = model.apply_tts(
        text=text,
        speaker=speaker,
        sample_rate=sample_rate,
        put_accent=put_accent,
    )
    save_audio(audioout, sample_rate, out_path)
    play_audio(out_path)


def main():
    language = "ru"
    model_id = "ru_v3"
    sample_rate = 48000
    speaker = "aidar"
    put_accent = True

    device = torch.device("cpu")
    torch.backends.quantized.engine = "qnnpack"

    print("Загружаю модель синтеза речи...")
    model, _ = torch.hub.load(
        repo_or_dir="snakers4/silero-models",
        model="silero_tts",
        language=language,
        speaker=model_id,
    )
    model.to(device)

    wake_words = ["толик"]
    exit_words = ["выход"]

    system_prompt = {
        "role": "system",
        "content": (
            "Ты - робот Толик на операционной системе ROS, с которым можно "
            "поговорить. Ты знаешь очень много интересных историй, шаришь за "
            "психологию и в целом клевый собеседник. Ты умеешь отвечать на "
            "вопросы пользователя, а так же понимаешь язык программирования "
            "python. Если собеседник говорит, что хочет закончить разговор, "
            "вежливо попрощайся."
        ),
    }

    print("Готов. Скажите 'Толик', чтобы начать разговор.")
    while True:
        user_text = listen("Слушаю... (ожидаю слово 'Толик')")

        if not contains_any(user_text, wake_words):
            if user_text:
                print(f"Слово 'Толик' не услышано (сказано: '{user_text}'). Пробуем снова.")
            continue

        print("Слово найдено! Начинаю диалог.")
        speak(model, "Я тебя слушаю", sample_rate, speaker, put_accent)

        conversation_history = [system_prompt]
        giga_token = None

        while True:
            user_text = listen("Говорите (или скажите 'выход', чтобы закончить)...")
            if not user_text:
                continue

            # Пользователь сам решает завершить диалог — проверяем то,
            # что сказал ОН, а не ответ модели.
            if contains_any(user_text, exit_words):
                print("Выход из диалога, до новых встреч.")
                speak(model, "До новых встреч!", sample_rate, speaker, put_accent)
                break

            token_response = get_token(AUTH_KEY)
            if token_response is None:
                print("Не удалось получить токен доступа, пропускаю реплику.")
                continue
            giga_token = token_response.json()["access_token"]

            chat_response, conversation_history = get_chat_completion(
                giga_token, user_text, conversation_history
            )
            if chat_response is None:
                print("Не удалось получить ответ от GigaChat, пропускаю реплику.")
                continue

            otvet = conversation_history[-1]["content"]
            print("Толик:", otvet)

            speak(model, otvet, sample_rate, speaker, put_accent)


if __name__ == "__main__":
    main()
