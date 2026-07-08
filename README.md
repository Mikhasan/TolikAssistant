# Толик Assistant

Этот проект представляет собой пробную версию голосового ассистента «Толик». Код создан в рамках дипломного проекта КАИТ 20 и пока находится на стадии разработки.

## Описание

Проект использует:
- распознавание речи;
- синтез речи;
- взаимодействие с сервисом GigaChat;
- запуск на роботе с ROS.

> Этот репозиторий — не финальная версия продукта, а экспериментальная и учебная разработка для дипломного проекта.

## Важное замечание

В коде используются сторонние библиотеки, которые необходимо установить перед запуском.

## Требования

- Ubuntu / ROS (например, ROS Noetic)
- Python 3.8+
- доступ к сети для работы с GigaChat
- микрофон и динамики/аудио-устройство

## Установка на робота с ROS

1. Обновите систему и установите базовые пакеты:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev portaudio19-dev sox
```

2. Создайте виртуальное окружение:

```bash
python3 -m venv ~/tolik_venv
source ~/tolik_venv/bin/activate
```

3. Установите зависимости Python:

```bash
pip install torch torchaudio requests SpeechRecognition python-dotenv pyaudio
```

4. Перейдите в рабочее пространство ROS и клонируйте репозиторий:

```bash
cd ~/catkin_ws/src
git clone <url_репозитория>
```

5. Загрузите окружение ROS:

```bash
source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash
```

6. Укажите ключ GigaChat:

```bash
cp .env.example .env
```

Затем отредактируйте файл `.env` и задайте значение переменной:

```bash
GIGACHAT_AUTH_KEY=your_key_here
```

7. Запустите проект:

```bash
python3 TolikAssistant.py
```

## Переменные окружения

- `GIGACHAT_AUTH_KEY` — ключ доступа к GigaChat.
- `GIGACHAT_CA_BUNDLE` — необязательно, путь к сертификату, если возникают ошибки SSL.

## Примечание для запуска

При первом запуске может потребоваться время на загрузку моделей синтеза речи.
