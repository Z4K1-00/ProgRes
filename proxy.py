import socket
import threading
import re
import requests
from urllib.parse import urlparse, urljoin
from flask import Flask, render_template, request
from bs4 import BeautifulSoup

app = Flask(__name__)

# Variables de configuration
filtrage_active = True
mots_interdits = ["YouTube"]


def extract_host(request_data):
    host_match = re.search(r'Host: (.+?)\r\n', request_data)
    if host_match:
        host = host_match.group(1).split(":")[0]
        return host
    return None

def extract_post_data(request_data):
    post_match = re.search(r'\r\n\r\n(.*)$', request_data, re.DOTALL)
    if post_match:
        post_data = post_match.group(1)
        return post_data
    return None

def modify_request(request_data, full_url):
    parsed_url = urlparse(full_url)
    path = parsed_url.path if parsed_url.path else '/'
    modified_request = re.sub(r'\s(/[^ ]*)\s', f' {urljoin(full_url, path)} ', request_data)
    return modified_request

def filter_html_content(html_content):
    if filtrage_active:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Exemple d'insertion de texte dans le titre
        if soup.title:
            soup.title.string = '***Proxy***' + soup.title.string

        # Exemple de remplacement de texte
        for mot_interdit in mots_interdits:
            for element in soup.find_all(text=re.compile(re.escape(mot_interdit), re.IGNORECASE)):
                element.replace_with('***CENSURE***')

        # Exemple de blocage de l'accès au contenu
        blocked_tags = ['script', 'iframe']
        for tag in blocked_tags:
            for element in soup.find_all(tag):
                element.decompose()

        # Exemple de suppression des ressources au format mp4
        for element in soup.find_all('source', {'type': 'video/mp4'}):
            element.decompose()

        # Ne pas filtrer le contenu des balises link pour les fichiers CSS
        for link in soup.find_all('link', {'rel': 'stylesheet'}):
            pass

        return str(soup)

    return html_content


def handle_client(client_socket):
    request_data = client_socket.recv(4096)
    host = extract_host(request_data.decode('utf-8'))
    if not host:
        print("[*] Impossible d'extraire le Host de la requête.")
        client_socket.close()
        return
    print(f'[*] Requête HTTP pour {host}')

    post_data = extract_post_data(request_data.decode('utf-8'))
    full_url = f'http://{host}'
    modified_request = modify_request(request_data.decode('utf-8'), full_url)

    try:
        response = requests.get(full_url)
        remote_data = response.content
    except Exception as e:
        print(f"[*] Erreur lors de la récupération des données du serveur distant: {e}")
        client_socket.close()
        return

    try:
        decoded_data = remote_data.decode('utf-8')
    except UnicodeDecodeError:
        # Utilisez un autre codec ou affichez les données brutes si la décodage échoue
        decoded_data = remote_data.decode('latin-1', errors='replace')
        
    filtered_data = filter_html_content(decoded_data)
    client_socket.sendall(filtered_data.encode('utf-8'))

    print(f'[*] Réponse du serveur pour {host}:\n{decoded_data}')

    client_socket.close()



@app.route('/')
def index():
    return render_template('index.html', filtrage_active=filtrage_active, mots_interdits=mots_interdits)


@app.route('/config', methods=['POST'])
def config():
    global filtrage_active, mots_interdits
    filtrage_active = request.form.get('filtrage_active') == 'on'
    mots_interdits = [mot.strip() for mot in request.form.get('mots_interdits').split(',')]
    return render_template('index.html', filtrage_active=filtrage_active, mots_interdits=mots_interdits)


def start_proxy(local_port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', local_port))
    server.listen(5)

    print(f'[*] Proxy en écoute sur le port {local_port}')

    while True:
        client_socket, addr = server.accept()
        print(f'[*] Connexion acceptée de {addr[0]}:{addr[1]}')

        proxy_thread = threading.Thread(target=handle_client, args=(client_socket,))
        proxy_thread.start()


if __name__ == '__main__':
    local_port = 8888
    proxy_thread = threading.Thread(target=start_proxy, args=(local_port,))
    proxy_thread.start()

    # Lancer l'application Flask pour la configuration web
    app.run(debug=True, port=5000)