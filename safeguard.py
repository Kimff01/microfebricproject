import speech_recognition as sr
from twilio.rest import Client
import requests
from transformers import pipeline, AutoModelForSeq2SeqLM, AutoTokenizer
from langdetect import detect
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from PySide6.QtBluetooth import QBluetoothDeviceDiscoveryAgent, QBluetoothDeviceInfo
from PySide6.QtCore import QCoreApplication, QEventLoop
import tkinter as tk
from tkinter import messagebox
from cryptography.fernet import Fernet
import threading
import asyncio

# Twilio credentials
account_sid = ''
auth_token = ''
twilio_number = ''
emergency_contact_number = ''

# OpenCage API key
opencage_key = '762040660f5e44878d403cb66a76c168'

# Encryption key (make sure to keep this secure)
key = b'Keku--uzxBVUtp6R2d3a8PBQhCCv8v88XJXsvz95aCE='
cipher_suite = Fernet(key)

# Initialize NLP models
sentiment_analysis = pipeline("sentiment-analysis")
translation_model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-{src}-{tgt}")
tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-{src}-{tgt}")

# Function to encrypt data
def encrypt_data(data):
    return cipher_suite.encrypt(data.encode()).decode()

# Function to get current location
def get_location():
    try:
        url = f"https://api.opencagedata.com/geocode/v1/json?q=&key={opencage_key}"
        response = requests.get(url)
        response.raise_for_status()
        location_data = response.json()
        lat = location_data['results'][0]['geometry']['lat']
        lng = location_data['results'][0]['geometry']['lng']
        return lat, lng
    except requests.RequestException as e:
        print(f"Error getting location: {e}")
        return None, None

# Function to send alert message
def send_alert_message(location_url, device_info):
    try:
        encrypted_location = encrypt_data(location_url)
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=f"Help! I need assistance. My location: {encrypted_location}. Nearby devices: {device_info}",
            from_=twilio_number,
            to=emergency_contact_number
        )
        print(f"Alert sent: {message.sid}")
    except Exception as e:
        print(f"Error sending alert message: {e}")

# Function to authenticate user voice using aiortc
class VoiceActivityDetector(MediaStreamTrack):
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.vad = RTCPeerConnection()

    async def recv(self):
        frame = await super().recv()
        audio_data = frame.to_ndarray()
        if self.is_speech(audio_data):
            return True
        return False

    def is_speech(self, audio_data):
        # Implement your VAD logic here
        return True

# Function to scan for nearby Bluetooth devices using PySide6
def scan_bluetooth_devices():
    app = QCoreApplication([])
    discovery_agent = QBluetoothDeviceDiscoveryAgent()
    devices = []

    def device_discovered(device_info):
        devices.append(f"{device_info.address().toString()} - {device_info.name()}")

    discovery_agent.deviceDiscovered.connect(device_discovered)
    discovery_agent.start()
    
    loop = QEventLoop()
    discovery_agent.finished.connect(loop.quit)
    loop.exec()

    if devices:
        print(f"Nearby devices: {devices}")
        return devices
    else:
        print("No nearby devices found.")
        return "No devices found"

# Speech recognition and alerting logic
def listen_and_analyze():
    r = sr.Recognizer()
    while listening:
        with sr.Microphone() as source:
            print("Listening for distress signals...")
            try:
                audio = r.listen(source, timeout=5)
            except sr.WaitTimeoutError:
                print("Listening timed out, continuing...")
                continue

            try:
                audio_data = audio.get_wav_data()
                text = r.recognize_google(audio)
                language = detect(text)
                print(f"Detected language: {language}")

                if language != 'en':
                    inputs = tokenizer.encode(text, return_tensors="pt")
                    translated = translation_model.generate(inputs)
                    text = tokenizer.decode(translated[0], skip_special_tokens=True)
                    print(f"Translated text: {text}")

                vad = VoiceActivityDetector()
                if vad.is_speech(audio_data):
                    result = sentiment_analysis(text)[0]
                    if result['label'] == 'NEGATIVE':
                        print("Distress signal detected, sending alert...")
                        lat, lng = get_location()
                        if lat is not None and lng is not None:
                            location_url = f"https://maps.google.com/?q={lat},{lng}"
                            device_info = scan_bluetooth_devices()
                            send_alert_message(location_url, device_info)
                        else:
                            print("Could not obtain location.")
                    else:
                        print("No distress signal detected.")
                else:
                    print("Voice not recognized as user's.")
            except sr.UnknownValueError:
                print("Google Web Speech API could not understand audio")
            except sr.RequestError as e:
                print(f"Could not request results from Google Web Speech API; {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

# UI setup
def start_listening():
    global listening
    listening = True
    thread = threading.Thread(target=listen_and_analyze)
    thread.start()

def stop_listening():
    global listening
    listening = False

def add_contact():
    global emergency_contact_number
    emergency_contact_number = contact_entry.get()
    messagebox.showinfo("Contact Added", "Emergency contact added successfully!")

app = tk.Tk()
app.title("SafeGuard - Personal Safety Assistant")

tk.Label(app, text="SafeGuard - Personal Safety Assistant", font=("Helvetica", 16)).pack(pady=10)
tk.Button(app, text="Start Listening", command=start_listening, bg="green", fg="white", font=("Helvetica", 12)).pack(pady=5)
tk.Button(app, text="Stop Listening", command=stop_listening, bg="red", fg="white", font=("Helvetica", 12)).pack(pady=5)

tk.Label(app, text="Emergency Contact:").pack(pady=5)
contact_entry = tk.Entry(app, width=30)
contact_entry.pack(pady=5)
tk.Button(app, text="Add Contact", command=add_contact, font=("Helvetica", 12)).pack(pady=5)

app.mainloop()
